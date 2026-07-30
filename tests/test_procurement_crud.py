"""HTTP CRUD for PR/PO/GR documents (create-form → save, edit, lifecycle, GR)."""
from decimal import Decimal


def _setup(app, seed):
    from app.config import db
    from app.models.models import Material, MaterialStock, Supplier
    cid, sid = seed['company_id'], seed['store_id']
    with app.app_context():
        sup = Supplier(company_id=cid, supplier_code='S1', name='NCC 1')
        db.session.add(sup); db.session.flush()
        m1 = Material(company_id=cid, material_code='M1', name='Vải', unit_price=Decimal('100'), supplier_id=sup.id)
        m2 = Material(company_id=cid, material_code='M2', name='Mút', unit_price=Decimal('50'), supplier_id=sup.id)
        db.session.add_all([m1, m2]); db.session.flush()
        db.session.add(MaterialStock(company_id=cid, material_id=m1.id, store_id=sid, current_quantity=Decimal('0')))
        db.session.commit()
        return str(m1.id), str(m2.id)


def test_pr_po_gr_crud_over_http(app, client, login, seed):
    from app.models.models import (PurchaseRequisition, PurchaseOrder, GoodsReceipt, MaterialStock)
    m1, m2 = _setup(app, seed)
    login(username='admin')

    # --- PR: create form + save ---
    assert client.get('/requisitions/create').status_code == 200
    client.post('/requisitions/create', data={
        'title': 'Dự phòng', 'line_material_id[]': [m1, m2],
        'line_quantity[]': ['20', '10'], 'line_unit[]': ['m²', 'kg'],
    }, follow_redirects=True)
    with app.app_context():
        pr = PurchaseRequisition.query.filter_by(company_id=seed['company_id']).first()
        assert pr and len(pr.lines) == 2
        prid = str(pr.id)
    assert client.get(f'/requisitions/{prid}').status_code == 200

    # --- PR: edit (replace lines), then submit → approve → convert ---
    client.post(f'/requisitions/{prid}/edit', data={
        'line_material_id[]': [m1], 'line_quantity[]': ['25'], 'line_unit[]': ['m²'],
    }, follow_redirects=True)
    with app.app_context():
        assert len(PurchaseRequisition.query.get(prid).lines) == 1
    client.post(f'/requisitions/{prid}/status/submit', follow_redirects=True)
    client.post(f'/requisitions/{prid}/status/approve', follow_redirects=True)
    client.post(f'/requisitions/{prid}/convert', follow_redirects=True)
    with app.app_context():
        pr = PurchaseRequisition.query.get(prid)
        assert pr.status == 'converted'
        po = PurchaseOrder.query.filter_by(pr_id=pr.id).first()
        assert po is not None and po.pr_id == pr.id
        poid = str(po.id); lid = str(po.lines[0].id)

    # --- PO: view + receive (GR) → stock up ---
    assert client.get(f'/purchase-orders/{poid}').status_code == 200
    client.post(f'/purchase-orders/{poid}/status/submit', follow_redirects=True)
    client.post(f'/purchase-orders/{poid}/receive',
                data={f'qty_{lid}': '25', 'store_id': seed['store_id']}, follow_redirects=True)
    with app.app_context():
        assert PurchaseOrder.query.get(poid).status == 'received'
        st = MaterialStock.query.filter_by(material_id=m1, store_id=seed['store_id']).first()
        assert float(st.current_quantity) == 25.0
        gr = GoodsReceipt.query.filter_by(company_id=seed['company_id']).first()
        grid = str(gr.id)
    # --- GR management pages ---
    assert client.get('/goods-receipts').status_code == 200
    assert client.get(f'/goods-receipts/{grid}').status_code == 200


def test_po_document_create_and_edit_over_http(app, client, login, seed):
    from app.models.models import PurchaseOrder
    m1, m2 = _setup(app, seed)
    login(username='admin')
    assert client.get('/purchase-orders/create').status_code == 200
    client.post('/purchase-orders/create', data={
        'vat_rate': '8', 'line_material_id[]': [m1, m2],
        'line_quantity[]': ['10', '4'], 'line_unit[]': ['m²', 'kg'], 'line_price[]': ['100', ''],
    }, follow_redirects=True)
    with app.app_context():
        po = PurchaseOrder.query.filter_by(company_id=seed['company_id']).first()
        assert po and len(po.lines) == 2 and po.pr_id is None   # standalone PO
        assert float(po.subtotal) == 10*100 + 4*50              # m2 price defaulted to 50
        poid = str(po.id)
    # edit form loads + save replaces lines
    assert client.get(f'/purchase-orders/{poid}/edit').status_code == 200
    client.post(f'/purchase-orders/{poid}/edit', data={
        'vat_rate': '0', 'line_material_id[]': [m1], 'line_quantity[]': ['3'], 'line_price[]': ['100'],
    }, follow_redirects=True)
    with app.app_context():
        po = PurchaseOrder.query.get(poid)
        assert len(po.lines) == 1 and float(po.total_amount) == 300.0
