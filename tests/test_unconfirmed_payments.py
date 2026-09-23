"""Money recorded but not confirmed must be visible somewhere.

Every figure in the product counts a payment only once `is_confirmed` is set —
correctly, because an unconfirmed payment is a claim, not cash. But nothing
listed the claims. So a payment slip recorded on Friday and never confirmed
makes the customer look like a debtor for as long as nobody happens to open
that order, and the person chasing the debt has no way to find out that the
answer is "it is sitting in the queue".

The queue belongs on the receivables screen rather than on one of its own:
that is where somebody asks "why does this customer still owe us?", and it is
the answer to that question. A separate screen would be one more place to
remember to visit.
"""
import datetime as dt

import pytest


@pytest.fixture()
def customer_owing_with_a_pending_payment(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus, PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PEND',
                      title='Sofa băng 3 chỗ')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-PEND', contract_date=dt.date(2026, 9, 1),
            contract_value=30_000_000, advance_percentage=0, is_signed=True))

        # Recorded on Friday, never confirmed. Counts nowhere.
        db.session.add(PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-PENDING', payment_type='final',
            report_date=dt.date(2026, 9, 20), payment_date=dt.date(2026, 9, 20),
            amount=30_000_000, is_confirmed=False))

        # And one that was confirmed, which must NOT appear in the queue.
        db.session.add(PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-DONE', payment_type='advance',
            report_date=dt.date(2026, 9, 2), payment_date=dt.date(2026, 9, 2),
            amount=5_000_000, advance_amount=5_000_000,
            is_confirmed=True, confirmed_date=dt.date(2026, 9, 2)))
        db.session.commit()
        return seed


def test_the_service_lists_payments_awaiting_confirmation(
        app, customer_owing_with_a_pending_payment):
    from app.services.report_service import ReportService

    with app.app_context():
        pending = ReportService().unconfirmed_payments(
            customer_owing_with_a_pending_payment['company_id'])

    numbers = [row['report_number'] for row in pending]
    assert 'TT-PENDING' in numbers
    assert 'TT-DONE' not in numbers, 'a confirmed payment is not in the queue'


def test_it_carries_what_is_needed_to_act_on_it(
        app, customer_owing_with_a_pending_payment):
    """A number alone means opening every order to find out whose it is."""
    from app.services.report_service import ReportService

    with app.app_context():
        pending = ReportService().unconfirmed_payments(
            customer_owing_with_a_pending_payment['company_id'])

    row = next(r for r in pending if r['report_number'] == 'TT-PENDING')
    assert row['amount'] == 30_000_000
    assert row['customer_name']
    assert row['order_code'] == 'DH-PEND'
    assert row['payment_id']


def test_a_canceled_payment_is_not_waiting_for_anything(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport
    from app.services.report_service import ReportService

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-CANC',
                      title='Sofa góc')
        db.session.add(order)
        db.session.flush()
        db.session.add(PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-CANCELED', payment_type='final',
            report_date=dt.date(2026, 9, 3), payment_date=dt.date(2026, 9, 3),
            amount=1_000_000, is_confirmed=False, is_canceled=True))
        db.session.commit()

        pending = ReportService().unconfirmed_payments(seed['company_id'])

    assert [r['report_number'] for r in pending] == []


def test_the_queue_appears_on_the_receivables_screen(
        client, login, customer_owing_with_a_pending_payment):
    """Where the question "why does this customer still owe?" is asked."""
    login('admin')
    body = client.get('/reports/receivables').get_data(as_text=True)
    assert 'TT-PENDING' in body, (
        'the receivables screen does not show what is waiting to be confirmed')


def test_the_screen_does_not_show_the_queue_when_it_is_empty(client, login,
                                                             seed):
    """An empty panel on every screen is clutter, not information."""
    login('admin')
    body = client.get('/reports/receivables').get_data(as_text=True)
    assert 'Chờ xác nhận' not in body
