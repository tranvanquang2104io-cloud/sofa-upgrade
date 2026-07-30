"""Purchase (PO) suggestions: BOM explosion across active plans net of stock."""
from decimal import Decimal


def _seed(app, seed):
    from app.config import db
    from app.models.models import (Material, MaterialStock, Supplier, Order, Contract,
                                   ProductionPlan, ProductionPlanItem, ProductionMaterialLine)
    cid, sid = seed['company_id'], seed['store_id']
    with app.app_context():
        sup = Supplier(company_id=cid, supplier_code='NCC-1', name='NCC Alpha', phone='090', lead_time_days=5)
        db.session.add(sup); db.session.flush()

        def mat(code, stock, minlvl, price, supplier=None):
            m = Material(company_id=cid, material_code=code, name=code, unit_price=Decimal(str(price)),
                         min_stock_level=Decimal(str(minlvl)), supplier_id=supplier)
            db.session.add(m); db.session.flush()
            db.session.add(MaterialStock(company_id=cid, material_id=m.id, store_id=None,
                                         current_quantity=Decimal(str(stock))))
            return m

        m1 = mat('M1', stock=10, minlvl=5, price=100, supplier=sup.id)   # plan needs 30 → 25
        m2 = mat('M2', stock=100, minlvl=0, price=1, supplier=sup.id)    # no need, ok → excluded
        m3 = mat('M3', stock=2, minlvl=20, price=50, supplier=None)      # low stock → 18

        o = Order(company_id=cid, store_id=sid, customer_id=seed['customer_id'],
                  order_code='PO-O1', title='x')
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, company_id=cid, contract_number='PO-C1',
                     contract_date=__import__('datetime').date(2026, 7, 29), contract_value=Decimal('1'))
        db.session.add(c); db.session.flush()
        plan = ProductionPlan(company_id=cid, order_id=o.id, contract_id=c.id,
                              plan_number='PO-KH1', status='approved')
        db.session.add(plan); db.session.flush()
        it = ProductionPlanItem(plan_id=plan.id, source_name='Sofa', quantity=1)
        db.session.add(it); db.session.flush()
        db.session.add(ProductionMaterialLine(plan_id=plan.id, plan_item_id=it.id,
                                              material_id=m1.id, quantity_required=Decimal('30'),
                                              quantity_issued=Decimal('0'), unit='m²'))
        db.session.commit()


def test_purchase_suggestions_math_and_grouping(app, seed):
    from app.services.services import ProductionPlanService
    _seed(app, seed)
    with app.app_context():
        data = ProductionPlanService().purchase_suggestions(seed['company_id'])
        assert data['count'] == 2                      # M1 + M3 (M2 excluded)
        # flatten lines by material code
        lines = {ln['material'].material_code: ln for g in data['groups'] for ln in g['lines']}
        assert lines['M1']['suggested'] == 25.0        # 30 - 10 + 5
        assert lines['M1']['est_cost'] == 2500.0       # 25 * 100
        assert lines['M3']['suggested'] == 18.0        # 0 - 2 + 20 (low stock top-up)
        assert 'M2' not in lines
        assert data['total'] == 2500.0 + 900.0         # M1 2500 + M3 18*50=900
        # grouping: named supplier first, "no supplier" last
        assert data['groups'][0]['supplier'] is not None
        assert data['groups'][-1]['supplier'] is None


def test_purchase_suggestions_page_renders(app, client, login, seed):
    _seed(app, seed)
    login(username='admin')
    r = client.get('/materials/purchase-suggestions')
    assert r.status_code == 200
    assert 'Đề xuất mua hàng'.encode() in r.data
    assert b'NCC Alpha' in r.data
