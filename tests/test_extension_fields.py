"""Extension-field config + validation (D9)."""
import pytest


def _cfg(company_id, entity_type, key, **kw):
    from app.models.models import ExtensionFieldConfig
    defaults = dict(is_enabled=True, data_type='text', is_required=False, sort_order=0, label=key)
    defaults.update(kw)
    return ExtensionFieldConfig(company_id=company_id, entity_type=entity_type,
                                field_key=key, **defaults)


@pytest.fixture()
def configured(app, seed):
    """Enable a few extension slots on 'quotation' for the seeded company."""
    from app.config import db
    cid = seed["company_id"]
    with app.app_context():
        db.session.add_all([
            _cfg(cid, "quotation", "extend01", label="PO Number", data_type="text", is_required=True),
            _cfg(cid, "quotation", "extend02", label="Delivery Date", data_type="date"),
            _cfg(cid, "quotation", "extend03", label="Priority", data_type="number"),
            _cfg(cid, "quotation", "extend04", label="Rush", data_type="boolean"),
            _cfg(cid, "quotation", "extend05", label="Disabled", is_enabled=False),
        ])
        db.session.commit()
    return seed


def test_required_field_missing_raises(app, configured):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        with pytest.raises(ValueError, match="PO Number"):
            collect_extension_values(configured["company_id"], "quotation", {})


def test_invalid_number_raises(app, configured):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        with pytest.raises(ValueError, match="Priority"):
            collect_extension_values(configured["company_id"], "quotation",
                                     {"extend01": "PO-1", "extend03": "abc"})


def test_invalid_date_raises(app, configured):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        with pytest.raises(ValueError, match="Delivery Date"):
            collect_extension_values(configured["company_id"], "quotation",
                                     {"extend01": "PO-1", "extend02": "31-12-2026"})


def test_valid_values_collected(app, configured):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        vals = collect_extension_values(configured["company_id"], "quotation", {
            "extend01": "PO-1", "extend02": "2026-12-31",
            "extend03": "5", "extend04": "on",
        })
    assert vals["extend01"] == "PO-1"
    assert vals["extend02"] == "2026-12-31"
    assert vals["extend03"] == "5"
    assert vals["extend04"] == "true"
    # Disabled slot (extend05) is never collected.
    assert "extend05" not in vals


def test_boolean_unchecked_is_false(app, configured):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        vals = collect_extension_values(configured["company_id"], "quotation",
                                        {"extend01": "PO-1"})
    assert vals["extend04"] == "false"


def test_no_config_yields_empty(app, seed):
    from app.utils.extension_fields import collect_extension_values
    with app.app_context():
        assert collect_extension_values(seed["company_id"], "contract", {"extend01": "x"}) == {}
