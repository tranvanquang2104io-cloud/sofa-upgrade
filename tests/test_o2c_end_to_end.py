"""Order-to-cash, correct to the đồng at every step.

One order walked the whole way — quotation, contract, advance, handover, final
payment — with every figure asserted against hand-computed values rather than
against whatever the code happens to produce.

The numbers, fixed once here so a drift anywhere shows up as a failure:

    2 sofas x 12,500,000            = 25,000,000
    1 armchair x 4,300,000          =  4,300,000
                                      ----------
                                      29,300,000   subtotal
    VAT 8%                          =  2,344,000
    shipping (not taxed)            =    500,000
    other fee (not taxed)           =    200,000
                                      ----------
                                      32,344,000   contract value
    advance 30%                     =  9,703,200
    remaining                       = 22,640,800

VAT applies to the goods only; the two fees are added after tax. If that ever
changes, the contract value moves by 56,000 đồng on this order alone.
"""
import datetime as dt

import pytest

from app.services.money import compute_totals

SOFA_QTY, SOFA_PRICE = 2, 12_500_000
CHAIR_QTY, CHAIR_PRICE = 1, 4_300_000
SUBTOTAL = SOFA_QTY * SOFA_PRICE + CHAIR_QTY * CHAIR_PRICE   # 29,300,000
VAT_RATE = 8
VAT_AMOUNT = 2_344_000
SHIPPING = 500_000
OTHER = 200_000
TOTAL = 32_344_000
ADVANCE_PCT = 30
ADVANCE = 9_703_200
REMAINING = TOTAL - ADVANCE                                   # 22,640,800

ITEMS = [
    {'name': 'Sofa góc da bò thật', 'unit': 'bộ', 'quantity': SOFA_QTY,
     'unit_price': SOFA_PRICE, 'total': SOFA_QTY * SOFA_PRICE},
    {'name': 'Ghế thư giãn', 'unit': 'chiếc', 'quantity': CHAIR_QTY,
     'unit_price': CHAIR_PRICE, 'total': CHAIR_QTY * CHAIR_PRICE},
]


# --- the arithmetic itself ------------------------------------------------

def test_the_totals_match_hand_calculation():
    totals = compute_totals(subtotal=SUBTOTAL, vat_rate=VAT_RATE,
                            shipping_fee=SHIPPING, another_fee=OTHER)
    assert totals['subtotal'] == SUBTOTAL
    assert totals['vat_amount'] == VAT_AMOUNT
    assert totals['total_amount'] == TOTAL


def test_vat_is_not_charged_on_the_fees():
    """Taxing the fees too would add 56,000 to this one order."""
    taxed_everything = (SUBTOTAL + SHIPPING + OTHER) * VAT_RATE / 100
    assert taxed_everything - VAT_AMOUNT == 56_000

    totals = compute_totals(subtotal=SUBTOTAL, vat_rate=VAT_RATE,
                            shipping_fee=SHIPPING, another_fee=OTHER)
    assert totals['vat_amount'] == VAT_AMOUNT


def test_the_advance_is_a_percentage_of_the_whole_contract_value():
    assert round(TOTAL * ADVANCE_PCT / 100, 2) == ADVANCE


# --- the order walked end to end -----------------------------------------

@pytest.fixture()
def o2c(app, seed):
    """Approved quotation and a signed contract carrying the numbers above."""
    from app.config import db
    from app.models import Order, Quotation
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-O2C',
                      title='Bộ sofa phòng khách')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       quotation_approved=True,
                                       contract_created=True,
                                       contract_signed=True))
        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-O2C', quotation_date=dt.date(2026, 1, 5),
            items=ITEMS, subtotal=SUBTOTAL, vat_rate=VAT_RATE,
            vat_amount=VAT_AMOUNT, shipping_fee=SHIPPING, another_fee=OTHER,
            total_amount=TOTAL, is_approved=True)
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-O2C', contract_date=dt.date(2026, 1, 10),
            items=ITEMS, subtotal=SUBTOTAL, vat_rate=VAT_RATE,
            vat_amount=VAT_AMOUNT, shipping_fee=SHIPPING, another_fee=OTHER,
            contract_value=TOTAL, advance_percentage=ADVANCE_PCT,
            advance_amount=ADVANCE, is_signed=True)
        db.session.add_all([quotation, contract])
        db.session.commit()
        return {'order_id': str(order.id), 'contract_id': str(contract.id),
                **seed}


def test_the_contract_carries_the_same_total_as_the_quotation(app, o2c):
    from app.models import Quotation
    from app.models.models import Contract

    with app.app_context():
        quotation = Quotation.query.filter_by(quotation_number='BG-O2C').first()
        contract = Contract.query.get(o2c['contract_id'])
        assert float(quotation.total_amount) == float(contract.contract_value)
        assert float(contract.contract_value) == TOTAL


def test_booked_revenue_is_the_contract_value(app, o2c):
    from app.services.report_service import ReportService

    with app.app_context():
        assert ReportService().sales(o2c['company_id'])['booked_value'] == TOTAL


def test_the_whole_value_is_receivable_before_any_payment(app, o2c):
    from app.services.report_service import ReportService

    with app.app_context():
        assert ReportService().accounting(
            o2c['company_id'])['receivable'] == TOTAL


@pytest.fixture()
def after_advance(app, o2c):
    from app.config import db
    from app.models.models import LifecycleStatus, PaymentReport

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=o2c['company_id'], order_id=o2c['order_id'],
            report_number='TU-O2C', report_date=dt.date(2026, 1, 12),
            payment_date=dt.date(2026, 1, 12), payment_type='advance',
            amount=ADVANCE, advance_amount=ADVANCE, is_confirmed=True))
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=o2c['order_id']).first()
        lifecycle.advance_paid = True
        db.session.commit()
        return o2c


def test_the_advance_reduces_the_receivable_by_exactly_its_amount(
        app, after_advance):
    from app.services.report_service import ReportService

    with app.app_context():
        assert ReportService().accounting(
            after_advance['company_id'])['receivable'] == REMAINING


def test_the_customer_balance_shows_the_remainder(app, after_advance):
    from app.services.report_service import ReportService

    with app.app_context():
        rows = ReportService().customer_receivables(after_advance['company_id'])
        assert rows[0]['booked'] == TOTAL
        assert rows[0]['collected'] == ADVANCE
        assert rows[0]['outstanding'] == REMAINING


def test_paying_the_remainder_settles_the_order(app, after_advance):
    from app.config import db
    from app.models.models import PaymentReport
    from app.services.report_service import ReportService

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=after_advance['company_id'],
            order_id=after_advance['order_id'], report_number='TT-O2C',
            report_date=dt.date(2026, 2, 1), payment_date=dt.date(2026, 2, 1),
            payment_type='final', amount=REMAINING, is_confirmed=True))
        db.session.commit()

        rows = ReportService().customer_receivables(after_advance['company_id'])
        assert rows[0]['outstanding'] == 0
        assert rows[0]['settled'] is True
        assert ReportService().accounting(
            after_advance['company_id'])['receivable'] == 0


def test_an_unconfirmed_payment_changes_no_figure(app, after_advance):
    """Money promised is not money received."""
    from app.config import db
    from app.models.models import PaymentReport
    from app.services.report_service import ReportService

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=after_advance['company_id'],
            order_id=after_advance['order_id'], report_number='TT-CHUA',
            report_date=dt.date(2026, 2, 1), payment_date=dt.date(2026, 2, 1),
            payment_type='final', amount=REMAINING, is_confirmed=False))
        db.session.commit()

        assert ReportService().accounting(
            after_advance['company_id'])['receivable'] == REMAINING
