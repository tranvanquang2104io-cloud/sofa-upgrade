"""The framework-agreement route to cash, correct to the đồng.

A customer with a HỢP ĐỒNG NGUYÊN TẮC does not sign a contract per order: each
order is an ĐƠN ĐẶT HÀNG citing the agreement, and the agreed price list
supplies the prices. That makes this a second O2C chain with its own
arithmetic, and one extra thing to get right — a price agreed today must not be
rewritten when the price list is revised tomorrow.

The numbers:

    agreed price list   sofa 11,000,000 · armchair 3,800,000

    order  2 sofas + 1 armchair = 25,800,000 subtotal
           VAT 8%               =  2,064,000
           delivery (not taxed) =    400,000
                                   ----------
                                   28,264,000 total

    a later revision to 12,000,000 must not move the order already issued.
"""
import datetime as dt

import pytest

from app.services.agreement_service import AgreementService, product_key

EFFECTIVE = dt.date(2026, 1, 1)
ORDER_DATE = dt.date(2026, 3, 10)

SOFA_PRICE = 11_000_000
CHAIR_PRICE = 3_800_000
SUBTOTAL = 2 * SOFA_PRICE + 1 * CHAIR_PRICE     # 25,800,000
VAT_AMOUNT = 2_064_000
DELIVERY = 400_000
TOTAL = 28_264_000

ITEMS = [
    {'name': 'Sofa góc', 'unit': 'bộ', 'quantity': 2},
    {'name': 'Ghế đơn', 'unit': 'chiếc', 'quantity': 1},
]


@pytest.fixture()
def agreed(app, seed):
    """An active agreement with a two-line price list, and an order to fill."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        LifecycleStatus, MasterAgreement, MasterAgreementPriceLine,
    )

    with app.app_context():
        agreement = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-2026', effective_from=EFFECTIVE,
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(agreement)
        db.session.flush()
        db.session.add_all([
            MasterAgreementPriceLine(
                agreement_id=agreement.id, product_key=product_key('Sofa góc'),
                product_name='Sofa góc', unit='bộ',
                agreed_unit_price=SOFA_PRICE, effective_from=EFFECTIVE),
            MasterAgreementPriceLine(
                agreement_id=agreement.id, product_key=product_key('Ghế đơn'),
                product_name='Ghế đơn', unit='chiếc',
                agreed_unit_price=CHAIR_PRICE, effective_from=EFFECTIVE),
        ])

        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HDNT',
                      title='Đợt giao tháng 3')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()

        return {'agreement_id': str(agreement.id), 'order_id': str(order.id),
                **seed}


def _agreement(agreement_id):
    from app.models.models import MasterAgreement
    return MasterAgreement.query.get(agreement_id)


def _order(order_id):
    from app.models import Order
    return Order.query.get(order_id)


def _issue(app, agreed, number='DDH-001', items=None, when=ORDER_DATE):
    return AgreementService.create_confirmation(
        _order(agreed['order_id']), _agreement(agreed['agreement_id']),
        items if items is not None else [dict(i) for i in ITEMS],
        confirmation_number=number, confirmation_date=when,
        vat_rate=8, shipping_fee=DELIVERY)


# --- the prices come from the agreement ----------------------------------

def test_the_order_is_priced_from_the_agreed_list(app, agreed):
    with app.app_context():
        confirmation = _issue(app, agreed)

        prices = {line['name']: float(line['unit_price'])
                  for line in confirmation.items}
        assert prices['Sofa góc'] == SOFA_PRICE
        assert prices['Ghế đơn'] == CHAIR_PRICE


def test_the_totals_match_hand_calculation(app, agreed):
    with app.app_context():
        confirmation = _issue(app, agreed)

        assert float(confirmation.subtotal) == SUBTOTAL
        assert float(confirmation.vat_amount) == VAT_AMOUNT
        assert float(confirmation.total_amount) == TOTAL


def test_delivery_is_added_after_tax(app, agreed):
    """Taxing it too would add 32,000 to this order."""
    with app.app_context():
        confirmation = _issue(app, agreed)
        assert float(confirmation.total_amount) == (
            SUBTOTAL + VAT_AMOUNT + DELIVERY)


# --- the snapshot -------------------------------------------------------

def test_a_later_price_revision_does_not_rewrite_an_issued_order(app, agreed):
    """The whole reason prices are snapshotted onto the ĐĐH."""
    from app.config import db
    from app.models.models import MasterAgreementPriceLine, OrderConfirmation

    with app.app_context():
        confirmation = _issue(app, agreed)
        confirmation_id = str(confirmation.id)

        line = MasterAgreementPriceLine.query.filter_by(
            agreement_id=agreed['agreement_id'],
            product_name='Sofa góc').first()
        line.agreed_unit_price = 12_000_000
        db.session.commit()

        reread = OrderConfirmation.query.get(confirmation_id)
        assert float(reread.total_amount) == TOTAL
        prices = {item['name']: float(item['unit_price'])
                  for item in reread.items}
        assert prices['Sofa góc'] == SOFA_PRICE


def test_the_order_records_which_agreement_it_cited(app, agreed):
    with app.app_context():
        confirmation = _issue(app, agreed)
        assert confirmation.cited_agreement_number == 'HDNT-2026'


# --- the agreement must be in force -------------------------------------

def test_an_order_dated_before_the_agreement_is_refused(app, agreed):
    with app.app_context():
        with pytest.raises(ValueError):
            _issue(app, agreed, number='DDH-EARLY',
                   when=EFFECTIVE - dt.timedelta(days=1))


def test_a_suspended_agreement_cannot_take_new_orders(app, agreed):
    with app.app_context():
        AgreementService.suspend(_agreement(agreed['agreement_id']))
        with pytest.raises(ValueError):
            _issue(app, agreed, number='DDH-SUSPENDED')


def test_two_orders_cannot_share_a_number(app, agreed):
    with app.app_context():
        _issue(app, agreed, number='DDH-DUP')
        with pytest.raises(ValueError):
            _issue(app, agreed, number='DDH-DUP')


# --- it reaches the money reports ----------------------------------------

def test_a_confirmed_order_counts_as_booked_revenue(app, agreed):
    from app.models.models import OrderConfirmation
    from app.services.report_service import ReportService

    with app.app_context():
        confirmation = _issue(app, agreed)
        confirmation.status = OrderConfirmation.STATUS_CONFIRMED
        from app.config import db
        db.session.commit()

        result = ReportService().sales(agreed['company_id'])
        assert result['booked_value'] == TOTAL


def test_the_customer_owes_the_order_total(app, agreed):
    from app.config import db
    from app.models.models import OrderConfirmation
    from app.services.report_service import ReportService

    with app.app_context():
        confirmation = _issue(app, agreed)
        confirmation.status = OrderConfirmation.STATUS_CONFIRMED
        db.session.commit()

        rows = ReportService().customer_receivables(agreed['company_id'])
        assert rows[0]['outstanding'] == TOTAL


def test_a_draft_order_owes_nothing_yet(app, agreed):
    from app.services.report_service import ReportService

    with app.app_context():
        _issue(app, agreed)
        assert ReportService().sales(agreed['company_id'])['booked_value'] == 0
