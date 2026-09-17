"""HỢP ĐỒNG NGUYÊN TẮC and the ĐƠN ĐẶT HÀNG issued under it.

The rules being pinned here are legal/commercial, not merely technical:
  * an order under an active framework agreement gets an ĐƠN ĐẶT HÀNG, not a
    second full contract;
  * a customer with no agreement is completely unaffected (no migration);
  * an already-issued confirmation survives the agreement expiring, because it
    was a completed offer+acceptance in its own right (BLDS 2015 Đ.386+393);
  * prices are snapshotted, so a later revision never rewrites a past order.
"""
import datetime as dt

import pytest

from app.models.models import MasterAgreement, MasterAgreementPriceLine
from app.services.agreement_service import (
    DOC_CONTRACT,
    DOC_ORDER_CONFIRMATION,
    AgreementService,
    product_key,
)

TODAY = dt.date(2026, 6, 15)


@pytest.fixture()
def agreement(app, seed):
    """An active HĐNT covering the seeded customer for all of 2026."""
    from app.config import db

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-2026-001",
            signed_date=dt.date(2026, 1, 1),
            effective_from=dt.date(2026, 1, 1),
            effective_to=dt.date(2026, 12, 31),
            status=MasterAgreement.STATUS_ACTIVE,
            payment_terms="Thanh toán trong 30 ngày",
        )
        db.session.add(ma)
        db.session.commit()
        return str(ma.id)


@pytest.fixture()
def order(app, seed):
    from app.config import db
    from app.models import Order

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-MA1",
                  title="Sofa order under framework")
        db.session.add(o)
        db.session.commit()
        return str(o.id)


def _order(order_id):
    from app.models import Order
    return Order.query.get(order_id)


def _agreement(agreement_id):
    return MasterAgreement.query.get(agreement_id)


ITEMS = [
    {'name': 'Sofa 3 chỗ', 'unit': 'bộ', 'quantity': 2,
     'unit_price': 10_000_000, 'total': 20_000_000},
]


# --- the routing decision -------------------------------------------------

def test_customer_without_an_agreement_still_gets_a_contract(app, order):
    """No agreement => unchanged behaviour. This is why no migration is needed."""
    with app.app_context():
        kind, found = AgreementService.resolve_document_kind(_order(order), TODAY)
        assert kind == DOC_CONTRACT
        assert found is None


def test_customer_with_an_active_agreement_gets_an_order_confirmation(
        app, order, agreement):
    with app.app_context():
        kind, found = AgreementService.resolve_document_kind(_order(order), TODAY)
        assert kind == DOC_ORDER_CONFIRMATION
        assert found.agreement_number == "HDNT-2026-001"


def test_a_draft_agreement_does_not_route_orders_to_it(app, order, agreement):
    from app.config import db
    with app.app_context():
        _agreement(agreement).status = MasterAgreement.STATUS_DRAFT
        db.session.commit()
        kind, _ = AgreementService.resolve_document_kind(_order(order), TODAY)
        assert kind == DOC_CONTRACT


def test_a_suspended_agreement_blocks_new_releases(app, order, agreement):
    """A customer in dispute should not be able to place new orders."""
    with app.app_context():
        AgreementService.suspend(_agreement(agreement), reason='Payment dispute')
        kind, _ = AgreementService.resolve_document_kind(_order(order), TODAY)
        assert kind == DOC_CONTRACT


def test_an_expired_agreement_is_not_used_for_new_orders(app, order, agreement):
    with app.app_context():
        after_expiry = dt.date(2027, 1, 5)
        kind, _ = AgreementService.resolve_document_kind(_order(order),
                                                         after_expiry)
        assert kind == DOC_CONTRACT


def test_an_open_ended_agreement_never_expires(app, order, agreement):
    """effective_to NULL = vô thời hạn, common in Vietnamese practice."""
    from app.config import db
    with app.app_context():
        _agreement(agreement).effective_to = None
        db.session.commit()
        kind, _ = AgreementService.resolve_document_kind(
            _order(order), dt.date(2030, 1, 1))
        assert kind == DOC_ORDER_CONFIRMATION


# --- issuing the release order -------------------------------------------

def test_creating_a_confirmation_cites_the_agreement(app, order, agreement):
    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-001", confirmation_date=TODAY, vat_rate=8)

        assert conf.cited_agreement_number == "HDNT-2026-001"
        assert conf.cited_agreement_date == dt.date(2026, 1, 1)
        assert float(conf.subtotal) == 20_000_000
        assert float(conf.vat_amount) == 1_600_000
        assert float(conf.total_amount) == 21_600_000


def test_confirmation_inherits_payment_terms_from_the_agreement(
        app, order, agreement):
    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-002", confirmation_date=TODAY)
        assert conf.payment_terms == "Thanh toán trong 30 ngày"


def test_cannot_issue_against_an_agreement_that_is_not_in_effect(
        app, order, agreement):
    with app.app_context():
        with pytest.raises(ValueError, match='not in effect'):
            AgreementService.create_confirmation(
                _order(order), _agreement(agreement), ITEMS,
                confirmation_number="DDH-003",
                confirmation_date=dt.date(2027, 3, 1))


def test_duplicate_confirmation_number_is_refused(app, order, agreement):
    with app.app_context():
        AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-DUP", confirmation_date=TODAY)
        with pytest.raises(ValueError, match='already exists'):
            AgreementService.create_confirmation(
                _order(order), _agreement(agreement), ITEMS,
                confirmation_number="DDH-DUP", confirmation_date=TODAY)


def test_confirming_marks_the_order_contracted_and_signed(app, order, agreement):
    """An accepted order is offer+acceptance in one step — no separate signing."""
    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-004", confirmation_date=TODAY)
        AgreementService.confirm(conf)

        lifecycle = _order(order).lifecycle
        assert lifecycle.contract_created is True
        assert lifecycle.contract_signed is True


def test_an_issued_confirmation_survives_the_agreement_expiring(
        app, order, agreement):
    """It was a completed contract in its own right; expiry only stops NEW ones."""
    from app.config import db
    from app.models.models import OrderConfirmation

    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-005", confirmation_date=TODAY)
        AgreementService.confirm(conf)

        AgreementService.terminate(_agreement(agreement), reason='Ended')

        still = OrderConfirmation.query.filter_by(
            confirmation_number="DDH-005").first()
        assert still is not None
        assert still.is_confirmed, "a completed transaction must not be undone"


# --- pricing --------------------------------------------------------------

def _add_price_line(app, agreement_id, name, price, frm=None, to=None):
    from app.config import db
    with app.app_context():
        db.session.add(MasterAgreementPriceLine(
            agreement_id=agreement_id, product_key=product_key(name),
            product_name=name, agreed_unit_price=price,
            effective_from=frm, effective_to=to))
        db.session.commit()


def test_agreed_price_overrides_the_quoted_price(app, order, agreement):
    _add_price_line(app, agreement, 'Sofa 3 chỗ', 9_000_000)

    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-006", confirmation_date=TODAY, vat_rate=8)

        assert conf.items[0]['unit_price'] == 9_000_000
        assert conf.items[0]['price_source'] == 'agreement'
        assert float(conf.subtotal) == 18_000_000, "2 x 9,000,000"


def test_a_discount_line_is_applied_to_the_quoted_price(app, order, agreement):
    from app.config import db
    with app.app_context():
        db.session.add(MasterAgreementPriceLine(
            agreement_id=agreement, product_key=product_key('Sofa 3 chỗ'),
            product_name='Sofa 3 chỗ', discount_pct=10))
        db.session.commit()

        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-007", confirmation_date=TODAY)
        assert conf.items[0]['unit_price'] == 9_000_000, "10% off 10,000,000"


def test_items_with_no_price_line_keep_their_quoted_price(app, order, agreement):
    """An agreement need only price the products it actually covers."""
    _add_price_line(app, agreement, 'Ghế đơn', 1_000_000)

    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-008", confirmation_date=TODAY)
        assert conf.items[0]['unit_price'] == 10_000_000


def test_price_lookup_respects_line_validity_dates(app, order, agreement):
    """A revised price must not rewrite what an earlier order was charged."""
    _add_price_line(app, agreement, 'Sofa 3 chỗ', 9_000_000,
                    frm=dt.date(2026, 1, 1), to=dt.date(2026, 5, 31))
    _add_price_line(app, agreement, 'Sofa 3 chỗ', 9_500_000,
                    frm=dt.date(2026, 6, 1), to=None)

    with app.app_context():
        early = AgreementService.price_for(_agreement(agreement), 'Sofa 3 chỗ',
                                           dt.date(2026, 3, 1))
        later = AgreementService.price_for(_agreement(agreement), 'Sofa 3 chỗ',
                                           dt.date(2026, 7, 1))
        assert float(early.agreed_unit_price) == 9_000_000
        assert float(later.agreed_unit_price) == 9_500_000


def test_prices_are_snapshotted_onto_the_confirmation(app, order, agreement):
    """Changing the price list later must not alter an issued document."""
    from app.config import db
    _add_price_line(app, agreement, 'Sofa 3 chỗ', 9_000_000)

    with app.app_context():
        conf = AgreementService.create_confirmation(
            _order(order), _agreement(agreement), ITEMS,
            confirmation_number="DDH-009", confirmation_date=TODAY)
        conf_id = conf.id

        line = MasterAgreementPriceLine.query.filter_by(
            agreement_id=agreement).first()
        line.agreed_unit_price = 12_000_000
        db.session.commit()

        from app.models.models import OrderConfirmation
        reloaded = OrderConfirmation.query.get(conf_id)
        assert reloaded.items[0]['unit_price'] == 9_000_000, (
            "the issued document must keep the price it was issued with"
        )


def test_product_key_is_normalized_for_matching():
    assert product_key('  Sofa 3 Chỗ ') == product_key('sofa 3 chỗ')
