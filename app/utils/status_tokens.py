"""One shared vocabulary for document/order status → colour.

WHY
---
Status colour was decided independently on every screen: the sales screens
used inline ``{% if %}/{% elif %}`` chains in the template, the procurement
screens used a ``colors.get(status, 'secondary')`` dict built in the view. The
same Bootstrap colour therefore meant different things on different pages —
``bg-warning`` was "delivered" on the order list but "unsigned" on contracts.

Professional design systems (SAP Fiori semantic colours, Salesforce Lightning,
Frappe's ``get_indicator``) all solve this the same way: business states map
through ONE table to a small set of *semantic tokens*, and the UI only ever
renders a token. Adding a status then means adding one row here, not editing
N templates.

THE TOKENS (deliberately only five)
    neutral   — not started / informational      (Draft, New)
    progress  — actively moving                  (Sent, In Production)
    attention — needs a human, not broken        (Pending approval, Partial)
    success   — terminal good                    (Approved, Signed, Paid)
    critical  — terminal bad / blocking          (Rejected, Cancelled)

Fiori's rule that colour must never be the ONLY carrier of meaning is kept:
every helper returns a label alongside the token.
"""

# Semantic token -> Bootstrap 5 contextual class.
# Changing the palette is a one-line edit here.
TOKEN_CLASSES = {
    'neutral': 'bg-secondary',
    'progress': 'bg-primary',
    'attention': 'bg-warning text-dark',
    'success': 'bg-success',
    'critical': 'bg-danger',
}

DEFAULT_TOKEN = 'neutral'


def token_class(token):
    """Bootstrap classes for a semantic token."""
    return TOKEN_CLASSES.get(token, TOKEN_CLASSES[DEFAULT_TOKEN])


# --- per-entity status maps ---------------------------------------------
# Values are (token, label_key). label_key goes through t() in the template.
DOCUMENT_STATUS = {
    'draft': ('neutral', 'Draft'),
    'pending': ('attention', 'Pending'),
    'sent': ('progress', 'Sent'),
    'approved': ('success', 'Approved'),
    'signed': ('success', 'Signed'),
    'confirmed': ('success', 'Confirmed'),
    'paid': ('success', 'Paid'),
    'partial': ('attention', 'Partially Paid'),
    # A document WAITING for someone is not the same as one not started.
    # Flattening both to "Draft" would lose the call to action, which is the
    # more useful half of the message for the person looking at the screen.
    'pending_approval': ('attention', 'Pending Approval'),
    'unsigned': ('attention', 'Unsigned'),
    'unconfirmed': ('attention', 'Unconfirmed'),
    'rejected': ('critical', 'Rejected'),
    'canceled': ('critical', 'Cancelled'),
    'cancelled': ('critical', 'Cancelled'),
    'expired': ('critical', 'Expired'),
}

# Procurement/production statuses previously coloured by ad-hoc view dicts.
PROCUREMENT_STATUS = {
    'draft': ('neutral', 'Draft'),
    'submitted': ('progress', 'Submitted'),
    'approved': ('success', 'Approved'),
    'ordered': ('progress', 'Ordered'),
    'partial': ('attention', 'Partially Received'),
    'received': ('success', 'Received'),
    'converted': ('success', 'Converted'),
    'canceled': ('critical', 'Cancelled'),
    'rejected': ('critical', 'Rejected'),
    'processing': ('progress', 'In Production'),
    'completed': ('success', 'Completed'),
    'validating': ('attention', 'Validating'),
    'validated': ('success', 'Validated'),
    'finished': ('success', 'Finished'),
}

ENTITY_MAPS = {
    'document': DOCUMENT_STATUS,
    'quotation': DOCUMENT_STATUS,
    'contract': DOCUMENT_STATUS,
    'handover': DOCUMENT_STATUS,
    'payment': DOCUMENT_STATUS,
    'procurement': PROCUREMENT_STATUS,
    'purchase_order': PROCUREMENT_STATUS,
    'purchase_requisition': PROCUREMENT_STATUS,
    'goods_receipt': PROCUREMENT_STATUS,
    'production': PROCUREMENT_STATUS,
}


def document_state(doc):
    """Derive a document's status from its boolean flags.

    Quotations carry `is_approved`, contracts `is_signed`, handovers and
    payments `is_confirmed` — and every view template used to turn those into
    a badge with its own hardcoded colour. That drifted: `payments/view`
    painted "Draft" amber while the token map calls draft neutral, so the same
    word appeared in two colours depending on which screen you were on.

    One derivation, one colour.
    """
    if getattr(doc, 'is_canceled', False):
        return 'canceled'
    if getattr(doc, 'is_approved', False):
        return 'approved'
    if getattr(doc, 'is_signed', False):
        return 'signed'
    if getattr(doc, 'is_confirmed', False):
        return 'confirmed'

    # Some documents carry an explicit status string instead of flags.
    explicit = getattr(doc, 'status', None)
    if isinstance(explicit, str) and explicit:
        return explicit

    # Not done yet — but WHY not depends on the document, and "waiting for a
    # signature" is a more useful thing to show than "draft". Which flag the
    # object owns tells us which kind of document it is.
    if hasattr(doc, 'is_approved'):
        return 'pending_approval'
    if hasattr(doc, 'is_signed'):
        return 'unsigned'
    if hasattr(doc, 'is_confirmed'):
        return 'unconfirmed'
    return 'draft'


def document_meta(doc):
    """(token, label) for any document, from its flags."""
    return status_meta(document_state(doc))


def status_meta(status, entity='document'):
    """Return ``(token, label)`` for a raw status string."""
    if status is None:
        return DEFAULT_TOKEN, 'Unknown'
    key = str(status).strip().lower()
    mapping = ENTITY_MAPS.get(entity, DOCUMENT_STATUS)
    token, label = mapping.get(key, (DEFAULT_TOKEN, str(status)))
    return token, label


# --- order lifecycle -----------------------------------------------------
# The order's overall stage, derived from LifecycleStatus.
#
# ORDER MATTERS AND WAS PREVIOUSLY WRONG. orders/list.html tested
# `advance_paid` BEFORE `handover_confirmed`, but every delivered order also
# has advance_paid set, so the "Delivered" and "Contract Signed" branches were
# unreachable — an order stayed on "Advance Paid" from delivery until it was
# fully paid. Stages are therefore listed here most-advanced-first, once.
#
# Each entry: (flag, token, label, stage_key)
LIFECYCLE_STAGES = (
    ('completed', 'success', 'Completed', 'completed'),
    ('fully_paid', 'success', 'Fully Paid', 'fully_paid'),
    ('handover_confirmed', 'progress', 'Delivered', 'handover_confirmed'),
    ('advance_paid', 'progress', 'Advance Paid', 'advance_paid'),
    ('contract_signed', 'progress', 'Contract Signed', 'contract_signed'),
    ('contract_created', 'attention', 'Contract Drafted', 'contract_created'),
    ('quotation_approved', 'attention', 'Quotation Approved', 'quotation_approved'),
    ('quotation_created', 'neutral', 'Quotation Created', 'quotation_created'),
)

# The stepper shown on the order page, in business order (earliest first).
ORDER_PROCESS_STEPS = (
    ('quotation_approved', 'Quotation'),
    ('contract_signed', 'Contract'),
    ('advance_paid', 'Advance'),
    ('handover_confirmed', 'Handover'),
    ('fully_paid', 'Payment'),
)


def order_status_meta(order):
    """Overall ``(token, label)`` for an order, honouring cancellation."""
    if getattr(order, 'is_canceled', False):
        return 'critical', 'Cancelled'

    lifecycle = getattr(order, 'lifecycle', None)
    if lifecycle is None:
        return DEFAULT_TOKEN, 'New'

    for flag, token, label, _key in LIFECYCLE_STAGES:
        if getattr(lifecycle, flag, False):
            # An advance that was SKIPPED is not an advance that was PAID.
            # Reporting is unaffected (money figures come from PaymentReport
            # rows), but the timeline used to show the same green tick for
            # both, so a user could not tell them apart.
            if flag == 'advance_paid' and getattr(lifecycle, 'advance_skipped', False):
                return 'attention', 'Advance Skipped'
            return token, label

    return DEFAULT_TOKEN, 'New'


def order_process_steps(order):
    """Steps for the order stepper: ``[{key,label,state}]``.

    ``state`` is one of ``done`` / ``current`` / ``todo`` / ``skipped``.
    """
    lifecycle = getattr(order, 'lifecycle', None)
    steps = []
    current_assigned = False

    for flag, label in ORDER_PROCESS_STEPS:
        done = bool(getattr(lifecycle, flag, False)) if lifecycle else False
        skipped = (flag == 'advance_paid' and lifecycle is not None
                   and bool(getattr(lifecycle, 'advance_skipped', False)))

        if skipped:
            state = 'skipped'
        elif done:
            state = 'done'
        elif not current_assigned:
            state = 'current'
            current_assigned = True
        else:
            state = 'todo'

        steps.append({'key': flag, 'label': label, 'state': state})

    return steps
