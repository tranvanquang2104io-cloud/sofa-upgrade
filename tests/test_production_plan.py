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
