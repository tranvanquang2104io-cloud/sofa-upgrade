# -*- coding: utf-8 -*-
"""Reset a company's MANUAL business data, keeping seed/config.

Deletes (per company, FK-safe order): production plans + items + material lines,
material norms, generated documents, payment reports, handover records, contracts,
quotations, lifecycle statuses, orders, material stock, materials, suppliers,
customers.

KEEPS: company, stores, users, material categories, material units, extension
field configs, document templates.

Usage:
    venv/Scripts/python.exe scripts/reset_company_data.py NGOCHAN --yes
Idempotent (safe to re-run). Returns a dict of deleted counts.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def reset_company_data(company_id):
    """Delete all manual business data for one company. Caller commits.
    Returns {table: n_deleted}."""
    from app.config import db
    from app.models.models import (
        Order, Customer, Material, MaterialStock, Supplier,
        ProductionPlan, ProductionPlanItem, ProductionMaterialLine, MaterialNorm,
        Document, Quotation, Contract, HandoverRecord, PaymentReport, LifecycleStatus,
        PurchaseOrder, PurchaseOrderLine, GoodsReceipt, GoodsReceiptLine,
        PurchaseRequisition, PurchaseRequisitionLine,
    )

    order_ids = [o.id for o in Order.query.filter_by(company_id=company_id).all()]
    plan_ids = [p.id for p in ProductionPlan.query.filter_by(company_id=company_id).all()]
    po_ids = [p.id for p in PurchaseOrder.query.filter_by(company_id=company_id).all()]
    gr_ids = [g.id for g in GoodsReceipt.query.filter_by(company_id=company_id).all()]
    pr_ids = [p.id for p in PurchaseRequisition.query.filter_by(company_id=company_id).all()]
    counts = {}

    def _del(model, crit):
        counts[model.__tablename__] = crit.delete(synchronize_session=False)

    # 0. Procurement (children → GR/PO/PR). GR & PO reference PR, so drop them first.
    if gr_ids:
        _del(GoodsReceiptLine, GoodsReceiptLine.query.filter(GoodsReceiptLine.gr_id.in_(gr_ids)))
    if po_ids:
        _del(PurchaseOrderLine, PurchaseOrderLine.query.filter(PurchaseOrderLine.po_id.in_(po_ids)))
    _del(GoodsReceipt, GoodsReceipt.query.filter_by(company_id=company_id))
    _del(PurchaseOrder, PurchaseOrder.query.filter_by(company_id=company_id))
    if pr_ids:
        _del(PurchaseRequisitionLine, PurchaseRequisitionLine.query.filter(
            PurchaseRequisitionLine.pr_id.in_(pr_ids)))
    _del(PurchaseRequisition, PurchaseRequisition.query.filter_by(company_id=company_id))

    # 1. Production (children → plan)
    if plan_ids:
        _del(ProductionMaterialLine, ProductionMaterialLine.query.filter(
            ProductionMaterialLine.plan_id.in_(plan_ids)))
        _del(ProductionPlanItem, ProductionPlanItem.query.filter(
            ProductionPlanItem.plan_id.in_(plan_ids)))
    _del(ProductionPlan, ProductionPlan.query.filter_by(company_id=company_id))
    _del(MaterialNorm, MaterialNorm.query.filter_by(company_id=company_id))

    # 2. Order-scoped documents & sub-records (contracts before quotations: FK)
    _del(Document, Document.query.filter_by(company_id=company_id))
    if order_ids:
        _del(PaymentReport, PaymentReport.query.filter(PaymentReport.order_id.in_(order_ids)))
        _del(HandoverRecord, HandoverRecord.query.filter(HandoverRecord.order_id.in_(order_ids)))
        _del(Contract, Contract.query.filter(Contract.order_id.in_(order_ids)))
        _del(Quotation, Quotation.query.filter(Quotation.order_id.in_(order_ids)))
        _del(LifecycleStatus, LifecycleStatus.query.filter(LifecycleStatus.order_id.in_(order_ids)))

    # 3. Orders
    _del(Order, Order.query.filter_by(company_id=company_id))

    # 4. Materials & suppliers & customers
    _del(MaterialStock, MaterialStock.query.filter_by(company_id=company_id))
    _del(Material, Material.query.filter_by(company_id=company_id))
    _del(Supplier, Supplier.query.filter_by(company_id=company_id))
    _del(Customer, Customer.query.filter_by(company_id=company_id))

    db.session.commit()
    return counts


def main():
    from app import create_app
    from app.models.models import Company
    if '--yes' not in sys.argv:
        print('Refusing to run without --yes (destructive).')
        sys.exit(2)
    code = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
    if not code:
        print('Usage: reset_company_data.py <COMPANY_CODE> --yes')
        sys.exit(2)
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        co = Company.query.filter_by(company_code=code).first()
        if not co:
            print(f'Company {code} not found'); sys.exit(1)
        counts = reset_company_data(co.id)
        for t, n in counts.items():
            print(f'  deleted {n:>4}  {t}')
        print(f'Done: reset manual data for {code}')


if __name__ == '__main__':
    main()
