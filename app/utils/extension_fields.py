"""Admin-configurable extension fields (extend01..extend10) — see AUDIT D9.

Each document type (quotation, contract, handover, payment) has ten reserved
TEXT columns. Per company, an admin enables a slot and gives it a label, a data
type (text|number|date|boolean) and whether it is required, via
``ExtensionFieldConfig``. This module reads that config and validates/collects
the values submitted on a document form.
"""
from datetime import datetime

from app.models.models import ExtensionFieldConfig, EXTENSION_FIELD_KEYS

ENTITY_TYPES = ExtensionFieldConfig.ENTITY_TYPES
DATA_TYPES = ExtensionFieldConfig.DATA_TYPES
FIELD_KEYS = EXTENSION_FIELD_KEYS


def get_enabled_configs(company_id, entity_type):
    """Enabled extension-field configs for a company + entity type, ordered."""
    return (ExtensionFieldConfig.query
            .filter_by(company_id=company_id, entity_type=entity_type, is_enabled=True)
            .order_by(ExtensionFieldConfig.sort_order, ExtensionFieldConfig.field_key)
            .all())


def _label(cfg):
    return cfg.label or cfg.field_key


def _validate_and_normalize(cfg, raw):
    """Validate a raw string against the slot's data type; return the value to
    store (text). Raises ValueError with a human message on invalid input."""
    dt = cfg.data_type
    if dt == 'number':
        try:
            float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{_label(cfg)}: phải là số")
        return raw
    if dt == 'date':
        try:
            datetime.strptime(raw, '%Y-%m-%d')
        except (TypeError, ValueError):
            raise ValueError(f"{_label(cfg)}: phải là ngày (YYYY-MM-DD)")
        return raw
    # text
    return raw


def collect_extension_values(company_id, entity_type, form):
    """Read + validate the extension values from a submitted form.

    Returns a dict {field_key: value_or_None} for the enabled slots. Raises
    ValueError if a required field is empty or a value fails its type check.
    Booleans are derived from checkbox presence (never "required-missing").
    """
    values = {}
    for cfg in get_enabled_configs(company_id, entity_type):
        if cfg.data_type == 'boolean':
            raw = (form.get(cfg.field_key) or '').strip().lower()
            values[cfg.field_key] = 'true' if raw in ('true', '1', 'on', 'yes') else 'false'
            continue
        raw = (form.get(cfg.field_key) or '').strip()
        if not raw:
            if cfg.is_required:
                raise ValueError(f"{_label(cfg)}: bắt buộc nhập")
            values[cfg.field_key] = None
            continue
        values[cfg.field_key] = _validate_and_normalize(cfg, raw)
    return values


def apply_extension_values(doc, values):
    """Set collected extension values onto a document ORM object (caller commits)."""
    for key, val in values.items():
        setattr(doc, key, val)
    return bool(values)
