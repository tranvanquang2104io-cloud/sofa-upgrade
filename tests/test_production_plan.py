"""Feature 2 — production planning: plan creation, norms, inventory, low-stock."""
from datetime import date
from decimal import Decimal


def _mk_contract(app, seed, items, sign=False):
    from app.config import db
    from app.models.models import Order, Contract
    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="PP-O1", title="SX")
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, contract_number="PP-C1", contract_date=date(2026, 7, 27),
                     contract_value=Decimal("1000000"), items=items, is_signed=sign)
        db.session.add(c); db.session.commit()
        return str(o.id), str(c.id)


def _mk_material(app, seed, code, stock_qty, min_level=0, store_id=None):
    from app.config import db
    from app.models.models import Material, MaterialStock
    with app.app_context():
        m = Material(company_id=seed["company_id"], material_code=code, name=code,
                     min_stock_level=Decimal(str(min_level)))
        db.session.add(m); db.session.flush()
        st = MaterialStock(material_id=m.id, company_id=seed["company_id"],
                           store_id=store_id or seed["store_id"],
                           current_quantity=Decimal(str(stock_qty)))
        db.session.add(st); db.session.commit()
        return str(m.id)


def test_create_from_contract_creates_plan_and_items(app, seed):
    from app.config import db
    from app.models.models import Contract, ProductionPlan
    from app.services.services import ProductionPlanService
    _mk_contract(app, seed, [{"name": "Sofa 3 chỗ", "unit": "Bộ", "quantity": 2, "unit_price": 5, "total": 10},
                             {"name": "Ghế đơn", "unit": "Cái", "quantity": 1, "unit_price": 3, "total": 3}])
    with app.app_context():
        c = Contract.query.filter_by(contract_number="PP-C1").first()
        plan = ProductionPlanService().create_from_contract(c)
        assert plan.status == "draft"
        assert len(plan.items) == 2
        # Idempotent
        assert ProductionPlanService().create_from_contract(c).id == plan.id


def test_norm_suggestion_and_save(app, seed):
    from app.config import db
    from app.models.models import Contract, MaterialNorm, ProductionPlan
    from app.services.services import ProductionPlanService
    mat = _mk_material(app, seed, "DA-01", stock_qty=100)
    with app.app_context():
        db.session.add(MaterialNorm(company_id=seed["company_id"], product_key="sofa 3 chỗ",
                                    material_id=mat, quantity_per_unit=Decimal("4"), unit="m2"))
        db.session.commit()
    _mk_contract(app, seed, [{"name": "Sofa 3 chỗ", "unit": "Bộ", "quantity": 2, "total": 10}])
    with app.app_context():
        c = Contract.query.filter_by(contract_number="PP-C1").first()
        plan = ProductionPlanService().create_from_contract(c)
        lines = plan.material_lines
        assert len(lines) == 1
        assert float(lines[0].quantity_required) == 8.0  # 4 * 2


def test_issue_materials_deducts_then_blocks_on_shortage(app, seed):
    from app.config import db
    from app.models.models import Contract, MaterialStock, ProductionPlan, ProductionMaterialLine
    from app.services.services import ProductionPlanService
    mat = _mk_material(app, seed, "MUT-01", stock_qty=10)
    oid, cid = _mk_contract(app, seed, [{"name": "X", "unit": "c", "quantity": 1, "total": 1}])
    svc = ProductionPlanService()
    with app.app_context():
        c = Contract.query.get(cid)
        plan = svc.create_from_contract(c)
        db.session.add(ProductionMaterialLine(plan_id=plan.id, material_id=mat,
                                              quantity_required=Decimal("6"), unit="kg"))
        db.session.commit()
        pid = str(plan.id)
    with app.app_context():
        plan = ProductionPlan.query.get(pid)
        assert svc.issue_materials(plan) == []          # enough -> deducted
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mat).first()
        assert float(st.current_quantity) == 4.0        # 10 - 6
    # add another line needing more than remaining -> shortage, no deduction
    with app.app_context():
        plan = ProductionPlan.query.get(pid)
        db.session.add(ProductionMaterialLine(plan_id=plan.id, material_id=mat,
                                              quantity_required=Decimal("99"), unit="kg"))
        db.session.commit()
        plan = ProductionPlan.query.get(pid)
        shortages = svc.issue_materials(plan)
        assert shortages and shortages[0]["material_id"] == mat
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mat).first()
        assert float(st.current_quantity) == 4.0        # unchanged


def test_low_stock_materials(app, seed):
    from app.services.services import ProductionPlanService
    _mk_material(app, seed, "LOW-01", stock_qty=2, min_level=5)   # below
    _mk_material(app, seed, "OK-01", stock_qty=50, min_level=5)   # ok
    with app.app_context():
        low = ProductionPlanService().low_stock_materials(seed["company_id"])
        codes = {m.material_code for m in low}
        assert "LOW-01" in codes and "OK-01" not in codes


def test_plan_page_and_low_stock_render(login, client, seeded_order):
    login(username="admin")
    assert client.get(f"/orders/{seeded_order['order_id']}/production-plan").status_code == 200
    assert client.get("/materials/low-stock").status_code == 200


def test_plan_routes_add_and_issue(app, client, login, seed):
    from app.config import db
    from app.models.models import Order, Contract, MaterialStock, ProductionPlan
    from app.services.services import ProductionPlanService
    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="PR-1", title="x")
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, contract_number="PR-C1", contract_date=date(2026, 7, 27),
                     contract_value=Decimal("1"), items=[{"name": "A", "unit": "c", "quantity": 1, "total": 1}])
        db.session.add(c); db.session.commit()
        pid = str(ProductionPlanService().create_from_contract(c).id)
    mat = _mk_material(app, seed, "RT-01", stock_qty=10)
    login(username="admin")
    client.post(f"/production-plan/{pid}/materials",
                data={"material_id": mat, "quantity_required": "3", "unit": "kg"}, follow_redirects=True)
    with app.app_context():
        assert len(ProductionPlan.query.get(pid).material_lines) == 1
    client.post(f"/production-plan/{pid}/issue", follow_redirects=True)
    with app.app_context():
        st = MaterialStock.query.filter_by(material_id=mat).first()
        assert float(st.current_quantity) == 7.0


def test_plan_lifecycle_transitions(app, seed):
    import pytest
    from app.models.models import Contract, ProductionPlan
    from app.services.services import ProductionPlanService
    _mk_contract(app, seed, [{"name": "X", "unit": "c", "quantity": 1, "total": 1}])
    svc = ProductionPlanService()
    with app.app_context():
        c = Contract.query.filter_by(contract_number="PP-C1").first()
        plan = svc.create_from_contract(c)
        pid = str(plan.id)
        assert plan.status == "draft"
        with pytest.raises(ValueError):          # cannot jump to finish
            svc.transition(plan, "finish")
    flow = [("approve", "approved"), ("start", "processing"), ("complete", "completed"),
            ("submit", "validating"), ("reject", "rejected"), ("start", "processing"),
            ("complete", "completed"), ("submit", "validating"), ("validate", "validated"),
            ("finish", "finished")]
    for action, expected in flow:
        with app.app_context():
            plan = ProductionPlan.query.get(pid)
            svc.transition(plan, action)
            assert plan.status == expected


def test_plan_page_ui_status_and_print(app, client, login, seed):
    from app.config import db
    from app.models.models import Order, Contract, ProductionPlan
    from app.services.services import ProductionPlanService
    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="PPUI-1", title="x")
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, contract_number="PPUI-C1", contract_date=date(2026, 7, 27),
                     contract_value=Decimal("1"), items=[{"name": "A", "unit": "c", "quantity": 1, "total": 1}])
        db.session.add(c); db.session.commit()
        plan = ProductionPlanService().create_from_contract(c)
        pid, oid = str(plan.id), str(o.id)
    login(username="admin")
    r = client.get(f"/orders/{oid}/production-plan")
    assert r.status_code == 200 and "Duyệt kế hoạch".encode() in r.data
    client.post(f"/production-plan/{pid}/status/approve", follow_redirects=True)
    with app.app_context():
        assert ProductionPlan.query.get(pid).status == "approved"
    rp = client.get(f"/production-plan/{pid}/print")
    assert rp.status_code == 200 and rp.data[:2] == b"PK"   # docx = zip
