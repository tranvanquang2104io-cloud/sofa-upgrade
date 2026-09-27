"""Who signed it, who confirmed the money, who cancelled it.

Before this, the answer was nobody knows. The whole schema carried three
`*_by_id` columns and two of them were on `ApprovalRequest`. No contract
recorded who signed it, no payment recorded who confirmed that the customer's
money had arrived, and no cancellation recorded who decided.

The owner asked for maker-checker. An approval with nobody's name against it
is not a control; it is a habit.

These tests go through the SERVICES, because that is where the recording
happens, and through a logged-in client where the point is that the right
person's name lands on the row.
"""
import datetime as dt

import pytest


@pytest.fixture()
def an_order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus, PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HIST',
                      title='Sofa goc L', total_amount=30_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True))
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-HIST', contract_date=dt.date(2026, 9, 1),
            contract_value=30_000_000, advance_percentage=50,
            is_signed=False, is_active=True)
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-HIST', report_date=dt.date(2026, 9, 2),
            payment_date=dt.date(2026, 9, 2), payment_type='advance',
            amount=15_000_000, is_confirmed=False)
        db.session.add_all([contract, payment])
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'contract_id': str(contract.id),
                'payment_id': str(payment.id)}


def test_signing_a_contract_records_who_signed_it(app, client, login,
                                                  an_order):
    """Through the route, so the name comes from a real logged-in session."""
    from app.services.transitions import history_for

    login('admin')
    client.post(f"/contracts/{an_order['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        events = history_for('contract', an_order['contract_id'])
        assert len(events) == 1, f'expected one event, got {events}'
        assert events[0].action == 'contract.sign'
        assert events[0].user_id is not None, (
            'the contract was signed by nobody; that is the whole problem '
            'this table exists to fix')
        assert events[0].to_state == 'signed'


def test_confirming_and_then_voiding_money_leaves_both_lines(app, client,
                                                             login, an_order):
    """The history is a story, not a current value.

    A `confirmed_by` column would hold the last thing that happened and lose
    the fact that it was confirmed and then given back. That sequence is
    exactly the one somebody asks about six months later.
    """
    from app.services.transitions import history_for

    login('admin')
    client.post(f"/payment/{an_order['payment_id']}/confirm",
                follow_redirects=True)
    client.post(f"/payment/{an_order['payment_id']}/cancel",
                data={'reason': 'Khach chuyen nham tai khoan'},
                follow_redirects=True)

    with app.app_context():
        events = history_for('payment', an_order['payment_id'])
        actions = [event.action for event in events]
        assert actions == ['payment.confirm', 'payment.cancel'], actions
        assert events[1].reason == 'Khach chuyen nham tai khoan', (
            'the reason the user typed was not kept; it is the single most '
            'useful column here')
        assert events[0].user_id is not None


def test_the_order_history_gathers_its_documents(app, client, login,
                                                 an_order):
    """A person looking at an order wants one story, not five."""
    from app.services.transitions import history_for_order

    login('admin')
    client.post(f"/contracts/{an_order['contract_id']}/sign",
                follow_redirects=True)
    client.post(f"/payment/{an_order['payment_id']}/confirm",
                follow_redirects=True)

    with app.app_context():
        events = history_for_order(an_order['order_id'])
        assert [event.action for event in events] == [
            'contract.sign', 'payment.confirm'], (
            'the order history did not gather its child documents in order')


def test_an_action_outside_a_request_records_no_user_rather_than_a_wrong_one(
        app, an_order):
    """A migration or a job acts for nobody.

    Recording whoever happens to be convenient would make every row suspect,
    including the true ones.
    """
    from app.services.services import ContractService
    from app.services.transitions import history_for

    with app.app_context():
        ContractService().mark_signed(an_order['contract_id'],
                                      an_order['order_id'])
        events = history_for('contract', an_order['contract_id'])
        assert events[0].user_id is None
        assert events[0].user_name is None


def test_a_broken_ledger_does_not_block_the_business(app, an_order,
                                                     monkeypatch):
    """The rule that matters most, and the one worth arguing about.

    A failure to write history is logged and swallowed. Refusing to confirm a
    customer's payment because an audit row would not insert is a worse
    outcome than a gap in the history: the gap is visible afterwards, a
    blocked payment at the counter is an emergency now. It also means this
    file cannot take the product down, which is more power than a ledger
    should have.
    """
    from app.models.models import PaymentReport
    import app.services.transitions as transitions

    def explode(*args, **kwargs):
        raise RuntimeError('the audit table is on fire')

    monkeypatch.setattr(transitions, '_who', explode)

    with app.app_context():
        from app.services.services import PaymentReportService

        PaymentReportService().mark_confirmed(an_order['payment_id'],
                                              an_order['order_id'])
        assert PaymentReport.query.get(
            an_order['payment_id']).is_confirmed is True, (
            'a failure in the audit trail stopped a customer payment being '
            'recorded')


def test_the_history_is_visible_on_the_order_screen(app, client, login,
                                                    an_order):
    """A ledger nobody can read answers no question.

    This repo has six instances of finished work that nothing reaches — a
    write-only stock movement table among them. An audit trail is exactly the
    kind of thing that quietly becomes the seventh, so the reachability is
    asserted rather than assumed.
    """
    login('admin')
    client.post(f"/payment/{an_order['payment_id']}/cancel",
                data={'reason': 'Ghi nham don hang'}, follow_redirects=True)

    body = client.get(f"/orders/{an_order['order_id']}").get_data(
        as_text=True)

    assert 'Ghi nham don hang' in body, (
        'the cancellation reason was recorded but cannot be seen anywhere; '
        'the history is write-only')
