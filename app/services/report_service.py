# -*- coding: utf-8 -*-
"""BI / KPI reporting (item 9).

Concise, admin-facing figures split into three domains — Sales, Purchasing and
Accounting. Everything is scoped to the current company; there is no cross-tenant
read here. Amounts are summed as Decimal in the DB and returned as float for the
templates. All figures respect the document state machine: only confirmed,
non-canceled payments count as cash; only signed, non-canceled contracts count as
booked sales.
"""
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


class ReportService:
    """Aggregate KPIs for the reports dashboard."""

    def _booked_rows(self, company_id):
        """Every agreement that counts as booked revenue, per customer.

        THIS IS THE ONE DEFINITION. It used to be written out separately in
        sales(), in top_customers and in accounting() — three copies of the
        same rule — so when the HĐNT path was added and orders started being
        agreed via an ĐƠN ĐẶT HÀNG instead of a Contract, all three kept
        counting only contracts and silently under-reported what customers
        owed by the full value of every framework-agreement order.

        Returns [(customer_id, customer_name, value)].
        """
        from app.models.models import OrderConfirmation

        rows = []

        contracts = db.session.query(
            Customer.id, Customer.name,
            func.coalesce(func.sum(Contract.contract_value), 0)
        ).join(Order, Order.customer_id == Customer.id
        ).join(Contract, Contract.order_id == Order.id
        ).filter(
            Order.company_id == company_id,
            Order.is_canceled == False,
            Contract.is_signed == True,
            Contract.is_canceled == False,
        ).group_by(Customer.id, Customer.name).all()
        rows.extend(contracts)

        confirmations = db.session.query(
            Customer.id, Customer.name,
            func.coalesce(func.sum(OrderConfirmation.total_amount), 0)
        ).join(Order, Order.customer_id == Customer.id
        ).join(OrderConfirmation, OrderConfirmation.order_id == Order.id
        ).filter(
            Order.company_id == company_id,
            Order.is_canceled == False,
            OrderConfirmation.status == OrderConfirmation.STATUS_CONFIRMED,
            OrderConfirmation.is_canceled == False,
        ).group_by(Customer.id, Customer.name).all()
        rows.extend(confirmations)

        merged = {}
        for cid, name, value in rows:
            key = str(cid)
            if key not in merged:
                merged[key] = [cid, name, Decimal('0')]
            merged[key][2] += Decimal(str(value or 0))
        return [(c, n, v) for c, n, v in merged.values()]

    def _booked_total(self, company_id):
        return float(sum((v for _c, _n, v in self._booked_rows(company_id)),
                         Decimal('0')))

    def _collected_by_customer(self, company_id):
        """Cash received per customer, using the same rule as _cash_collected."""
        pays = db.session.query(PaymentReport, Order.customer_id).join(
            Order, PaymentReport.order_id == Order.id).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False).all()

        totals = {}
        for payment, customer_id in pays:
            if payment.payment_type == 'advance':
                amount = payment.advance_amount or payment.amount or 0
            else:
                amount = payment.remaining_amount or payment.amount or 0
            key = str(customer_id)
            totals[key] = totals.get(key, Decimal('0')) + Decimal(str(amount))
        return totals

    def unconfirmed_payments(self, company_id):
        """Payments recorded but not yet confirmed.

        Every figure in the product counts a payment only once `is_confirmed`
        is set — correctly, because until then it is a claim rather than cash.
        But nothing listed the claims, so a slip recorded on Friday and never
        confirmed keeps the customer looking like a debtor until somebody
        happens to open that order, and whoever is chasing the debt has no way
        to discover that the answer is "it is waiting in the queue".

        Oldest first: the longer one has been sitting, the more likely it is
        that everybody assumes somebody else dealt with it.
        """
        rows = db.session.query(PaymentReport, Order, Customer).join(
            Order, PaymentReport.order_id == Order.id).outerjoin(
            Customer, Order.customer_id == Customer.id).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == False,
            PaymentReport.is_canceled == False,
        ).order_by(PaymentReport.report_date.asc()).all()

        result = []
        for payment, order, customer in rows:
            if payment.payment_type == 'advance':
                amount = payment.advance_amount or payment.amount or 0
            else:
                amount = payment.remaining_amount or payment.amount or 0
            result.append({
                'payment_id': str(payment.id),
                'report_number': payment.report_number,
                'report_date': payment.report_date,
                'payment_type': payment.payment_type,
                'amount': float(amount),
                'order_id': str(order.id),
                'order_code': order.order_code,
                'customer_name': customer.name if customer else '',
            })
        return result

    def customer_receivables(self, company_id):
        """Who owes us money, and how much.

        The company-wide `receivable` figure said only THAT money was owed,
        never BY WHOM — so chasing debt, a weekly job, could not be done from
        the system. The supplier side already answered the mirror question
        (`outstanding_for_supplier`), which made the gap lopsided.
        """
        collected = self._collected_by_customer(company_id)

        result = []
        for customer_id, name, booked in self._booked_rows(company_id):
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

    def sales(self, company_id):
        # Orders (exclude canceled)
        orders_total = db.session.query(func.count(Order.id)).filter(
            Order.company_id == company_id, Order.is_canceled == False).scalar() or 0

        # Lifecycle progress
        completed = db.session.query(func.count(LifecycleStatus.id)).join(
            Order, LifecycleStatus.order_id == Order.id).filter(
            Order.company_id == company_id, Order.is_canceled == False,
            LifecycleStatus.completed == True).scalar() or 0
        in_progress = max(orders_total - completed, 0)

        # Booked sales — signed contracts AND confirmed order confirmations.
        booked = self._booked_total(company_id)

        collected = self._cash_collected(company_id)

        # Top customers — same definition, so a framework-agreement customer
        # is not invisible here while appearing in the totals.
        ranked = sorted(self._booked_rows(company_id), key=lambda r: -r[2])[:5]
        top_customers = [{'name': n, 'value': float(v)} for _c, n, v in ranked]

        return {
            'orders_total': orders_total,
            'completed': completed,
            'in_progress': in_progress,
            'booked_value': booked,
            'collected': collected,
            'top_customers': top_customers,
        }

    def _cash_collected(self, company_id):
        """Cash actually received: confirmed, non-canceled payments.

        Advance rows contribute their advance_amount; final rows the remaining_amount
        (the balance settled at handover). Falls back to `amount` when those are 0.
        """
        pays = db.session.query(PaymentReport).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False).all()
        total = Decimal('0')
        for p in pays:
            if p.payment_type == 'advance':
                total += Decimal(str(p.advance_amount or p.amount or 0))
            else:
                total += Decimal(str(p.remaining_amount or p.amount or 0))
        return float(total)

    def purchasing(self, company_id):
        pr_count = db.session.query(func.count(PurchaseRequisition.id)).filter(
            PurchaseRequisition.company_id == company_id).scalar() or 0
        gr_count = db.session.query(func.count(GoodsReceipt.id)).filter(
            GoodsReceipt.company_id == company_id).scalar() or 0

        pos = db.session.query(PurchaseOrder).filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status != 'canceled').all()
        po_count = len(pos)
        po_value = sum((Decimal(str(p.total_amount or 0)) for p in pos), Decimal('0'))
        open_pos = sum(1 for p in pos if p.status in ('draft', 'submitted', 'partial'))

        # Value actually received (line qty_received × unit_price) across company POs
        received = db.session.query(
            func.coalesce(func.sum(PurchaseOrderLine.quantity_received *
                                   PurchaseOrderLine.unit_price), 0)).join(
            PurchaseOrder, PurchaseOrderLine.po_id == PurchaseOrder.id).filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status != 'canceled').scalar()

        rows = db.session.query(
            Supplier.name, func.coalesce(func.sum(PurchaseOrder.total_amount), 0)).join(
            PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id).filter(
            PurchaseOrder.company_id == company_id,
            PurchaseOrder.status != 'canceled').group_by(Supplier.name).order_by(
            func.sum(PurchaseOrder.total_amount).desc()).limit(5).all()
        top_suppliers = [{'name': n, 'value': _f(v)} for n, v in rows]

        return {
            'pr_count': pr_count,
            'po_count': po_count,
            'gr_count': gr_count,
            'po_value': float(po_value),
            'received_value': _f(received),
            'open_pos': open_pos,
            'outstanding': float(po_value) - _f(received),
            'top_suppliers': top_suppliers,
        }

    def accounting(self, company_id):
        collected = self._cash_collected(company_id)
        booked = self._booked_total(company_id)

        advance = db.session.query(
            func.coalesce(func.sum(PaymentReport.advance_amount), 0)).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.payment_type == 'advance',
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False).scalar()
        final = db.session.query(
            func.coalesce(func.sum(PaymentReport.remaining_amount), 0)).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.payment_type == 'final',
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False).scalar()

        pending = db.session.query(
            func.count(PaymentReport.id), func.coalesce(func.sum(PaymentReport.amount), 0)).filter(
            PaymentReport.company_id == company_id,
            PaymentReport.is_confirmed == False,
            PaymentReport.is_canceled == False).one()

        return {
            'cash_in': collected,
            'booked_value': booked,
            'receivable': max(booked - collected, 0.0),
            'advance_collected': _f(advance),
            'final_collected': _f(final),
            'pending_count': pending[0] or 0,
            'pending_amount': _f(pending[1]),
        }

    def dashboard(self, company_id):
        return {
            'sales': self.sales(company_id),
            'purchasing': self.purchasing(company_id),
            'accounting': self.accounting(company_id),
        }
