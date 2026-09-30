# -*- coding: utf-8 -*-
"""BI / KPI reporting (item 9).

Figures split into Sales, Purchasing, Accounting, Delivery and Margin. Every
figure respects the document state machine: only confirmed, non-canceled
payments count as cash; only signed, non-canceled, ACTIVE contracts (and
confirmed Đơn đặt hàng) count as booked sales.

Two dimensions were missing and are now on every method:

* `store_ids` — which branches the reader may see. `None` means the whole
  company, which only a company admin is given (the route decides). Until
  2026-09-30 every figure here was company-wide, so a branch manager — or a
  staff member granted "reports" — read every branch's revenue and every
  customer's debt by name, while the documents themselves were already
  locked to their branch.
* `period` — a `periods.Period`. `None` means all time, which is what the
  figures used to be: "1.2 tỷ collected" with no way to tell whether that was
  good. Point-in-time figures (what is owed NOW, what is late NOW) ignore it.

Called with neither, every method returns what it always did.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func

from app.config.database import db
from app.models.models import (
    Order, Contract, PaymentReport, Customer,
    PurchaseOrder, PurchaseOrderLine, PurchaseRequisition, GoodsReceipt,
    Supplier, LifecycleStatus,
)


def _f(x):
    return float(x or 0)


def _in_scope(query, store_ids):
    """Narrow a query that already involves `Order` to the reader's branches."""
    if store_ids is None:
        return query
    return query.filter(Order.store_id.in_(list(store_ids)))


def _day(value):
    return value.date() if isinstance(value, datetime) else value


def _payment_amount(payment):
    """The cash one confirmed payment represents — THE rule, used everywhere."""
    if payment.payment_type == 'advance':
        return Decimal(str(payment.advance_amount or payment.amount or 0))
    return Decimal(str(payment.remaining_amount or payment.amount or 0))


def _delta(now, before):
    """Change against the previous period, for display. None when there is no
    previous figure to compare with, rather than an invented +100%."""
    if before in (None, 0):
        return None
    return round((now - before) / before * 100)


class ReportService:
    """Aggregate KPIs for the reports screen and the home screen."""

    # ------------------------------------------------------------ booked

    def _booked_rows(self, company_id, store_ids=None, period=None):
        """Every agreement that counts as booked revenue, per customer.

        THIS IS THE ONE DEFINITION. It used to be written out separately in
        sales(), in top_customers and in accounting() — three copies of the
        same rule — so when the HĐNT path was added and orders started being
        agreed via an ĐƠN ĐẶT HÀNG instead of a Contract, all three kept
        counting only contracts and silently under-reported what customers
        owed by the full value of every framework-agreement order.

        A contract is booked on the date the document says it was signed
        (`contract_date`), falling back to when it was marked signed; a Đơn đặt
        hàng on its `confirmation_date`.

        Returns [(customer_id, customer_name, value)].
        """
        from app.models.models import OrderConfirmation

        merged = {}

        def add(cid, name, value, day):
            if period is not None and not period.contains(day):
                return
            key = str(cid)
            if key not in merged:
                merged[key] = [cid, name, Decimal('0')]
            merged[key][2] += Decimal(str(value or 0))

        contracts = _in_scope(db.session.query(
            Customer.id, Customer.name, Contract.contract_value,
            Contract.contract_date, Contract.signed_date,
        ).join(Order, Order.customer_id == Customer.id
        ).join(Contract, Contract.order_id == Order.id
        ).filter(
            Order.company_id == company_id,
            Order.is_canceled == False,
            Contract.is_signed == True,
            Contract.is_canceled == False,
            # A renegotiated order keeps its old contract: still signed, still
            # not cancelled, only `is_active = False`. Without this the order
            # books twice — at the old price AND the new one.
            Contract.is_active == True,
        ), store_ids).all()
        for cid, name, value, contract_date, signed_date in contracts:
            add(cid, name, value, contract_date or _day(signed_date))

        confirmations = _in_scope(db.session.query(
            Customer.id, Customer.name, OrderConfirmation.total_amount,
            OrderConfirmation.confirmation_date,
        ).join(Order, Order.customer_id == Customer.id
        ).join(OrderConfirmation, OrderConfirmation.order_id == Order.id
        ).filter(
            Order.company_id == company_id,
            Order.is_canceled == False,
            OrderConfirmation.status == OrderConfirmation.STATUS_CONFIRMED,
            OrderConfirmation.is_canceled == False,
        ), store_ids).all()
        for cid, name, value, day in confirmations:
            add(cid, name, value, day)

        return [(c, n, v) for c, n, v in merged.values()]

    def _booked_total(self, company_id, store_ids=None, period=None):
        return float(sum((v for _c, _n, v in self._booked_rows(company_id, store_ids, period)),
                         Decimal('0')))

    # ------------------------------------------------------------ cash

    def _confirmed_payments(self, company_id, store_ids=None, period=None):
        """(payment, customer_id) for confirmed, uncancelled payments.

        In a period by the day the money arrived (`payment_date`), falling back
        to the day it was confirmed.
        """
        rows = _in_scope(db.session.query(PaymentReport, Order.customer_id).join(
            Order, PaymentReport.order_id == Order.id).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False), store_ids).all()
        if period is None:
            return rows
        return [(p, c) for p, c in rows
                if period.contains(p.payment_date or _day(p.confirmed_date))]

    def _collected_by_customer(self, company_id, store_ids=None, period=None):
        """Cash received per customer, using the same rule as _cash_collected."""
        totals = {}
        for payment, customer_id in self._confirmed_payments(company_id, store_ids, period):
            key = str(customer_id)
            totals[key] = totals.get(key, Decimal('0')) + _payment_amount(payment)
        return totals

    def _cash_collected(self, company_id, store_ids=None, period=None):
        """Cash actually received: confirmed, non-canceled payments.

        Advance rows contribute their advance_amount; final rows the remaining_amount
        (the balance settled at handover). Falls back to `amount` when those are 0.
        """
        return float(sum((_payment_amount(p) for p, _c in
                          self._confirmed_payments(company_id, store_ids, period)),
                         Decimal('0')))

    def unconfirmed_payments(self, company_id, store_ids=None):
        """Payments recorded but not yet confirmed.

        Every figure in the product counts a payment only once `is_confirmed`
        is set — correctly, because until then it is a claim rather than cash.
        But nothing listed the claims, so a slip recorded on Friday and never
        confirmed keeps the customer looking like a debtor until somebody
        happens to open that order.

        Oldest first: the longer one has been sitting, the more likely it is
        that everybody assumes somebody else dealt with it.
        """
        rows = _in_scope(db.session.query(PaymentReport, Order, Customer).join(
            Order, PaymentReport.order_id == Order.id).outerjoin(
            Customer, Order.customer_id == Customer.id).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == False,
            PaymentReport.is_canceled == False,
        ), store_ids).order_by(PaymentReport.report_date.asc()).all()

        return [{
            'payment_id': str(payment.id),
            'report_number': payment.report_number,
            'report_date': payment.report_date,
            'payment_type': payment.payment_type,
            'amount': float(_payment_amount(payment)),
            'order_id': str(order.id),
            'order_code': order.order_code,
            'customer_name': customer.name if customer else '',
        } for payment, order, customer in rows]

    def customer_receivables(self, company_id, store_ids=None):
        """Who owes us money, and how much — right now, whatever the period."""
        collected = self._collected_by_customer(company_id, store_ids)

        result = []
        for customer_id, name, booked in self._booked_rows(company_id, store_ids):
            paid = collected.get(str(customer_id), Decimal('0'))
            outstanding = booked - paid
            if outstanding <= 0 and booked <= 0:
                continue
            result.append({
                'customer_id': str(customer_id),
                'customer_name': name,
                'booked': float(booked),
                'collected': float(paid),
                'outstanding': float(max(outstanding, Decimal('0'))),
                'settled': outstanding <= 0,
            })

        result.sort(key=lambda r: -r['outstanding'])
        return result

    def receivable_total(self, company_id, store_ids=None):
        return sum(r['outstanding'] for r in self.customer_receivables(company_id, store_ids))

    # ------------------------------------------------------------ sales

    def sales(self, company_id, store_ids=None, period=None):
        orders = _in_scope(db.session.query(
            Order.created_at, Order.is_canceled, LifecycleStatus.completed,
            LifecycleStatus.completed_at,
        ).outerjoin(LifecycleStatus, LifecycleStatus.order_id == Order.id).filter(
            Order.company_id == company_id, Order.is_active == True), store_ids).all()
        started = orders if period is None else [o for o in orders if period.contains(_day(o.created_at))]
        live = [o for o in started if not o.is_canceled]
        # Finished IN the period, whenever they were started.
        finished = [o for o in orders if not o.is_canceled and o.completed
                    and (period is None or period.contains(_day(o.completed_at)))]

        ranked = sorted(self._booked_rows(company_id, store_ids, period), key=lambda r: -r[2])[:5]
        return {
            'orders_total': len(live),
            'canceled': len(started) - len(live),
            'completed': len(finished),
            # Started in the period (or ever) and not finished yet.
            'in_progress': sum(1 for o in live if not o.completed),
            'booked_value': self._booked_total(company_id, store_ids, period),
            'collected': self._cash_collected(company_id, store_ids, period),
            'top_customers': [{'name': n, 'value': float(v)} for _c, n, v in ranked],
        }

    # ------------------------------------------------------------ delivery

    def due_dates(self, company_id, store_ids=None, open_only=True):
        """{order_id: due date} for agreed orders, in two queries.

        `order_due_date` answers for one order; asking it per order would be a
        query per row on every home screen. Same rule, fetched in bulk.
        """
        from app.models.models import OrderConfirmation

        base = _in_scope(db.session.query(Order.id).join(
            LifecycleStatus, LifecycleStatus.order_id == Order.id).filter(
            Order.company_id == company_id, Order.is_active == True,
            Order.is_canceled == False), store_ids)
        if open_only:
            base = base.filter(LifecycleStatus.handover_confirmed != True)
        order_ids = [r[0] for r in base.all()]
        if not order_ids:
            return {}

        dues = {}
        contracts = Contract.query.filter(
            Contract.order_id.in_(order_ids), Contract.is_signed == True,
            Contract.is_canceled == False, Contract.is_active == True,
        ).order_by(Contract.contract_date.asc()).all()
        for c in contracts:   # latest contract_date wins, as order_commitment does
            start = c.contract_start_date or c.contract_date or _day(c.signed_date)
            if start and c.contract_days_complete:
                dues[str(c.order_id)] = start + timedelta(days=int(c.contract_days_complete))
            else:
                dues.pop(str(c.order_id), None)
        with_contract = {str(c.order_id) for c in contracts}
        for oc in OrderConfirmation.query.filter(
                OrderConfirmation.order_id.in_(order_ids),
                OrderConfirmation.status == OrderConfirmation.STATUS_CONFIRMED,
                OrderConfirmation.is_canceled == False,
        ).order_by(OrderConfirmation.confirmation_date.asc()).all():
            if str(oc.order_id) not in with_contract and oc.delivery_date:
                dues[str(oc.order_id)] = oc.delivery_date
        return dues

    def delivery(self, company_id, store_ids=None, period=None, today=None):
        """Are we delivering what we promised, when we promised it?

        `late` and `due_soon` are NOW: open orders past, or within a week of,
        their promised date. `on_time` / `handed_over` are for the period:
        handovers confirmed in it, and how many were on or before the date.
        """
        from app.models.models import HandoverRecord

        today = today or date.today()
        open_dues = self.due_dates(company_id, store_ids)
        late = sorted(((d, oid) for oid, d in open_dues.items() if d < today))
        soon = sorted(((d, oid) for oid, d in open_dues.items() if today <= d < today + timedelta(days=7)))

        orders = {str(o.id): o for o in Order.query.filter(
            Order.id.in_([oid for _d, oid in late + soon])).all()} if (late or soon) else {}

        def row(due, oid):
            o = orders.get(oid)
            return {'order_id': oid, 'order_code': o.order_code if o else '',
                    'customer_name': o.customer.name if o and o.customer else '',
                    'title': o.title if o else '', 'due': due, 'days': (today - due).days}

        handovers = _in_scope(db.session.query(HandoverRecord.order_id, HandoverRecord.handover_date).join(
            Order, HandoverRecord.order_id == Order.id).filter(
            Order.company_id == company_id, Order.is_canceled == False,
            HandoverRecord.is_confirmed == True, HandoverRecord.is_canceled == False), store_ids).all()
        if period is not None:
            handovers = [h for h in handovers if period.contains(h.handover_date)]
        all_dues = self.due_dates(company_id, store_ids, open_only=False) if handovers else {}
        judged = [(h, all_dues.get(str(h.order_id))) for h in handovers]
        judged = [(h, d) for h, d in judged if d is not None and h.handover_date]
        on_time = sum(1 for h, d in judged if h.handover_date <= d)

        return {
            'late': [row(d, oid) for d, oid in late],
            'due_soon': [row(d, oid) for d, oid in soon],
            'handed_over': len(handovers),
            'judged': len(judged),
            'on_time': on_time,
            'on_time_pct': round(on_time / len(judged) * 100) if judged else None,
        }

    # ------------------------------------------------------------ margin

    def margins(self, company_id, store_ids=None, period=None):
        """Material margin on orders COMPLETED in the period.

        Revenue minus the materials issued to the job, valued at moving-average
        cost. Labour is not recorded anywhere yet, so this is not profit, and
        the screen says so; orders whose materials have no cost are flagged
        rather than counted as free.
        """
        from sqlalchemy.orm import selectinload

        from app.models.models import ProductionPlan, ProductionMaterialLine
        from app.services.services import ProductionPlanService

        rows = _in_scope(db.session.query(ProductionPlan, LifecycleStatus.completed_at).join(
            Order, ProductionPlan.order_id == Order.id).join(
            LifecycleStatus, LifecycleStatus.order_id == Order.id).filter(
            Order.company_id == company_id, Order.is_canceled == False,
            LifecycleStatus.completed == True), store_ids).options(
            selectinload(ProductionPlan.material_lines).joinedload(ProductionMaterialLine.material)).all()
        if period is not None:
            rows = [(p, c) for p, c in rows if period.contains(_day(c))]

        svc = ProductionPlanService()
        orders, revenue, cost, incomplete = [], Decimal('0'), Decimal('0'), 0
        for plan, _completed in rows:
            m = svc.order_margin(plan)
            revenue += Decimal(str(m['revenue']))
            cost += Decimal(str(m['material_cost']))
            incomplete += 0 if m['material_cost_complete'] else 1
            orders.append({'order_id': str(plan.order_id), 'order_code': plan.order.order_code,
                           'title': plan.order.title, **m,
                           'margin_pct': round(m['gross_margin'] / m['revenue'] * 100) if m['revenue'] else None})
        orders.sort(key=lambda r: (r['margin_pct'] is None, r['margin_pct'] if r['margin_pct'] is not None else 0))
        return {
            'orders': orders,
            'revenue': float(revenue),
            'material_cost': float(cost),
            'gross_margin': float(revenue - cost),
            'margin_pct': round((revenue - cost) / revenue * 100) if revenue else None,
            'incomplete': incomplete,
        }

    # ------------------------------------------------------------ purchasing

    def purchasing(self, company_id, store_ids=None, period=None):
        """Spend is by the receiving branch (`PurchaseOrder.store_id`)."""
        def scoped(q, model):
            return q if store_ids is None else q.filter(model.store_id.in_(list(store_ids)))

        pr_count = scoped(db.session.query(func.count(PurchaseRequisition.id)).filter(
            PurchaseRequisition.company_id == company_id), PurchaseRequisition).scalar() or 0
        gr_count = scoped(db.session.query(func.count(GoodsReceipt.id)).filter(
            GoodsReceipt.company_id == company_id), GoodsReceipt).scalar() or 0

        pos = scoped(PurchaseOrder.query.filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status != 'canceled'), PurchaseOrder).all()
        # Open orders are a fact of NOW; spend belongs to the period it was ordered in.
        open_pos = sum(1 for p in pos
                       if p.status in (PurchaseOrder.STATUS_DRAFT,
                                       PurchaseOrder.STATUS_ORDERED,
                                       PurchaseOrder.STATUS_PARTIAL))
        in_period = pos if period is None else [p for p in pos if period.contains(p.order_date or _day(p.created_at))]
        po_value = sum((Decimal(str(p.total_amount or 0)) for p in in_period), Decimal('0'))
        # Ex-VAT, so it can be compared with `received` below, which is
        # quantity x unit_price and carries no VAT.
        po_value_net = sum((Decimal(str(p.subtotal or 0)) for p in in_period), Decimal('0'))
        ids = [p.id for p in in_period]

        received = db.session.query(
            func.coalesce(func.sum(PurchaseOrderLine.quantity_received *
                                   PurchaseOrderLine.unit_price), 0)).filter(
            PurchaseOrderLine.po_id.in_(ids)).scalar() if ids else 0

        rows = db.session.query(
            Supplier.name, func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).join(
            PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id).filter(
            PurchaseOrder.id.in_(ids)).group_by(Supplier.name).order_by(
            func.sum(PurchaseOrder.total_amount).desc()).limit(5).all() if ids else []

        return {
            'pr_count': pr_count,
            'po_count': len(in_period),
            'gr_count': gr_count,
            'po_value': float(po_value),
            'received_value': _f(received),
            'open_pos': open_pos,
            'outstanding': float(po_value_net) - _f(received),
            'top_suppliers': [{'name': n, 'value': _f(v)} for n, v in rows],
        }

    # ------------------------------------------------------------ accounting

    def accounting(self, company_id, store_ids=None, period=None):
        collected = self._cash_collected(company_id, store_ids, period)
        booked = self._booked_total(company_id, store_ids, period)

        advance = final = Decimal('0')
        for p, _c in self._confirmed_payments(company_id, store_ids, period):
            if p.payment_type == 'advance':
                advance += Decimal(str(p.advance_amount or 0))
            elif p.payment_type == 'final':
                final += Decimal(str(p.remaining_amount or 0))

        pending = self.unconfirmed_payments(company_id, store_ids)
        return {
            'cash_in': collected,
            'booked_value': booked,
            # What is owed is a fact of now, not of the period being viewed.
            'receivable': self.receivable_total(company_id, store_ids),
            'advance_collected': float(advance),
            'final_collected': float(final),
            'pending_count': len(pending),
            'pending_amount': sum(p['amount'] for p in pending),
        }

    # ------------------------------------------------------------ composites

    def dashboard(self, company_id, store_ids=None, period=None):
        return {
            'sales': self.sales(company_id, store_ids, period),
            'purchasing': self.purchasing(company_id, store_ids, period),
            'accounting': self.accounting(company_id, store_ids, period),
        }

    def headline(self, company_id, store_ids, current, before, today=None):
        """The four figures an owner or a branch manager looks at first."""
        booked = self._booked_total(company_id, store_ids, current)
        cash = self._cash_collected(company_id, store_ids, current)
        prev_booked = self._booked_total(company_id, store_ids, before) if before else None
        prev_cash = self._cash_collected(company_id, store_ids, before) if before else None
        late = [d for d in self.due_dates(company_id, store_ids).values() if d < (today or date.today())]
        return {
            'booked': booked, 'booked_before': prev_booked, 'booked_delta': _delta(booked, prev_booked),
            'cash': cash, 'cash_before': prev_cash, 'cash_delta': _delta(cash, prev_cash),
            'receivable': self.receivable_total(company_id, store_ids),
            'late': len(late),
        }

    def by_branch(self, company_id, period):
        """One row per active branch — only ever shown to a company admin."""
        from app.models.models import Store

        rows = []
        for store in Store.query.filter_by(company_id=company_id, is_active=True).order_by(Store.name).all():
            scope = [store.id]
            rows.append({
                'store_id': str(store.id), 'name': store.name,
                'booked': self._booked_total(company_id, scope, period),
                'cash': self._cash_collected(company_id, scope, period),
                'receivable': self.receivable_total(company_id, scope),
                'late': len(self.delivery(company_id, scope)['late']),
            })
        return rows
