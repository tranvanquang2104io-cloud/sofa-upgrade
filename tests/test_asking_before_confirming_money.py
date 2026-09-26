"""A clerk raises the request; the branch manager decides.

The owner: "Chỉ có người đứng cao nhất của 1 cửa hàng, chi nhánh mới có quyền
Approve, còn những người khác chỉ được raise cái lệnh xác nhận/hủy đó lên
thôi, còn người duyệt phải là admin của chi nhánh/store."

This is NOT the same as tightening a permission. A permission refuses and stops
the work: the clerk with cash in their hand and a manager who is out cannot
record anything, so they borrow the manager's password and the whole control
becomes theatre. A request records what they did, in their own name, and waits.
The work continues; only the decision moves.

Two things this must get right, and both are about not making it worse:

* **Nobody is blocked from starting.** A staff user asks, and their asking is
  itself a record — who, when, for how much, and why.
* **Approving is what performs the action.** If approval merely unlocked a
  button, the manager could approve and nothing would happen until somebody
  pressed it — two steps where the business has one, and a gap where the amount
  can change between the decision and the act.

A manager acting alone is not made to ask themselves. Forcing a store_admin
through a request they immediately approve is a ceremony with no second pair of
eyes in it, and people route around ceremonies.
"""
import datetime as dt

import pytest


@pytest.fixture()
def a_payment_to_confirm(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-APPR',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-APPR', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            amount=9_703_200, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'payment_id': str(payment.id)}


# --------------------------------------------------------------------------
# A manager acts. A clerk asks.
# --------------------------------------------------------------------------

def test_a_branch_manager_confirms_directly(app, a_payment_to_confirm):
    """No ceremony for somebody who would only be approving themselves."""
    from app.models.models import ApprovalRequest, PaymentReport
    from app.services.approvals import request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm',
            target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='store_admin', user_id=None, reason=None)

        assert outcome.performed is True
        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is True
        assert ApprovalRequest.query.count() == 0, (
            'a manager was made to file a request against themselves')


def test_a_clerk_raises_a_request_instead(app, a_payment_to_confirm):
    from app.models.models import ApprovalRequest, PaymentReport
    from app.services.approvals import request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm',
            target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='user', user_id=None,
            reason='Khách chuyển khoản sáng nay')

        assert outcome.performed is False
        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is False, (
            'the money was confirmed without a decision')

        pending = ApprovalRequest.query.one()
        assert pending.action == 'payment.confirm'
        assert pending.status == ApprovalRequest.STATUS_PENDING
        assert pending.reason == 'Khách chuyển khoản sáng nay'


def test_the_clerk_is_not_blocked_from_working(app, a_payment_to_confirm):
    """The point of a request rather than a refusal.

    A refusal leaves somebody holding cash with nothing they can record, and
    the workaround for that is borrowing the manager's password.
    """
    from app.services.approvals import request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm', target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='user', user_id=None, reason=None)
        assert outcome.request is not None
        assert outcome.message, (
            'the clerk is told nothing about what happens next')


# --------------------------------------------------------------------------
# Approving is what performs the action.
# --------------------------------------------------------------------------

def test_approving_performs_the_action(app, a_payment_to_confirm):
    from app.models.models import ApprovalRequest, PaymentReport
    from app.services.approvals import approve, request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm', target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='user', user_id=None, reason=None)

        approve(outcome.request, user_id=None)

        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is True, (
            'approval unlocked a button instead of doing the thing, so the '
            'decision and the act can drift apart')
        assert ApprovalRequest.query.one().status == \
            ApprovalRequest.STATUS_APPROVED


def test_rejecting_records_why_and_changes_nothing(app, a_payment_to_confirm):
    from app.models.models import ApprovalRequest, PaymentReport
    from app.services.approvals import reject, request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm', target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='user', user_id=None, reason=None)

        reject(outcome.request, user_id=None, note='Chưa thấy tiền về')

        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is False
        rejected = ApprovalRequest.query.one()
        assert rejected.status == ApprovalRequest.STATUS_REJECTED
        assert rejected.decision_note == 'Chưa thấy tiền về'


def test_a_decided_request_cannot_be_decided_again(app, a_payment_to_confirm):
    """Otherwise approving twice would confirm twice, or reverse a refusal."""
    from app.services.approvals import approve, request_or_do

    with app.app_context():
        outcome = request_or_do(
            company_id=a_payment_to_confirm['company_id'],
            action='payment.confirm', target_type='payment_report',
            target_id=a_payment_to_confirm['payment_id'],
            user_role='user', user_id=None, reason=None)
        approve(outcome.request, user_id=None)

        with pytest.raises(ValueError):
            approve(outcome.request, user_id=None)


def test_an_unknown_action_is_refused_rather_than_queued(app,
                                                         a_payment_to_confirm):
    """A request nothing knows how to perform would sit forever.

    A manager would approve it, nothing would happen, and the queue would teach
    people that approving does not mean anything.
    """
    from app.services.approvals import request_or_do

    with app.app_context():
        with pytest.raises(ValueError):
            request_or_do(
                company_id=a_payment_to_confirm['company_id'],
                action='payment.teleport', target_type='payment_report',
                target_id=a_payment_to_confirm['payment_id'],
                user_role='user', user_id=None, reason=None)


# --------------------------------------------------------------------------
# Through the screens, because a queue nobody can reach is a queue that only
# delays work.
# --------------------------------------------------------------------------

def test_a_staff_user_confirming_raises_a_request(app, client, login, seed,
                                                  a_payment_to_confirm):
    from app.config import db
    from app.models import User
    from app.models.models import ApprovalRequest, PaymentReport

    with app.app_context():
        # The seeded staff user needs the feature grant, or the 403 would come
        # from the permission area and this test would pass for the wrong
        # reason — exactly the trap the store-isolation tests fell into.
        # `allowed_features`, not `features`. Guessing the attribute name
        # silently does nothing — the user keeps no grants, the route returns
        # 403, and the test fails for a reason that has nothing to do with
        # approvals.
        staff = User.query.filter_by(username='staff').first()
        staff.allowed_features = ['orders']
        db.session.commit()

    login('staff')
    client.post(f"/payment/{a_payment_to_confirm['payment_id']}/confirm",
                data={'reason': 'Khách chuyển khoản sáng nay'},
                follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is False, (
            'a staff user confirmed money with no decision')
        assert ApprovalRequest.query.count() == 1


def test_the_manager_sees_it_and_approving_confirms_the_money(
        app, client, login, seed, a_payment_to_confirm):
    from app.config import db
    from app.models import User
    from app.models.models import ApprovalRequest, PaymentReport

    with app.app_context():
        # `allowed_features`, not `features`. Guessing the attribute name
        # silently does nothing — the user keeps no grants, the route returns
        # 403, and the test fails for a reason that has nothing to do with
        # approvals.
        staff = User.query.filter_by(username='staff').first()
        staff.allowed_features = ['orders']
        db.session.commit()

    login('staff')
    client.post(f"/payment/{a_payment_to_confirm['payment_id']}/confirm",
                data={'reason': 'Khách chuyển khoản'}, follow_redirects=True)
    client.get('/auth/logout', follow_redirects=True)

    login('admin')
    body = client.get('/approvals').get_data(as_text=True)
    assert 'Khách chuyển khoản' in body, (
        'the request is queued and the manager cannot see what it is for')

    with app.app_context():
        request_id = str(ApprovalRequest.query.one().id)

    client.post(f'/approvals/{request_id}/approve', follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is True, (
            'the manager approved and the money was not confirmed')


def test_a_manager_confirming_does_not_queue_anything(app, client, login,
                                                      a_payment_to_confirm):
    from app.models.models import ApprovalRequest, PaymentReport

    login('admin')
    client.post(f"/payment/{a_payment_to_confirm['payment_id']}/confirm",
                follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(
            a_payment_to_confirm['payment_id']).is_confirmed is True
        assert ApprovalRequest.query.count() == 0, (
            'a manager was made to file a request against themselves')
