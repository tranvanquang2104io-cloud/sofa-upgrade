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

#: Every document type a template can be uploaded for, and its label.
#:
#: ONE list, because there were two: the upload form hand-wrote seven options
#: and the services hand-wrote the types they look up. They disagreed by two —
#: `agreement` and `order_confirmation` were required by the code and absent
#: from the form — so pressing "In HĐNT" failed and the screen that would have
#: fixed it did not offer the type. Each half was individually correct, which
#: is why nobody found it.
#:
#: Order is the order the form shows. Add a new printable document here and it
#: appears on the upload screen, passes validation, and is covered by the test
#: that compares this list against what the code actually asks for.
PRINTABLE_TYPES = (
    ('quotation', 'Báo giá'),
    ('contract', 'Hợp đồng'),
    ('handover', 'Biên bản bàn giao'),
    # The delivery generator prefers `delivery` and falls back to `handover`
    # (services.py), so both have to be creatable or the preference is a
    # setting nobody can exercise.
    ('delivery', 'Biên bản giao hàng'),
    ('payment', 'Phiếu thanh toán (chung)'),
    ('payment_advance', 'Phiếu tạm ứng'),
    ('payment_final', 'Phiếu thanh toán đợt cuối'),
    ('payment_request', 'Đề nghị thanh toán'),
    ('agreement', 'Hợp đồng nguyên tắc'),
    ('order_confirmation', 'Đơn đặt hàng (ĐĐH)'),
    # Đơn mua hàng: in ra bằng Python cứng trước đây (T-22a ghi lại dấu vết,
    # T-22b đưa về Cách A). Bố cục mặc định sinh từ chính bản dựng Python cũ,
    # nên không có gì bị bịa ra — đó vẫn là tờ đơn đang gửi nhà cung cấp.
    ('purchase_order', 'Đơn mua hàng'),
    ('production_plan', 'Lệnh sản xuất'),
)


def is_printable_type(document_type):
    """Whether a template may be stored under this type."""
    return any(key == document_type for key, _ in PRINTABLE_TYPES)


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
