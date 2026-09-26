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


def _confirm_payment(request_row):
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    payment = PaymentReport.query.get(request_row.target_id)
    if payment is None:
        raise ValueError('Không tìm thấy phiếu thanh toán')
    PaymentReportService().mark_confirmed(payment.id, payment.order_id)


def _cancel_payment(request_row):
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    payment = PaymentReport.query.get(request_row.target_id)
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


def request_or_do(company_id, action, target_type, target_id, user_role,
                  user_id, reason=None):
    """Perform `action` if this user may decide; otherwise raise a request."""
    from app.models.models import ApprovalRequest
    from app.utils.i18n import t

    if action not in PERFORMERS:
        raise ValueError(f'Không biết cách thực hiện "{action}"')

    row = ApprovalRequest(
        company_id=company_id, action=action, target_type=target_type,
        target_id=target_id, reason=reason, requested_by_id=user_id)

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


def pending_for(company_id):
    from app.models.models import ApprovalRequest

    return (ApprovalRequest.query
            .filter_by(company_id=company_id,
                       status=ApprovalRequest.STATUS_PENDING)
            .order_by(ApprovalRequest.requested_at)
            .all())
