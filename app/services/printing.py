"""Which printed files belong to a thing — whatever kind of thing it is.

`Document` links back with one foreign key per document kind: `quotation_id`,
`contract_id`, `handover_record_id`, `payment_report_id`. Four kinds, four
columns, and every new printable document would be a fifth column, a fifth
relationship, and a fifth branch everywhere that asks "what was this printed
from?".

`source_type` + `source_id` replaces that with data. A new printable kind
needs a line in `SOURCE_TYPES` and nothing else.

The four old columns are still read here. They are what today's rows carry and
what today's relationships use; a lookup that ignored them would show an empty
history on every document printed before this existed, which is worse than the
missing feature it replaces.
"""
from app.config import db

#: model class name -> the value stored in `Document.source_type`.
#: Written out rather than derived from the class name: a rename should be a
#: decision somebody makes about stored data, not something that silently
#: orphans every row pointing at the old spelling.
SOURCE_TYPES = {
    'Quotation': 'quotation',
    'Contract': 'contract',
    'HandoverRecord': 'handover_record',
    'PaymentReport': 'payment_report',
    'MasterAgreement': 'master_agreement',
    'OrderConfirmation': 'order_confirmation',
    'PurchaseOrder': 'purchase_order',
    'ProductionPlan': 'production_plan',
    'GoodsReceipt': 'goods_receipt',
    'SupplierInvoice': 'supplier_invoice',
    'PurchaseRequisition': 'purchase_requisition',
}

#: The per-kind columns that predate `source_type`. Read as well as the new
#: pair so a document printed before this change still appears.
LEGACY_COLUMNS = {
    'Quotation': 'quotation_id',
    'Contract': 'contract_id',
    'HandoverRecord': 'handover_record_id',
    'PaymentReport': 'payment_report_id',
}


def source_type_of(obj):
    """The stored `source_type` for this object, or None if it is not printable."""
    return SOURCE_TYPES.get(type(obj).__name__)


def documents_for(obj):
    """Every file printed from `obj`, newest first.

    Newest first because the question is almost always "what did we last send
    them?" — an older copy is history, the latest one is the document.

    Returns an empty list for anything unprintable rather than raising: a
    history block is the least important thing on a screen and must not be
    able to take the page down.
    """
    from app.models.models import Document

    kind = source_type_of(obj)
    if kind is None:
        return []

    obj_id = getattr(obj, 'id', None)
    if obj_id is None:
        return []

    clauses = [db.and_(Document.source_type == kind,
                       Document.source_id == obj_id)]

    legacy = LEGACY_COLUMNS.get(type(obj).__name__)
    if legacy is not None:
        clauses.append(getattr(Document, legacy) == obj_id)

    return (Document.query
            .filter(db.or_(*clauses))
            .order_by(Document.generated_at.desc())
            .all())
