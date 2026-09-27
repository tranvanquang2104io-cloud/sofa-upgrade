"""An approval queue that shows every branch is not the rule the owner asked for.

The owner's rule: *"nguoi duyet phai la admin cua chi nhanh/store"* -- the
person who decides is the manager OF THAT BRANCH. `ApprovalRequest` carries a
`company_id` and nothing else, and `pending_for(company_id)` returns the whole
company, so the manager of branch A sees and can approve branch B's requests.

That is not a small leak. The request is the thing a manager reads before
releasing money, and `approve()` PERFORMS the action -- so approving is the
act, not a permission to act later. A manager approving work from a branch they
have never visited is approving something they cannot check.

T-01 closed the other half of this: a clerk can no longer raise a request
against another branch's payment in the first place. That makes the queue leak
unreachable through the UI TODAY, and a rule that happens to be unreachable is
exactly the kind this repo has been bitten by twice already -- `mark_confirmed`
and the closed-books guard were both "enforced" only where nothing could reach
them. So this is tested at the queue directly.

Self-approval is the same shape. It is not reachable now, because a
`store_admin` who asks never creates a row at all: `request_or_do` performs the
action immediately for a deciding role. It becomes reachable the moment
somebody's role changes between the asking and the deciding, or the day
`DECIDING_ROLES` is widened. Closed as a trap, and the test says so rather than
claiming to have found a live hole.
"""
import datetime as dt

import pytest


@pytest.fixture()
def two_branches_with_requests(app, seed):
    """One pending request in the user's own branch, one in another branch."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        ApprovalRequest, PaymentReport, Store, User,
    )

    with app.app_context():
        far = Store(company_id=seed['company_id'], store_code='CH-FAR',
                    name='Chi nhanh Da Nang', is_active=True)
        db.session.add(far)
        db.session.flush()

        rows = {}
        for key, store_id, code in (('mine', seed['store_id'], 'DH-Q-MINE'),
                                    ('far', far.id, 'DH-Q-FAR')):
            order = Order(company_id=seed['company_id'], store_id=store_id,
                          customer_id=seed['customer_id'], order_code=code,
                          title='Sofa goc L', total_amount=10_000_000)
            db.session.add(order)
            db.session.flush()
            payment = PaymentReport(
                company_id=seed['company_id'], order_id=order.id,
                report_number=f'TT-{key.upper()}',
                report_date=dt.date(2026, 9, 1),
                payment_date=dt.date(2026, 9, 1), payment_type='advance',
                amount=5_000_000, is_confirmed=False)
            db.session.add(payment)
            db.session.flush()

            clerk = User.query.filter_by(username='staff').first()
            request_row = ApprovalRequest(
                company_id=seed['company_id'], action='payment.confirm',
                target_type='payment', target_id=payment.id,
                reason='Khach da chuyen khoan',
                requested_by_id=clerk.id,
                # Stamped, as `request_or_do` stamps it. A fixture that
                # leaves it NULL would be modelling a row from before the
                # column existed, which is a different case -- covered by
                # test_an_untraceable_old_request_stays_with_the_company_admin.
                store_id=store_id,
                status=ApprovalRequest.STATUS_PENDING)
            db.session.add(request_row)
            db.session.flush()
            rows[key] = {'request_id': str(request_row.id),
                         'payment_id': str(payment.id),
                         'order_id': str(order.id)}
        db.session.commit()

        flat = {f'{key}_{field.split("_")[0]}': value
                for key, row in rows.items()
                for field, value in row.items()}
        return {**seed, 'far_store_id': str(far.id), **flat}


@pytest.fixture()
def branch_manager(app, seed):
    """A store_admin belonging to the SEEDED branch, not the far one."""
    from app.config import db
    from app.models.models import User

    with app.app_context():
        manager = User(company_id=seed['company_id'],
                       store_id=seed['store_id'],
                       username='qlcn', email='qlcn@acme.test',
                       full_name='Quan ly chi nhanh',
                       role=User.ROLE_STORE_ADMIN, is_active=True,
                       allowed_features=['orders', 'payments', 'approvals'])
        manager.set_password('secret123')
        db.session.add(manager)
        db.session.commit()
    return seed


def test_the_queue_shows_only_this_managers_branch(
        app, two_branches_with_requests, branch_manager):
    """`pending_for` is what the screen renders; it must narrow to the branch."""
    from app.services.approvals import pending_for

    with app.app_context():
        from app.models.models import User
        manager = User.query.filter_by(username='qlcn').first()
        pending = pending_for(two_branches_with_requests['company_id'],
                              store_ids=[manager.store_id])

        ids = {str(row.id) for row in pending}
        assert two_branches_with_requests['mine_request'] in ids, (
            'the manager cannot see their own branch queue')
        assert two_branches_with_requests['far_request'] not in ids, (
            'the manager of one branch sees another branch pending money')


def test_a_company_admin_still_sees_every_branch(
        app, two_branches_with_requests):
    """Narrowing the queue must not blind the person above the branches."""
    from app.services.approvals import pending_for

    with app.app_context():
        ids = {str(row.id) for row in
               pending_for(two_branches_with_requests['company_id'])}
        assert two_branches_with_requests['mine_request'] in ids
        assert two_branches_with_requests['far_request'] in ids


def test_a_branch_manager_cannot_approve_another_branchs_request(
        app, client, login, two_branches_with_requests, branch_manager):
    """The sharp end: approving PERFORMS the confirmation, then and there.

    This one was GREEN before T-02 was written, and the reason is worth
    keeping: T-01 closed it by accident. `_confirm_payment` re-fetches the
    payment through `PaymentReportService`, which goes through the now-scoped
    repository, so the far branch payment reads as absent and the manager gets
    "Payment report ... not found".

    The money was therefore already safe, and this test does not claim
    otherwise. What it holds is that it STAYS safe -- the protection currently
    rests on one service happening to re-fetch through a repository, and a
    performer added tomorrow that acts on the row it was handed would not have
    it. The queue filtering below is the fix that does not depend on that.
    """
    from app.models.models import ApprovalRequest, PaymentReport

    login('qlcn')
    client.post(
        f"/approvals/{two_branches_with_requests['far_request']}/approve",
        follow_redirects=True)

    with app.app_context():
        payment = PaymentReport.query.get(
            two_branches_with_requests['far_payment'])
        assert payment.is_confirmed is False, (
            'a manager confirmed money for a branch they do not run')
        row = ApprovalRequest.query.get(
            two_branches_with_requests['far_request'])
        assert row.status == ApprovalRequest.STATUS_PENDING


def test_a_branch_manager_can_still_approve_their_own_branchs_request(
        app, client, login, two_branches_with_requests, branch_manager):
    """The ordinary case. A scope fix that stops the work is not a fix."""
    from app.models.models import ApprovalRequest, PaymentReport

    login('qlcn')
    client.post(
        f"/approvals/{two_branches_with_requests['mine_request']}/approve",
        follow_redirects=True)

    with app.app_context():
        payment = PaymentReport.query.get(
            two_branches_with_requests['mine_payment'])
        assert payment.is_confirmed is True, (
            'the branch manager was refused their own branch request')
        row = ApprovalRequest.query.get(
            two_branches_with_requests['mine_request'])
        assert row.status == ApprovalRequest.STATUS_APPROVED


def test_nobody_approves_their_own_request(app, two_branches_with_requests):
    """A trap, not a live hole -- see the module docstring.

    Whoever asked cannot be whoever decides, whatever role they hold by the
    time the decision is made. Two pairs of eyes or none; a queue where the
    asker signs their own request records a review that did not happen.
    """
    from app.models.models import ApprovalRequest
    from app.services.approvals import approve

    with app.app_context():
        row = ApprovalRequest.query.get(
            two_branches_with_requests['mine_request'])
        with pytest.raises(ValueError):
            approve(row, user_id=row.requested_by_id)

        assert ApprovalRequest.query.get(
            two_branches_with_requests['mine_request']
        ).status == ApprovalRequest.STATUS_PENDING


def test_a_request_records_the_branch_it_came_from(app, client, login, seed):
    """The column has to be filled at the moment the request is made.

    Backfilling it later from the document means re-deriving it, and the
    document can move: a stamped branch is what the queue is filtered on.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import ApprovalRequest, PaymentReport, User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['orders', 'payments']
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-STAMP',
                      title='Sofa bang', total_amount=8_000_000)
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-STAMP', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            amount=4_000_000, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()
        payment_id = str(payment.id)

    login('staff')
    client.post(f'/payment/{payment_id}/confirm', follow_redirects=True)

    with app.app_context():
        row = ApprovalRequest.query.filter_by(target_id=payment_id).first()
        assert row is not None, 'no request was filed'
        assert str(row.store_id) == str(seed['store_id']), (
            'the request does not say which branch it came from, so the queue '
            'cannot be filtered on it')



def test_an_untraceable_old_request_stays_with_the_company_admin(
        app, two_branches_with_requests, branch_manager):
    """A row raised before the column existed, whose document has since gone.

    The migration backfills `store_id` from the target payment's order. A row
    whose payment was deleted has nowhere to get it from and keeps NULL. It
    must not vanish from every queue: it goes to the person above the
    branches, who is the right fallback reader.
    """
    from app.config import db
    from app.models.models import ApprovalRequest, User

    with app.app_context():
        clerk = User.query.filter_by(username='staff').first()
        orphan = ApprovalRequest(
            company_id=two_branches_with_requests['company_id'],
            action='payment.confirm', target_type='payment',
            target_id=clerk.id,  # a target that is not a payment any more
            reason='Chung tu cu', requested_by_id=clerk.id, store_id=None,
            status=ApprovalRequest.STATUS_PENDING)
        db.session.add(orphan)
        db.session.commit()
        orphan_id = str(orphan.id)

        manager = User.query.filter_by(username='qlcn').first()
        from app.services.approvals import pending_for

        branch_view = {str(r.id) for r in pending_for(
            two_branches_with_requests['company_id'],
            store_ids=[manager.store_id])}
        company_view = {str(r.id) for r in pending_for(
            two_branches_with_requests['company_id'])}

        assert orphan_id not in branch_view, (
            'a request that cannot be attributed to a branch turned up in a '
            'branch queue anyway')
        assert orphan_id in company_view, (
            'an untraceable request fell out of every queue, so nobody is '
            'ever asked to decide it')
