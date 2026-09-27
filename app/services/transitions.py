"""Recording who did what to a document.

Called from the service methods that change a document's standing — the same
choke points the rest of this refactor converged on, which is why this could
be added without touching a route. If a new way to sign a contract appears
tomorrow it goes through `ContractService.mark_signed`, and so it is recorded.

Two rules this file keeps:

1. **Never break the action it is recording.** A failure to write history is
   logged and swallowed. That is the opposite of the usual advice and it is
   deliberate: refusing to confirm a customer's payment because an audit row
   would not insert is a worse outcome than a gap in the history, and the gap
   is visible while a blocked payment at the counter is an emergency. The
   alternative — letting it raise — would also mean this file could take the
   whole product down, which is too much power for a ledger.

2. **Never invent a user.** Outside a request there is nobody acting: a
   migration, a seed, a scheduled job. The row is written with `user_id` NULL
   rather than attributed to whoever happens to be convenient. A history that
   names the wrong person is worse than one that admits it does not know.
"""
import logging

logger = logging.getLogger(__name__)

#: What each recorded action is called on screen.
#:
#: Written here rather than run through `t()` because these are stored VALUES,
#: not source literals: the translation scanner keys on literals it can see, so
#: `t(event.action)` would pass the scanner and then show the reader
#: "payment.cancel". A row written last year must still render as a sentence.
ACTION_LABELS_VI = {
    'quotation.approve': 'Duyệt báo giá',
    'contract.sign': 'Ký hợp đồng',
    'contract.cancel': 'Huỷ hợp đồng',
    'handover.confirm': 'Xác nhận bàn giao',
    'payment.confirm': 'Xác nhận đã thu tiền',
    'payment.cancel': 'Huỷ phiếu thu',
    'order.cancel': 'Huỷ đơn hàng',
}


def label_for(action):
    """A sentence for an action, falling back to the raw value.

    Falls back rather than raising: an action recorded by a future version and
    read by an older screen should still show SOMETHING. A history with a gap
    in it is worse than one with an untranslated line in it.
    """
    return ACTION_LABELS_VI.get(action, action)


def _who():
    """The user acting, or (None, None) outside a request."""
    try:
        from flask import has_request_context, session
        if not has_request_context() or 'user_id' not in session:
            return None, None
        return session.get('user_id'), session.get('full_name') or session.get(
            'username')
    except Exception:
        return None, None


def record(company_id, document_type, document_id, action,
           from_state=None, to_state=None, reason=None):
    """Append one line to a document's history. Never raises."""
    from app.config.database import db
    from app.models.models import DocumentTransition

    try:
        user_id, user_name = _who()
        db.session.add(DocumentTransition(
            company_id=company_id, document_type=document_type,
            document_id=document_id, action=action,
            from_state=from_state, to_state=to_state,
            user_id=user_id, user_name=user_name,
            reason=(reason or None)))
        db.session.flush()
    except Exception:
        # See rule 1 in the module docstring.
        logger.exception('Could not record %s on %s %s', action,
                         document_type, document_id)


def history_for(document_type, document_id):
    """Everything that has happened to one document, oldest first.

    Oldest first because this is read as a story, not as a feed: what was done
    and then what was done about it.
    """
    from app.models.models import DocumentTransition

    return (DocumentTransition.query
            .filter_by(document_type=document_type, document_id=document_id)
            .order_by(DocumentTransition.occurred_at,
                      DocumentTransition.id)
            .all())


def history_for_order(order_id):
    """The order's own events and those of every document hanging off it.

    A person looking at an order wants one story, not five. Assembled by
    asking each child service for its ids rather than by joining, because the
    document types have no common parent table to join through.
    """
    from app.models.models import (
        Contract, DocumentTransition, HandoverRecord, PaymentReport, Quotation,
    )

    ids = {'order': [order_id]}
    for key, model in (('quotation', Quotation), ('contract', Contract),
                       ('handover', HandoverRecord),
                       ('payment', PaymentReport)):
        ids[key] = [str(row.id) for row in
                    model.query.filter_by(order_id=order_id).all()]

    if not any(id_list for id_list in ids.values()):
        return []

    from sqlalchemy import and_, or_

    return (DocumentTransition.query
            .filter(or_(*[
                and_(DocumentTransition.document_type == document_type,
                     DocumentTransition.document_id.in_(id_list))
                for document_type, id_list in ids.items() if id_list]))
            .order_by(DocumentTransition.occurred_at,
                      DocumentTransition.id)
            .all())
