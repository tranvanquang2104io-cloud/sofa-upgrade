"""reset_company_data deletes manual business data, keeps seed/config."""
import os
import sys
from datetime import date


def _mk_business_data(cid, sid, cust_id):
    """Create an order + material + supplier + production plan for the company."""
    from app.config import db
    from app.models.models import (
        Order, Material, Supplier, MaterialStock, MaterialCategory, MaterialUnit,
        ProductionPlan, ProductionPlanItem, ProductionMaterialLine, Quotation,
        Contract, LifecycleStatus,
    )
    cat = MaterialCategory(company_id=cid, name="Vải bọc")
    unit = MaterialUnit(company_id=cid, name="m²")
    sup = Supplier(company_id=cid, supplier_code="NCC-001", name="NCC Test")
    db.session.add_all([cat, unit, sup]); db.session.flush()
    mat = Material(company_id=cid, material_code="VT-001", name="Vải nỉ",
                   category_id=cat.id, unit_id=unit.id, supplier_id=sup.id)
    db.session.add(mat); db.session.flush()
    db.session.add(MaterialStock(company_id=cid, material_id=mat.id, current_quantity=10))
    order = Order(company_id=cid, store_id=sid, customer_id=cust_id,
                  order_code="ORD-001", title="Bọc ghế", total_amount=1000)
    db.session.add(order); db.session.flush()
    db.session.add(LifecycleStatus(order_id=order.id))
    q = Quotation(order_id=order.id, company_id=cid, quotation_number="BG-001",
                  quotation_date=date.today(), total_amount=1000)
    db.session.add(q); db.session.flush()
    c = Contract(order_id=order.id, company_id=cid, quotation_id=q.id,
                 contract_number="HD-001", contract_date=date.today(), contract_value=1000)
    db.session.add(c); db.session.flush()
    plan = ProductionPlan(company_id=cid, order_id=order.id, contract_id=c.id,
                          plan_number="KH-001", status="draft")
    db.session.add(plan); db.session.flush()
    item = ProductionPlanItem(plan_id=plan.id, source_name="Ghế", quantity=1)
    db.session.add(item); db.session.flush()
    db.session.add(ProductionMaterialLine(plan_id=plan.id, plan_item_id=item.id,
                                          material_id=mat.id, quantity_required=5))
    db.session.commit()


def test_reset_keeps_seed_removes_business(app, seed):
    sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))
    from reset_company_data import reset_company_data
    from app.models.models import (
        Order, Material, Supplier, Customer, ProductionPlan, MaterialCategory,
        MaterialUnit, User, Store, Contract, Quotation,
    )
    cid = seed["company_id"]
    with app.app_context():
        _mk_business_data(cid, seed["store_id"], seed["customer_id"])
        assert Order.query.filter_by(company_id=cid).count() == 1
        assert ProductionPlan.query.filter_by(company_id=cid).count() == 1

        reset_company_data(cid)

        # business data gone
        for m in (Order, Material, Supplier, Customer, ProductionPlan, Contract, Quotation):
            assert m.query.filter_by(company_id=cid).count() == 0, m.__name__
        # seed/config kept
        assert MaterialCategory.query.filter_by(company_id=cid).count() == 1
        assert MaterialUnit.query.filter_by(company_id=cid).count() == 1
        assert User.query.filter_by(company_id=cid).count() == 2
        assert Store.query.filter_by(company_id=cid).count() == 1

        # idempotent
        again = reset_company_data(cid)
        assert all(v == 0 for v in again.values())
