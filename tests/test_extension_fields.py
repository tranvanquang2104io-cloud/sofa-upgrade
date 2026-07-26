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


def _q_payload(number, **extra):
    data = {
        "quotation_number": number, "quotation_date": "2026-07-26", "vat_rate": "10",
        "item_name[]": ["Fabric"], "item_unit[]": ["m"],
        "item_quantity[]": ["1"], "item_price[]": ["100000"],
    }
    data.update(extra)
    return data


def test_extension_value_saved_and_required_enforced(app, client, login, seeded_order):
    """End-to-end: a required text extension field is enforced and stored."""
    from app.config import db
    from app.models.models import Quotation
    cid = seeded_order["company_id"]
    with app.app_context():
        db.session.add(_cfg(cid, "quotation", "extend01", label="PO", is_required=True))
        db.session.commit()

    login(username="admin")

    # Missing the required extension value → quotation NOT created.
    client.post(f"/quotations/{seeded_order['order_id']}/create",
                data=_q_payload("QE-1"), follow_redirects=True)
    with app.app_context():
        assert Quotation.query.filter_by(quotation_number="QE-1").first() is None

    # Provided → created and the value is persisted in the extend01 column.
    client.post(f"/quotations/{seeded_order['order_id']}/create",
                data=_q_payload("QE-2", extend01="PO-123"), follow_redirects=True)
    with app.app_context():
        q = Quotation.query.filter_by(quotation_number="QE-2").first()
        assert q is not None
        assert q.extend01 == "PO-123"
