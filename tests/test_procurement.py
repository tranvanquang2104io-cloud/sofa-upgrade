"""Feature 3 — procurement loop: PR(suggestions) → PO → GR increases stock."""
from datetime import date
from decimal import Decimal


def _seed_need(app, seed):
    """One material (stock 10, min 5, supplier) with a plan needing 30 → shortfall 25."""
    from app.config import db
    from app.models.models import (Material, MaterialStock, Supplier, Order, Contract,
                                   ProductionPlan, ProductionPlanItem, ProductionMaterialLine)
    cid, sid = seed['company_id'], seed['store_id']
    with app.app_context():
        sup = Supplier(company_id=cid, supplier_code='NCC-1', name='NCC Alpha')
        db.session.add(sup); db.session.flush()
        m = Material(company_id=cid, material_code='M1', name='Vải nỉ', unit_price=Decimal('100'),
                     min_stock_level=Decimal('5'), supplier_id=sup.id)
        db.session.add(m); db.session.flush()
        db.session.add(MaterialStock(company_id=cid, material_id=m.id, store_id=None,
                                     current_quantity=Decimal('10')))
        o = Order(company_id=cid, store_id=sid, customer_id=seed['customer_id'],
                  order_code='PC-O1', title='x')
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, company_id=cid, contract_number='PC-C1',
                     contract_date=date(2026, 7, 29), contract_value=Decimal('1'))
        db.session.add(c); db.session.flush()
        plan = ProductionPlan(company_id=cid, order_id=o.id, contract_id=c.id,
                              plan_number='PC-KH1', status='approved')
        db.session.add(plan); db.session.flush()
        it = ProductionPlanItem(plan_id=plan.id, source_name='Sofa', quantity=1)
        db.session.add(it); db.session.flush()
        db.session.add(ProductionMaterialLine(plan_id=plan.id, plan_item_id=it.id,
                                              material_id=m.id, quantity_required=Decimal('30'),
                                              quantity_issued=Decimal('0'), unit='m²'))
        db.session.commit()
        return str(m.id)


def test_full_loop_pr_po_gr_increases_stock(app, seed):
    from app.services.procurement_service import ProcurementService
    from app.models.models import PurchaseOrder, MaterialStock, GoodsReceipt
    mid = _seed_need(app, seed)
    svc = ProcurementService()
    with app.app_context():
        # PR → PO
        pos = svc.create_pos_from_suggestions(seed['company_id'])
        assert len(pos) == 1
        po = PurchaseOrder.query.get(pos[0].id)
        assert po.status == 'draft'
        assert len(po.lines) == 1
        line = po.lines[0]
        assert float(line.quantity_ordered) == 25.0     # 30 - 10 + 5
        assert float(po.total_amount) == 2500.0          # 25 * 100 (vat 0)
        pid, lid = str(po.id), str(line.id)

    with app.app_context():
        po = PurchaseOrder.query.get(pid)
        svc.transition(po, 'submit')                     # gửi NCC
        assert po.status == 'ordered'
        # receive 10 → partial, stock 10→20
        gr, warns = svc.receive(po, {lid: 10})
        assert po.status == 'partial'
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=None).first()
        assert float(st.current_quantity) == 20.0        # 10 + 10

    with app.app_context():
        po = PurchaseOrder.query.get(pid)
        svc.receive(po, {lid: 15})                        # receive rest → received
        assert po.status == 'received'
        assert float(po.lines[0].quantity_received) == 25.0
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=None).first()
        assert float(st.current_quantity) == 35.0        # 20 + 15
        assert GoodsReceipt.query.filter_by(company_id=seed['company_id']).count() == 2


def test_loop_through_http_routes(app, client, login, seed):
    from app.models.models import PurchaseOrder, MaterialStock
    mid = _seed_need(app, seed)
    login(username='admin')
    # PR page renders
    assert client.get('/materials/purchase-suggestions').status_code == 200
    # PR → PO
    client.post('/purchase-orders/from-suggestions', follow_redirects=True)
    with app.app_context():
        po = PurchaseOrder.query.filter_by(company_id=seed['company_id']).first()
        pid = str(po.id); lid = str(po.lines[0].id)
    assert client.get('/purchase-orders').status_code == 200
    assert client.get(f'/purchase-orders/{pid}').status_code == 200
    # submit + print
    client.post(f'/purchase-orders/{pid}/status/submit', follow_redirects=True)
    rp = client.get(f'/purchase-orders/{pid}/print')
    assert rp.status_code == 200 and rp.data[:2] == b'PK'
    # receive → stock up
    client.post(f'/purchase-orders/{pid}/receive', data={f'qty_{lid}': '25'}, follow_redirects=True)
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mid, store_id=None).first()
        assert float(st.current_quantity) == 35.0   # 10 + 25
        assert PurchaseOrder.query.get(pid).status == 'received'


def test_cannot_receive_before_submit_or_edit_after_submit(app, seed):
    import pytest
    from app.services.procurement_service import ProcurementService
    from app.models.models import PurchaseOrder
    _seed_need(app, seed)
    svc = ProcurementService()
    with app.app_context():
        po = svc.create_pos_from_suggestions(seed['company_id'])[0]
        pid = str(po.id)
    with app.app_context():
        po = PurchaseOrder.query.get(pid)
        with pytest.raises(ValueError):        # draft → cannot receive
            svc.receive(po, {})
        svc.transition(po, 'submit')
        with pytest.raises(ValueError):        # ordered → cannot add line
            svc.add_line(po, po.lines[0].material_id, 5)
