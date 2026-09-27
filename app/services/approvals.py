"""Who may decide, and what happens to everybody else's work in the meantime.

The owner's rule: only the person at the top of a branch approves confirming or
cancelling money. Everybody else raises the request.

The shape matters more than the rule. A permission that simply refuses stops
the work — a clerk holding cash and a manager who is out have nothing they can
record, and the way round that is borrowing the manager's password, at which
point the control is theatre and the audit trail is a lie. A request lets the
work continue in the clerk's own name and moves only the decision.

Approving PERFORMS the action, here, once. Unlocking a button instead would
make two steps out of one and leave a gap in which the amount can change
between the decision and the act.
"""
from collections import namedtuple

from app.config import db

#: What a caller gets back: whether the thing was done, the request if one was
#: raised, and a sentence to show the user. Callers should not have to work out
#: which of the two happened from the shape of the return value.
Outcome = namedtuple('Outcome', 'performed request message')


def _payment_of(request_row):
    """The payment this request is about, through the REPOSITORY.

    Not `PaymentReport.query.get()`. The repository applies the branch check
    (`app/utils/scope.py`), and the queue is a second door into exactly the
    same record — a door that used to bypass it. That it was not exploitable
    is not a reason to leave it: the protection rested on `mark_confirmed`
    happening to re-fetch through the repository, and the next performer
    written might act on the row it was handed.
    """
    from app.repositories.repository import PaymentReportRepository

    return PaymentReportRepository().get_by_id(request_row.target_id)


def _confirm_payment(request_row):
    from app.services.services import PaymentReportService

    payment = _payment_of(request_row)
    if payment is None:
        raise ValueError('Không tìm thấy phiếu thanh toán')
    PaymentReportService().mark_confirmed(payment.id, payment.order_id)


def _cancel_payment(request_row):
    from app.services.services import PaymentReportService

    payment = _payment_of(request_row)
    if payment is None:
        raise ValueError('Không tìm thấy phiếu thanh toán')
    PaymentReportService().cancel_payment(
        payment.id, payment.order_id, reason=request_row.reason or '')


#: Only these can be requested. An action nothing knows how to perform would be
#: approved, do nothing, and teach people that approving means nothing.
PERFORMERS = {
    'payment.confirm': _confirm_payment,
    'payment.cancel': _cancel_payment,
}

#: Roles that decide rather than ask. A manager is not made to file a request
#: against themselves: a ceremony with no second pair of eyes in it is one
#: people route around, and it buries the real requests in noise.
DECIDING_ROLES = ('company_admin', 'store_admin')


def _branch_of(action, target_id):
    """Which branch a request is about, read from the document itself.

    From the document rather than from the asker's own store, because those
    can differ — a company admin raising a request on a branch's behalf would
    otherwise stamp it with their own (often empty) store and drop it out of
    the branch queue entirely.
    """
    if not action.startswith('payment.'):
        return None
    from app.repositories.repository import PaymentReportRepository

    payment = PaymentReportRepository().get_by_id(target_id)
    order = getattr(payment, 'order', None) if payment else None
    return getattr(order, 'store_id', None)


def request_or_do(company_id, action, target_type, target_id, user_role,
                  user_id, reason=None):
    """Perform `action` if this user may decide; otherwise raise a request."""
    from app.models.models import ApprovalRequest
    from app.utils.i18n import t

    if action not in PERFORMERS:
        raise ValueError(f'Không biết cách thực hiện "{action}"')

    row = ApprovalRequest(
        company_id=company_id, action=action, target_type=target_type,
        target_id=target_id, reason=reason, requested_by_id=user_id,
        store_id=_branch_of(action, target_id))

    if user_role in DECIDING_ROLES:
        # Done now, and nothing is written to the queue: there is no decision
        # pending and a row saying otherwise would be a record of a wait that
        # never happened.
        PERFORMERS[action](row)
        return Outcome(True, None, '')

    row.status = ApprovalRequest.STATUS_PENDING
    db.session.add(row)
    db.session.commit()
    return Outcome(
        False, row,
        t('Đã gửi đề nghị cho quản lý chi nhánh duyệt. Việc này chưa có hiệu lực cho tới khi được duyệt.'))


def approve(request_row, user_id, note=None):
    """Decide yes — and carry the action out."""
    from datetime import datetime

    from app.models.models import ApprovalRequest

    if not request_row.is_pending():
        # Otherwise approving twice would confirm twice, or reverse a refusal
        # somebody already recorded.
        raise ValueError('Đề nghị này đã được quyết định rồi')

    if (request_row.requested_by_id is not None
            and str(request_row.requested_by_id) == str(user_id)):
        # Not reachable today: a deciding role never creates a row, the action
        # is performed on the spot. It becomes reachable the day somebody is
        # promoted between asking and deciding, or DECIDING_ROLES is widened.
        # Two pairs of eyes or none — a request the asker signs themselves
        # records a review that did not happen.
        raise ValueError('Không thể tự duyệt đề nghị của chính mình')

    PERFORMERS[request_row.action](request_row)
    request_row.status = ApprovalRequest.STATUS_APPROVED
    request_row.decided_by_id = user_id
    request_row.decided_at = datetime.utcnow()
    request_row.decision_note = note
    db.session.commit()
    return request_row


def reject(request_row, user_id, note=None):
    """Decide no. Nothing happens to the document, and the reason is kept."""
    from datetime import datetime

    from app.models.models import ApprovalRequest

    if not request_row.is_pending():
        raise ValueError('Đề nghị này đã được quyết định rồi')

    request_row.status = ApprovalRequest.STATUS_REJECTED
    request_row.decided_by_id = user_id
    request_row.decided_at = datetime.utcnow()
    request_row.decision_note = note
    db.session.commit()
    return request_row


def pending_for(company_id, store_ids=None):
    """Requests waiting for a decision.

    `store_ids=None` means every branch, which is what a company admin sees —
    the person above the branches. A branch manager passes their own stores.

    A row with no `store_id` (raised before the column existed, and whose
    document has since gone) is shown to the company-wide view only. It cannot
    be attributed to a branch, and putting it in an arbitrary branch queue
    would be worse than leaving it to the person who oversees all of them.
    """
    from app.models.models import ApprovalRequest

    query = ApprovalRequest.query.filter_by(
        company_id=company_id, status=ApprovalRequest.STATUS_PENDING)
    if store_ids is not None:
        query = query.filter(ApprovalRequest.store_id.in_(list(store_ids)))
    return query.order_by(ApprovalRequest.requested_at).all()
