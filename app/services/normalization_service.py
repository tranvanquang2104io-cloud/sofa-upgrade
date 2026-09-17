"""Applies the per-company data-standardization rules.

WHERE THIS RUNS, AND WHY IT MATTERS
-----------------------------------
At the **ORM boundary** (SQLAlchemy ``before_insert`` / ``before_update``),
not in the routes.

The app has several write paths for the same data — the route layer, the
service layer, and the seed/import scripts in ``scripts/`` — and more will be
added. Normalising in the routes would mean every future write path has to
remember to call it, and one that forgets reintroduces exactly the
inconsistency this feature exists to remove. The mapper event is the one place
every path is guaranteed to pass through. This is the same choice Odoo (model
layer) and Salesforce (platform layer) make, rather than enforcing in the UI.

SAFETY RAILS
------------
* Identifier fields are refused outright (``is_protected_field``) whatever the
  configuration says — "tidying" a tax code or an invoice number corrupts a
  legal identifier, or hides a data-entry error that should have been raised.
* ``confirm``-mode rules never rewrite the value; they record a
  ``NormalizationSuggestion`` for a human to accept.
* A failure here must never block a save. Normalisation is a convenience; a
  bug in it must not stop a business from recording an order.
"""
import logging

from app.config.database import db
from app.models.models import NormalizationRule
from app.utils.text_normalize import (
    PRIMITIVES,
    apply_primitives,
    is_protected_field,
)

logger = logging.getLogger(__name__)

# Always applied first to every configured text field, regardless of rules:
# NFC is a correctness fix (see text_normalize), not a house-style choice.
ALWAYS_PRIMITIVES = ('nfc',)


# Sensible Vietnamese defaults, seeded per company.
# (entity_type, field_name, primitives, mode)
DEFAULT_RULES = (
    # Customers: the business asked for uppercase customer names so documents
    # are visually consistent.
    ('customer', 'name',
     ['nfc', 'trim', 'collapse_whitespace', 'normalize_punctuation', 'upper'], 'auto'),
    ('customer', 'representative_name',
     ['nfc', 'trim', 'collapse_whitespace', 'title_case'], 'auto'),
    ('customer', 'address',
     ['nfc', 'trim', 'collapse_whitespace', 'normalize_punctuation'], 'auto'),

    # Suppliers are companies: legal form uppercase, distinctive part Title Case.
    ('supplier', 'name',
     ['nfc', 'trim', 'collapse_whitespace', 'company_name_case'], 'auto'),
    ('supplier', 'address',
     ['nfc', 'trim', 'collapse_whitespace', 'normalize_punctuation'], 'auto'),

    # Items/materials: first letter only — the rest may legitimately contain
    # model names and acronyms.
    ('material', 'name',
     ['nfc', 'trim', 'collapse_whitespace', 'capitalize_first'], 'auto'),

    # Free text: capitalise sentence starts, leave the body alone.
    ('order', 'title',
     ['nfc', 'trim', 'collapse_whitespace', 'capitalize_first'], 'auto'),
    ('order', 'description',
     ['nfc', 'trim', 'collapse_whitespace', 'normalize_punctuation',
      'sentence_case'], 'auto'),
)

# Entities wired to the mapper events. Keyed by the entity_type used in rules.
NORMALIZED_ENTITIES = {
    'customer': 'Customer',
    'supplier': 'Supplier',
    'material': 'Material',
    'order': 'Order',
}


class NormalizationService:
    """Reads the rules and applies them to model instances."""

    @staticmethod
    def seed_defaults(company_id, overwrite=False):
        """Install the default Vietnamese rule set for a company (idempotent)."""
        created = 0
        for index, (entity, field, primitives, mode) in enumerate(DEFAULT_RULES):
            existing = NormalizationRule.query.filter_by(
                company_id=company_id, entity_type=entity, field_name=field,
            ).first()
            if existing:
                if overwrite:
                    existing.primitives = list(primitives)
                    existing.mode = mode
                    existing.is_active = True
                continue
            db.session.add(NormalizationRule(
                company_id=company_id, entity_type=entity, field_name=field,
                primitives=list(primitives), mode=mode, sort_order=index,
            ))
            created += 1
        db.session.commit()
        logger.info("Seeded %s normalization rules for company %s",
                    created, company_id)
        return created

    @staticmethod
    def rules_for(company_id, entity_type):
        if not company_id:
            return []
        return NormalizationRule.query.filter_by(
            company_id=company_id, entity_type=entity_type, is_active=True,
        ).order_by(NormalizationRule.sort_order).all()

    @staticmethod
    def preview(value, primitives):
        """Apply primitives to a value without touching anything stored."""
        return apply_primitives(value, list(ALWAYS_PRIMITIVES) + list(primitives))

    @classmethod
    def normalize_instance(cls, instance, entity_type, company_id=None):
        """Apply the company's ``auto`` rules to ``instance`` in place.

        Returns a list of ``(field, original, suggested)`` for ``confirm``-mode
        rules whose output differs — the caller decides whether to persist
        them as suggestions.
        """
        company_id = company_id or getattr(instance, 'company_id', None)
        pending = []

        for rule in cls.rules_for(company_id, entity_type):
            field = rule.field_name

            # Never normalise an identifier, whatever the config says.
            if is_protected_field(field):
                logger.debug("Skipping protected field %s.%s", entity_type, field)
                continue
            if not hasattr(instance, field):
                continue

            original = getattr(instance, field)
            if not isinstance(original, str) or not original.strip():
                continue

            primitives = [p for p in (rule.primitives or []) if p in PRIMITIVES]
            new_value = cls.preview(original, primitives)
            if new_value == original:
                continue

            if rule.mode == NormalizationRule.MODE_CONFIRM:
                pending.append((field, original, new_value))
            else:
                setattr(instance, field, new_value)

        return pending


def _make_listener(entity_type):
    def _listener(mapper, connection, target):
        # Never let a normalisation bug block a business record from saving.
        try:
            NormalizationService.normalize_instance(target, entity_type)
        except Exception:
            logger.exception("Normalization failed for %s; saving unchanged",
                             entity_type)
    return _listener


_LISTENERS_REGISTERED = False


def register_normalization_listeners():
    """Attach the mapper events. Safe to call more than once.

    The app factory runs once per test, and mapper events are registered on
    the CLASS, not the app — so without this guard every extra ``create_app``
    would stack another listener and run the rules N times per save.
    """
    global _LISTENERS_REGISTERED
    if _LISTENERS_REGISTERED:
        return

    from sqlalchemy import event
    from app.models import models as m

    for entity_type, model_name in NORMALIZED_ENTITIES.items():
        model = getattr(m, model_name, None)
        if model is None:
            continue
        listener = _make_listener(entity_type)
        event.listen(model, 'before_insert', listener)
        event.listen(model, 'before_update', listener)
    _LISTENERS_REGISTERED = True
    logger.info("Normalization listeners registered for %s entities",
                len(NORMALIZED_ENTITIES))
