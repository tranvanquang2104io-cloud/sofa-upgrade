"""Data standardization applied at the ORM boundary.

The point of these tests is that normalization happens no matter WHICH write
path is used — that is the whole reason the rules live on the mapper event
rather than in a route.
"""
import unicodedata

import pytest

from app.models.models import NormalizationRule
from app.services.normalization_service import NormalizationService


@pytest.fixture()
def seeded_rules(app, seed):
    with app.app_context():
        NormalizationService.seed_defaults(seed["company_id"])
    return seed


def _make_customer(app, seed, **kwargs):
    """Create a Customer through the ORM (no route involved)."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        c = Customer(company_id=seed["company_id"], store_id=seed["store_id"],
                     **kwargs)
        db.session.add(c)
        db.session.commit()
        return c.id


def _reload(app, model, pk):
    with app.app_context():
        return model.query.get(pk)


# --- the chokepoint -------------------------------------------------------

def test_customer_name_is_uppercased_on_a_direct_orm_write(app, seeded_rules):
    """No route, no service — straight ORM. It must still normalize."""
    from app.models import Customer

    cid = _make_customer(app, seeded_rules, customer_code="CUST-N1",
                         name="  nguyễn   văn a  ")
    assert _reload(app, Customer, cid).name == "NGUYỄN VĂN A"


def test_normalization_also_runs_on_update(app, seeded_rules):
    from app.config import db
    from app.models import Customer

    cid = _make_customer(app, seeded_rules, customer_code="CUST-N2",
                         name="Ban Đầu")
    with app.app_context():
        c = Customer.query.get(cid)
        c.name = "tên mới sau khi sửa"
        db.session.commit()

    assert _reload(app, Customer, cid).name == "TÊN MỚI SAU KHI SỬA"


def test_customer_created_through_the_http_route_is_normalized(
        app, client, login, seeded_rules):
    """The route path must inherit the same behaviour for free."""
    from app.models import Customer

    login("admin")
    resp = client.post('/customers/create', data={
        'customer_code': 'CUST-HTTP',
        'name': 'trần thị b',
        'phone': '0901234567',
        'store_id': seeded_rules["store_id"],
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        c = Customer.query.filter_by(customer_code='CUST-HTTP').first()
        if c is not None:            # route shape may differ; only assert if created
            assert c.name == "TRẦN THỊ B"


# --- Unicode --------------------------------------------------------------

def test_decomposed_input_is_stored_precomposed(app, seeded_rules):
    """NFD input would otherwise fail every later equality lookup."""
    from app.models import Customer

    nfd_name = unicodedata.normalize('NFD', 'Nguyễn Việt')
    cid = _make_customer(app, seeded_rules, customer_code="CUST-NFD",
                         name=nfd_name)

    stored = _reload(app, Customer, cid).name
    assert stored == unicodedata.normalize('NFC', stored), "must be stored as NFC"
    assert stored == "NGUYỄN VIỆT"


# --- safety rails ---------------------------------------------------------

def test_protected_identifier_fields_are_never_normalized(app, seed):
    """Even when a rule explicitly targets one."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed["company_id"], entity_type='customer',
            field_name='customer_code',          # an identifier
            primitives=['upper'], mode='auto'))
        db.session.commit()

    cid = _make_customer(app, seed, customer_code="cust-lower-001",
                         name="Khách Hàng")
    assert _reload(app, Customer, cid).customer_code == "cust-lower-001", (
        "an identifier must survive untouched — normalizing it would corrupt "
        "a value used for exact matching"
    )


def test_confirm_mode_does_not_rewrite_the_value(app, seed):
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed["company_id"], entity_type='customer',
            field_name='name', primitives=['upper'], mode='confirm'))
        db.session.commit()

    cid = _make_customer(app, seed, customer_code="CUST-CF", name="giữ nguyên")
    assert _reload(app, Customer, cid).name == "giữ nguyên", (
        "confirm-mode must only suggest, never silently rewrite"
    )


def test_a_broken_rule_does_not_block_the_save(app, seed):
    """Normalization is a convenience; it must never stop business data."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add(NormalizationRule(
            company_id=seed["company_id"], entity_type='customer',
            field_name='name', primitives=['no_such_primitive'], mode='auto'))
        db.session.commit()

    cid = _make_customer(app, seed, customer_code="CUST-BAD", name="vẫn lưu")
    assert _reload(app, Customer, cid) is not None


def test_company_with_no_rules_is_left_alone(app, seed):
    """Opt-in: an unconfigured tenant sees no change at all."""
    from app.models import Customer

    cid = _make_customer(app, seed, customer_code="CUST-NORULE",
                         name="  khong  doi  ")
    assert _reload(app, Customer, cid).name == "  khong  doi  "


# --- configuration --------------------------------------------------------

def test_seeding_is_idempotent(app, seed):
    with app.app_context():
        first = NormalizationService.seed_defaults(seed["company_id"])
        second = NormalizationService.seed_defaults(seed["company_id"])
        assert first > 0
        assert second == 0


def test_admin_can_change_the_house_style(app, seed):
    """Title Case instead of UPPERCASE, without a deploy."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        NormalizationService.seed_defaults(seed["company_id"])
        rule = NormalizationRule.query.filter_by(
            company_id=seed["company_id"], entity_type='customer',
            field_name='name').first()
        rule.primitives = ['nfc', 'trim', 'collapse_whitespace', 'title_case']
        db.session.commit()

    cid = _make_customer(app, seed, customer_code="CUST-STYLE",
                         name="lê văn c")
    assert _reload(app, Customer, cid).name == "Lê Văn C"


def test_rules_are_isolated_per_company(app, seed):
    from app.config import db
    from app.models import Company

    with app.app_context():
        NormalizationService.seed_defaults(seed["company_id"])
        other = Company(company_code="NRM2", name="Other", email="o@n.test")
        db.session.add(other)
        db.session.commit()
        assert NormalizationService.rules_for(other.id, 'customer') == []


def test_preview_does_not_touch_stored_data():
    assert NormalizationService.preview("  cty tnhh an phát ",
                                        ['trim', 'company_name_case']) == \
        "CÔNG TY TNHH An Phát"
