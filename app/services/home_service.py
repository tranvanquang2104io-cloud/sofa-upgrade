"""The home screen: what is waiting on this person, now.

The old home screen showed four counts — orders, customers, stores, "in
progress" — to everybody, and a list of the latest orders. It answered "how
big are we", which nobody opens the app to ask, and never "what do I have to
do", which everybody does. A quotation waiting for approval, a contract nobody
signed, money recorded and never confirmed, an order past the date on its
contract: each was visible only to someone who opened that order.

Each queue is a set of orders (or materials, plans, purchase orders) with ONE
definition here. The card shows how many; the link opens `/orders?queue=<key>`,
which lists exactly those, from the same function — so the number on the card
and the rows behind it cannot disagree.

What a person sees follows what they may do: queues are grouped by the
feature that grants them, and the scope is the branches they may see.
"""
from datetime import date, timedelta

from app.config.database import db
from app.models.models import (
    Contract, HandoverRecord, LifecycleStatus, Order, PaymentReport, Quotation,
)

DUE_SOON_DAYS = 7

# key -> (label, hint, tone). Order matters: the sequence of the work.
ORDER_QUEUES = {
    'late': ('Trễ hạn giao', 'Đã quá ngày giao đã cam kết trong hợp đồng / đơn đặt hàng', 'critical'),
    'due_soon': ('Sắp đến hạn giao', f'Hạn giao trong {DUE_SOON_DAYS} ngày tới, chưa bàn giao', 'attention'),
    'quote_pending': ('Báo giá chờ duyệt', 'Đã lập báo giá, chưa duyệt', 'neutral'),
    'to_sign': ('Hợp đồng chờ ký', 'Đã lập hợp đồng, chưa ký', 'neutral'),
    'await_advance': ('Chờ thu tạm ứng', 'Hợp đồng đã ký, khách chưa tạm ứng', 'attention'),
    'payment_unconfirmed': ('Phiếu thu chưa xác nhận', 'Đã ghi phiếu, chưa xác nhận tiền về', 'attention'),
    'handover_unconfirmed': ('Bàn giao chưa xác nhận', 'Đã lập biên bản, chưa xác nhận', 'neutral'),
    'await_final': ('Chờ thu nốt', 'Đã bàn giao, chưa thu đủ tiền', 'attention'),
}


def _orders(company_id, store_ids):
    q = Order.query.filter(Order.company_id == company_id, Order.is_active == True,
                           Order.is_canceled == False)
    if store_ids is not None:
        q = q.filter(Order.store_id.in_(list(store_ids)))
    return q


def queue_order_ids(key, company_id, store_ids, today=None):
    """The ids of the orders in queue `key` — the single definition."""
    from app.services.report_service import ReportService

    today = today or date.today()
    base = _orders(company_id, store_ids).with_entities(Order.id)

    if key in ('late', 'due_soon'):
        dues = ReportService().due_dates(company_id, store_ids)
        if key == 'late':
            return {oid for oid, d in dues.items() if d < today}
        return {oid for oid, d in dues.items() if today <= d < today + timedelta(days=DUE_SOON_DAYS)}

    if key == 'quote_pending':
        q = base.join(Quotation, Quotation.order_id == Order.id).filter(
            Quotation.is_approved == False, Quotation.is_canceled == False,
            Quotation.is_active == True)
    elif key == 'to_sign':
        q = base.join(Contract, Contract.order_id == Order.id).filter(
            Contract.is_signed == False, Contract.is_canceled == False,
            Contract.is_active == True)
    elif key == 'await_advance':
        # Only where the contract asked for one: a contract at 0% advance owes
        # nothing up front, which is how the workflow judges it too.
        q = base.join(LifecycleStatus, LifecycleStatus.order_id == Order.id).join(
            Contract, Contract.order_id == Order.id).filter(
            LifecycleStatus.contract_signed == True, LifecycleStatus.advance_paid != True,
            LifecycleStatus.advance_skipped != True,
            Contract.is_signed == True, Contract.is_active == True, Contract.is_canceled == False,
            Contract.advance_percentage > 0)
    elif key == 'payment_unconfirmed':
        q = base.join(PaymentReport, PaymentReport.order_id == Order.id).filter(
            PaymentReport.is_confirmed == False, PaymentReport.is_canceled == False)
    elif key == 'handover_unconfirmed':
        q = base.join(HandoverRecord, HandoverRecord.order_id == Order.id).filter(
            HandoverRecord.is_confirmed == False, HandoverRecord.is_canceled == False)
    elif key == 'await_final':
        q = base.join(LifecycleStatus, LifecycleStatus.order_id == Order.id).filter(
            LifecycleStatus.handover_confirmed == True, LifecycleStatus.fully_paid != True)
    else:
        raise KeyError(key)
    return {str(r[0]) for r in q.distinct().all()}


def work_queue(company_id, store_ids, can, is_decider, today=None):
    """The cards for the home screen, for this person.

    `can(feature)` is the permission check; `is_decider` whether they approve
    requests. Returns [{'key', 'label', 'hint', 'tone', 'count', 'url'}] —
    every card the person is entitled to, including those at zero, so "nothing
    waiting" is a statement and not an absence.
    """
    from flask import url_for

    from app.models.models import Material, ProductionPlan, PurchaseOrder

    cards = []
    if can('orders'):
        for key, (label, hint, tone) in ORDER_QUEUES.items():
            cards.append({'key': key, 'label': label, 'hint': hint, 'tone': tone,
                          'count': len(queue_order_ids(key, company_id, store_ids, today)),
                          'url': url_for('dashboard.list_orders', queue=key)})

        plans = ProductionPlan.query.join(Order, ProductionPlan.order_id == Order.id).filter(
            ProductionPlan.company_id == company_id, ProductionPlan.is_delayed == True,
            ProductionPlan.status.notin_((ProductionPlan.STATUS_FINISHED, ProductionPlan.STATUS_CANCELED)))
        if store_ids is not None:
            plans = plans.filter(Order.store_id.in_(list(store_ids)))
        cards.append({'key': 'production_delayed', 'label': 'Sản xuất đang chậm',
                      'hint': 'Kế hoạch sản xuất bị đánh dấu chậm', 'tone': 'critical',
                      'count': plans.count(), 'url': url_for('dashboard.list_production_plans', status='delayed')})

    if can('inventory'):
        from sqlalchemy.orm import selectinload
        materials = Material.query.filter_by(company_id=company_id, is_active=True).options(
            selectinload(Material.stock_entries)).all()
        cards.append({'key': 'low_stock', 'label': 'Vật tư dưới mức tối thiểu',
                      'hint': 'Tồn kho thấp hơn mức cảnh báo', 'tone': 'attention',
                      'count': sum(1 for m in materials if m.is_low_stock),
                      'url': url_for('dashboard.list_materials', low_stock=1)})

    if can('purchasing'):
        count = PurchaseOrder.query.filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status.in_((PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL))).count()
        cards.append({'key': 'po_awaiting', 'label': 'Đơn mua chờ nhận hàng',
                      'hint': 'Đã gửi nhà cung cấp, chưa nhận đủ', 'tone': 'neutral',
                      'count': count, 'url': url_for('dashboard.list_purchase_orders', status='awaiting_receipt')})

    if is_decider:
        from app.services.approvals import pending_count
        cards.append({'key': 'approvals', 'label': 'Đề nghị chờ duyệt',
                      'hint': 'Nhân viên đang chờ bạn quyết định', 'tone': 'attention',
                      'count': pending_count(company_id, store_ids), 'url': url_for('dashboard.list_approvals')})
    return cards


def scope_counts(company_id, store_ids):
    """How big the reader's part of the business is — one line, not the page."""
    from app.models.models import Customer, Store

    customers = db.session.query(Customer).filter(Customer.is_active == True)
    customers = (customers.filter(Customer.company_id == company_id) if store_ids is None
                 else customers.filter(Customer.store_id.in_(list(store_ids))))
    stores = Store.query.filter_by(company_id=company_id, is_active=True)
    if store_ids is not None:
        stores = stores.filter(Store.id.in_(list(store_ids)))
    # Every order the order list can show, cancelled ones included — the list
    # has a filter for them, and the old home total counted them the same way.
    orders = Order.query.filter(Order.company_id == company_id, Order.is_active == True)
    if store_ids is not None:
        orders = orders.filter(Order.store_id.in_(list(store_ids)))
    return {
        'orders': orders.count(),
        'customers': customers.count(),
        'stores': stores.count(),
    }
