"""End-to-end operational loop:
order → production plan → issue (deduct stock) → shortage → PR → PO → GR
(replenish stock) → issue succeeds. Proves the closed procurement/inventory cycle.
"""
from datetime import date
from decimal import Decimal


def test_operational_cycle_closes(app, seed):
    from app.config import db
    from app.models.models import (Material, MaterialStock, Supplier, Order, Contract,
                                   ProductionPlan, ProductionPlanItem, ProductionMaterialLine,
                                   PurchaseOrder)
    from app.services.services import ProductionPlanService
    from app.services.procurement_service import ProcurementService
    cid, sid = seed['company_id'], seed['store_id']
    pp = ProductionPlanService()
    proc = ProcurementService()

    with app.app_context():
        sup = Supplier(company_id=cid, supplier_code='NCC-1', name='NCC Alpha')
        db.session.add(sup); db.session.flush()
        m = Material(company_id=cid, material_code='M1', name='Vải nỉ', unit_price=Decimal('100'),
                     min_stock_level=Decimal('10'), supplier_id=sup.id)
        db.session.add(m); db.session.flush()
        db.session.add(MaterialStock(company_id=cid, material_id=m.id, store_id=sid,
                                     current_quantity=Decimal('20')))   # only 20 on hand
        o = Order(company_id=cid, store_id=sid, customer_id=seed['customer_id'],
                  order_code='LOOP-O1', title='Bộ sofa')
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, company_id=cid, contract_number='LOOP-C1',
                     contract_date=date(2026, 7, 30), contract_value=Decimal('1'))
        db.session.add(c); db.session.flush()
        plan = ProductionPlan(company_id=cid, order_id=o.id, contract_id=c.id,
                              plan_number='LOOP-KH1', status='approved')
        db.session.add(plan); db.session.flush()
        it = ProductionPlanItem(plan_id=plan.id, source_name='Sofa', quantity=1)
        db.session.add(it); db.session.flush()
        db.session.add(ProductionMaterialLine(plan_id=plan.id, plan_item_id=it.id,
                                              material_id=m.id, quantity_required=Decimal('30'),
                                              quantity_issued=Decimal('0'), unit='m²'))
        db.session.commit()
        mid, pid = str(m.id), str(plan.id)

    # 1) Issue for production → SHORTAGE (need 30, have 20): nothing deducted
    with app.app_context():
        plan = ProductionPlan.query.get(pid)
        shortages = pp.issue_materials(plan)
        assert shortages and shortages[0]['material_id'] == mid
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=sid).first()
        assert float(st.current_quantity) == 20.0        # unchanged

    # 2) PR → PO (suggest 30 - 20 + 10 = 20)
    with app.app_context():
        pos = proc.create_pos_from_suggestions(cid, store_id=sid)
        assert len(pos) == 1 and float(pos[0].lines[0].quantity_ordered) == 20.0
        poid, lid = str(pos[0].id), str(pos[0].lines[0].id)

    # 3) PO → GR (receive 20) → stock 20 → 40
    with app.app_context():
        po = PurchaseOrder.query.get(poid)
        proc.transition(po, 'submit')
        proc.receive(po, {lid: 20}, store_id=sid)
        assert po.status == 'received'
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=sid).first()
        assert float(st.current_quantity) == 40.0        # replenished

    # 4) Issue again → now enough → deduct 30 → stock 10, plan processing
    with app.app_context():
        plan = ProductionPlan.query.get(pid)
        assert pp.issue_materials(plan) == []            # no shortage
        assert plan.status == 'processing'
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=sid).first()
        assert float(st.current_quantity) == 10.0        # 40 - 30 → back at min level
