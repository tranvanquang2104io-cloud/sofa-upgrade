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

        # Booked sales = signed, non-canceled contracts
        booked = db.session.query(func.coalesce(func.sum(Contract.contract_value), 0)).join(
            Order, Contract.order_id == Order.id).filter(
            Order.company_id == company_id, Contract.is_signed == True,
            Contract.is_canceled == False).scalar()

        collected = self._cash_collected(company_id)

        # Top customers by booked contract value
        rows = db.session.query(
            Customer.name, func.coalesce(func.sum(Contract.contract_value), 0).label('v')).join(
            Order, Order.customer_id == Customer.id).join(
            Contract, Contract.order_id == Order.id).filter(
            Order.company_id == company_id, Contract.is_signed == True,
            Contract.is_canceled == False).group_by(Customer.name).order_by(
            func.sum(Contract.contract_value).desc()).limit(5).all()
        top_customers = [{'name': n, 'value': _f(v)} for n, v in rows]

        return {
            'orders_total': orders_total,
            'completed': completed,
            'in_progress': in_progress,
            'booked_value': _f(booked),
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
        booked = db.session.query(func.coalesce(func.sum(Contract.contract_value), 0)).join(
            Order, Contract.order_id == Order.id).filter(
            Order.company_id == company_id, Contract.is_signed == True,
            Contract.is_canceled == False).scalar()

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
            'booked_value': _f(booked),
            'receivable': max(_f(booked) - collected, 0.0),
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
