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

    @staticmethod
    def configurable_fields(entity_type, company_id=None):
        """Every text field of ``entity_type``, with whatever rule it has now.

        Discovered from the data model, not from a seed list. The screen used
        to show only the rules somebody had seeded, so a field nobody thought
        of in advance could never be configured at all — and the rule's target
        was a bare string, which is no answer to "how does the system know
        which field I mean".

        Returns ``[{field_name, type, protected, primitives, mode}]``. A field
        with no rule comes back with an empty ``primitives`` list, which is what
        lets the screen be a grid of empty cells rather than a create form.

        Protected identifiers are INCLUDED and flagged rather than filtered
        out: absent would read as an oversight, locked reads as a decision.
        """
        from sqlalchemy import String, Text

        from app.models import models as m

        model = getattr(m, NORMALIZED_ENTITIES.get(entity_type, ''), None)
        if model is None:
            return []

        applied = {}
        if company_id is not None:
            for rule in NormalizationRule.query.filter_by(
                    company_id=company_id, entity_type=entity_type).all():
                applied[rule.field_name] = rule

        rows = []
        for column in model.__table__.columns:
            if not isinstance(column.type, (String, Text)):
                continue
            # Foreign keys and ids are strings on some backends; they are
            # plumbing, not text a person typed.
            if column.foreign_keys or column.primary_key:
                continue
            rule = applied.get(column.name)
            rows.append({
                'field_name': column.name,
                'type': 'text' if isinstance(column.type, Text) else 'string',
                'protected': bool(is_protected_field(column.name)),
                'primitives': list(rule.primitives or []) if rule else [],
                'mode': rule.mode if rule else NormalizationRule.MODE_AUTO,
                'is_active': bool(rule.is_active) if rule else False,
            })
        rows.sort(key=lambda row: (row['protected'], row['field_name']))
        return rows

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


_SUGGESTIONS_KEY = '_normalization_suggestions'


def pending_suggestions():
    """Suggestions raised by ``confirm`` rules during this request.

    The settings screen tells the admin a confirm rule is "suggested only - the
    value is never rewritten without a person agreeing". The first half was
    true and the second never happened: normalize_instance() returns the
    pending list and the listener dropped it, so choosing confirm looked like
    choosing caution and was actually choosing nothing.

    Kept on ``g`` rather than in a table. A suggestion is only worth acting on
    while the record is still in mind; an inbox you have to remember to visit
    is the wrong shape for this product, and it would need a migration and a
    screen to say something that fits in one sentence.
    """
    from flask import g, has_request_context

    if not has_request_context():
        return []
    return list(getattr(g, _SUGGESTIONS_KEY, []))


def _record_suggestions(entity_type, pending):
    from flask import g, has_request_context

    if not has_request_context() or not pending:
        return
    collected = getattr(g, _SUGGESTIONS_KEY, None)
    if collected is None:
        collected = []
        setattr(g, _SUGGESTIONS_KEY, collected)
    for field, original, suggested in pending:
        collected.append({'entity_type': entity_type, 'field': field,
                          'original': original, 'suggested': suggested})


def _make_listener(entity_type):
    def _listener(mapper, connection, target):
        # Never let a normalisation bug block a business record from saving.
        try:
            pending = NormalizationService.normalize_instance(target, entity_type)
            _record_suggestions(entity_type, pending)
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
