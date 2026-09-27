"""When something is undone, do the numbers come back?

The five chains were validated going forwards. This asks the other question: a
quotation withdrawn, a contract cancelled, a payment voided, an order called
off — does the money stop being counted, and does the lifecycle stop claiming a
step that no longer happened?

This is where a reporting bug is most likely to hide, because cancelling is
rare enough that nobody notices the total staying high, and the figure that
stays behind is the one the business chases the customer for.

Numbers reused from the O2C walk: contract 32,344,000, advance 9,703,200.
"""
import datetime as dt

import pytest

CONTRACT_VALUE = 32_344_000
ADVANCE = 9_703_200
REMAINING = CONTRACT_VALUE - ADVANCE


@pytest.fixture()
def paid_order(app, seed):
    """A signed contract with its advance received and confirmed."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus, PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HUY',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, quotation_created=True, quotation_approved=True,
            contract_created=True, contract_signed=True, advance_paid=True))
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-HUY', contract_date=dt.date(2026, 1, 1),
            contract_value=CONTRACT_VALUE, advance_percentage=30,
            advance_amount=ADVANCE, is_signed=True)
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TU-HUY', report_date=dt.date(2026, 1, 5),
            payment_date=dt.date(2026, 1, 5), payment_type='advance',
            amount=ADVANCE, advance_amount=ADVANCE, is_confirmed=True)
        db.session.add_all([contract, payment])
        db.session.commit()
        return {'order_id': str(order.id), 'contract_id': str(contract.id),
                'payment_id': str(payment.id), **seed}


def _accounting(company_id):
    from app.services.report_service import ReportService
    return ReportService().accounting(company_id)


def _receivables(company_id):
    from app.services.report_service import ReportService
    return ReportService().customer_receivables(company_id)


# --- the starting position ------------------------------------------------

def test_the_order_starts_owing_the_balance(app, paid_order):
    with app.app_context():
        assert _accounting(paid_order['company_id'])['receivable'] == REMAINING


# --- cancelling the order -------------------------------------------------

def test_a_cancelled_order_is_no_longer_booked_revenue(app, client, login,
                                                        paid_order):
    from app.services.report_service import ReportService

    login("admin")
    client.post(f"/orders/{paid_order['order_id']}/cancel",
                data={'canceled_reason': 'Khách đổi ý'}, follow_redirects=True)

    with app.app_context():
        result = ReportService().sales(paid_order['company_id'])
        assert result['booked_value'] == 0, (
            "a cancelled order must stop counting as revenue"
        )


def test_a_cancelled_order_is_no_longer_chased_for_money(app, client, login,
                                                          paid_order):
    """The figure that would otherwise be dunned out of a former customer."""
    login("admin")
    client.post(f"/orders/{paid_order['order_id']}/cancel",
                data={'canceled_reason': 'Khách đổi ý'}, follow_redirects=True)

    with app.app_context():
        assert _accounting(paid_order['company_id'])['receivable'] == 0

        rows = _receivables(paid_order['company_id'])
        assert all(row['outstanding'] == 0 for row in rows)


def test_cancelling_records_why(app, client, login, paid_order):
    from app.models import Order

    login("admin")
    client.post(f"/orders/{paid_order['order_id']}/cancel",
                data={'canceled_reason': 'Khách đổi ý'}, follow_redirects=True)

    with app.app_context():
        order = Order.query.get(paid_order['order_id'])
        assert order.is_canceled is True
        assert order.canceled_reason == 'Khách đổi ý'


# --- cancelling a payment -------------------------------------------------

def test_voiding_the_advance_puts_the_money_back_on_the_bill(app, paid_order):
    """A payment that did not happen must stop reducing what is owed."""
    from app.config import db
    from app.models.models import PaymentReport

    with app.app_context():
        payment = PaymentReport.query.get(paid_order['payment_id'])
        payment.is_canceled = True
        db.session.commit()

        assert _accounting(
            paid_order['company_id'])['receivable'] == CONTRACT_VALUE


def test_a_confirmed_payment_can_now_be_voided_with_a_reason(app, paid_order):
    """This pinned the opposite, and the owner changed the answer.

    It used to record that a mistaken confirmation was permanent:
    `can_cancel()` and `can_edit()` both required `not is_confirmed`, and no
    unconfirm route existed anywhere. That was pinned as CURRENT behaviour and
    written up as an owner decision (§3.2), because how an accounting mistake
    gets corrected is a business policy and not something to invent.

    The owner decided: *"hủy có lý do rồi tạo lại, chứng từ hủy muốn hủy thì
    phải được duyệt và hủy xong thì các data liên quan cũng phải được update
    lại."*

    So `can_cancel()` now allows it — with a mandatory reason, through the
    approval queue, and with everything the confirmation touched recomputed.
    `can_edit()` is deliberately NOT relaxed: void and re-create, never rewrite
    (Luật Kế toán 2015 Đ.27).

    This test failing when §3.2 landed is the test doing its job: it was
    holding a decision, and the decision changed.
    """
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        payment = PaymentReport.query.get(paid_order['payment_id'])
        assert payment.can_cancel() is True
        assert payment.can_edit() is False, (
            'a confirmed payment became editable; the rule is void and '
            're-create, never rewrite')

        with pytest.raises(ValueError):
            PaymentReportService().cancel_payment(paid_order['payment_id'],
                                                  paid_order['order_id'],
                                                  reason='')

        PaymentReportService().cancel_payment(paid_order['payment_id'],
                                              paid_order['order_id'],
                                              reason='Nhầm chứng từ')
        assert PaymentReport.query.get(
            paid_order['payment_id']).is_canceled is True


def test_an_unconfirmed_payment_can_still_be_voided(app, paid_order):
    """The correction path exists right up until the moment of confirming."""
    from app.config import db
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=paid_order['company_id'],
            order_id=paid_order['order_id'], report_number='TU-NHAP',
            report_date=dt.date(2026, 1, 7), payment_date=dt.date(2026, 1, 7),
            payment_type='advance', amount=500_000, advance_amount=500_000,
            is_confirmed=False))
        db.session.commit()
        draft = PaymentReport.query.filter_by(report_number='TU-NHAP').first()

        PaymentReportService().cancel_payment(str(draft.id),
                                              paid_order['order_id'],
                                              reason='Nhập nhầm')

        assert PaymentReport.query.filter_by(
            report_number='TU-NHAP').first().is_canceled is True


# --- cancelling a quotation ----------------------------------------------

def test_a_cancelled_quotation_is_not_an_approved_one(app, seed):
    from app.config import db
    from app.models import Order, Quotation
    from app.models.models import LifecycleStatus
    from app.services.services import QuotationService

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-BG-HUY',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True))
        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-HUY', quotation_date=dt.date(2026, 1, 1),
            total_amount=5_000_000)
        db.session.add(quotation)
        db.session.commit()

        QuotationService().cancel_quotation(str(quotation.id), reason='Sai giá')

        assert Quotation.query.get(quotation.id).is_canceled is True
        assert Quotation.query.get(quotation.id).is_approved is False


# --- the guard that exists on purpose ------------------------------------

def test_a_signed_contract_refuses_to_be_cancelled(app, paid_order):
    """Documented as an open decision in REVIEW-2026Q3.md §3.1.

    Pinned here so the current behaviour is unambiguous while the owner
    decides: today a signed contract cannot be cancelled at all.
    """
    from app.services.services import ContractService

    with app.app_context():
        with pytest.raises(ValueError):
            ContractService().cancel_contract(paid_order['contract_id'],
                                              paid_order['order_id'],
                                              reason='Khách huỷ')
