"""PR document CRUD + convert→PO, and document-style PO create/update."""
from decimal import Decimal


def _materials(app, seed):
    from app.config import db
    from app.models.models import Material, Supplier
    cid = seed['company_id']
    with app.app_context():
        s1 = Supplier(company_id=cid, supplier_code='S1', name='NCC 1')
        s2 = Supplier(company_id=cid, supplier_code='S2', name='NCC 2')
        db.session.add_all([s1, s2]); db.session.flush()
        m1 = Material(company_id=cid, material_code='M1', name='Vải', unit_price=Decimal('100'), supplier_id=s1.id)
        m2 = Material(company_id=cid, material_code='M2', name='Mút', unit_price=Decimal('50'), supplier_id=s2.id)
        db.session.add_all([m1, m2]); db.session.commit()
        return str(m1.id), str(m2.id)


def test_pr_crud_and_convert_groups_by_supplier(app, seed):
    from app.services.requisition_service import RequisitionService
    from app.models.models import PurchaseRequisition, PurchaseOrder
    m1, m2 = _materials(app, seed)
    svc = RequisitionService()
    with app.app_context():
        # create (manual, no stock constraint)
        pr = svc.create_pr(seed['company_id'], {'title': 'Dự phòng vải mút'},
                           [{'material_id': m1, 'quantity': 20, 'unit': 'm²'},
                            {'material_id': m2, 'quantity': 10, 'unit': 'kg'}])
        prid = str(pr.id)
        assert pr.status == 'draft' and len(pr.lines) == 2
    with app.app_context():
        pr = PurchaseRequisition.query.get(prid)
        # edit: replace lines
        svc.update_pr(pr, {'title': 'Đổi'}, [{'material_id': m1, 'quantity': 30, 'unit': 'm²'}])
        assert len(pr.lines) == 1 and float(pr.lines[0].quantity) == 30.0
        # lifecycle
        svc.transition(pr, 'submit'); assert pr.status == 'submitted'
        svc.transition(pr, 'approve'); assert pr.status == 'approved'
    with app.app_context():
        pr = PurchaseRequisition.query.get(prid)
        # convert: 1 material from supplier S1 → 1 PO, PR converted
        pos = svc.convert_to_pos(pr)
        assert len(pos) == 1 and pos[0].pr_id == pr.id
        assert PurchaseRequisition.query.get(prid).status == 'converted'


def test_pr_convert_two_suppliers_two_pos(app, seed):
    from app.services.requisition_service import RequisitionService
    m1, m2 = _materials(app, seed)
    svc = RequisitionService()
    with app.app_context():
        pr = svc.create_pr(seed['company_id'], {},
                           [{'material_id': m1, 'quantity': 5}, {'material_id': m2, 'quantity': 7}])
        svc.transition(pr, 'submit'); svc.transition(pr, 'approve')
        pos = svc.convert_to_pos(pr)
        assert len(pos) == 2   # two suppliers → two POs


def test_po_document_create_update(app, seed):
    from app.services.procurement_service import ProcurementService
    from app.models.models import PurchaseOrder
    m1, m2 = _materials(app, seed)
    svc = ProcurementService()
    with app.app_context():
        po = svc.create_po(seed['company_id'], {'vat_rate': 8},
                           [{'material_id': m1, 'quantity': 10, 'unit_price': 100},
                            {'material_id': m2, 'quantity': 4}])   # m2 price defaults to 50
        pid = str(po.id)
        assert len(po.lines) == 2
        assert float(po.subtotal) == 10*100 + 4*50   # 1200
        assert float(po.total_amount) == 1200 + round(1200*8/100)  # +96 = 1296
    with app.app_context():
        po = PurchaseOrder.query.get(pid)
        svc.update_po(po, {'vat_rate': 0}, [{'material_id': m1, 'quantity': 3, 'unit_price': 100}])
        assert len(po.lines) == 1 and float(po.total_amount) == 300.0
