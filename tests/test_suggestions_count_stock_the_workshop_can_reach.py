"""Purchase suggestions must count the stock the workshop can actually use.

`purchase_suggestions` compared what the plans need against `m.total_stock` —
the sum across every branch — while issuing draws from one branch only. So a
workshop needing 20m of fabric, holding none, while 50m sits at the showroom,
was told to buy nothing. The shortage then appears on the day of cutting, which
is the one day it cannot be fixed.

The fabric at the showroom is not unavailable in principle — somebody can drive
it over — but it is not available to this plan without a transfer that has to
be decided and documented. Counting it as if it were already at the workshop is
the same error as the issuing fallback that silently drew from the company
warehouse: it treats an undocumented move as a fact.

So requirement is aggregated per production site and compared against the stock
at that site. The output still groups by supplier — this is about the
arithmetic, not the screen — and a company with one location gets exactly the
same numbers as before, because there the two sums are the same sum.
"""
import pytest


@pytest.fixture()
def workshop_and_showroom(app, seed):
    from app.config import db
    from app.models import Order, Store
    from app.models.models import (
        Material, MaterialStock, ProductionMaterialLine, ProductionPlan,
        Supplier,
    )

    with app.app_context():
        workshop = Store(company_id=seed['company_id'], store_code='XUONG-S',
                         name='Xưởng Hoài Đức', is_active=True)
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-S', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add_all([workshop, supplier])
        db.session.flush()
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-SG', name='Vải bố',
                            unit_price=215_000, supplier_id=supplier.id,
                            is_active=True)
        db.session.add(material)
        db.session.flush()

        # 50m at the showroom, none at the workshop.
        db.session.add_all([
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id,
                          store_id=seed['store_id'], current_quantity=50),
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id,
                          store_id=workshop.id, current_quantity=0),
        ])

        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-SG',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-SG',
                              production_store_id=workshop.id,
                              status=ProductionPlan.STATUS_APPROVED)
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=material.id,
            quantity_required=20, unit='m'))
        db.session.commit()
        return {**seed, 'workshop_id': str(workshop.id),
                'material_id': str(material.id)}


def _suggested(result, material_id):
    """Read the shape the service actually returns.

    Groups hold `lines`, each with a `material` object and a `suggested`
    figure — not `items` and `suggest`, which is what the first version of this
    helper guessed and then failed on, saying nothing about branches.
    """
    for group in result['groups']:
        for line in group['lines']:
            if str(line['material'].id) == material_id:
                return float(line['suggested'])
    return 0.0


def test_fabric_at_another_branch_does_not_cancel_the_suggestion(
        app, workshop_and_showroom):
    from app.services.services import ProductionPlanService

    with app.app_context():
        result = ProductionPlanService().purchase_suggestions(
            workshop_and_showroom['company_id'])
        assert _suggested(result, workshop_and_showroom['material_id']) == 20, (
            'the workshop needs 20m and holds none, but 50m at the showroom '
            'cancelled the suggestion — the shortage now appears on the day '
            'of cutting')


def test_stock_at_the_workshop_itself_does_cancel_it(app,
                                                     workshop_and_showroom):
    """The fix must not simply stop counting stock."""
    from app.config import db
    from app.models.models import MaterialStock
    from app.services.services import ProductionPlanService

    with app.app_context():
        row = MaterialStock.query.filter_by(
            material_id=workshop_and_showroom['material_id'],
            store_id=workshop_and_showroom['workshop_id']).one()
        row.current_quantity = 30
        db.session.commit()

        result = ProductionPlanService().purchase_suggestions(
            workshop_and_showroom['company_id'])
        assert _suggested(result, workshop_and_showroom['material_id']) == 0, (
            'the workshop holds 30m for a 20m job and is still told to buy')


def test_one_location_gets_the_same_answer_as_before(app, seed):
    """Where the company has one branch, the two sums are the same sum."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Material, MaterialStock, ProductionMaterialLine, ProductionPlan,
        Supplier,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-1', name='Gỗ Hoà Bình',
                            is_active=True)
        db.session.add(supplier)
        db.session.flush()
        material = Material(company_id=seed['company_id'],
                            material_code='KHUNG-1', name='Khung sồi',
                            unit_price=2_100_000, supplier_id=supplier.id,
                            is_active=True)
        db.session.add(material)
        db.session.flush()
        db.session.add(MaterialStock(company_id=seed['company_id'],
                                     material_id=material.id,
                                     store_id=seed['store_id'],
                                     current_quantity=4))
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-ONE',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-ONE',
                              status=ProductionPlan.STATUS_APPROVED)
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=material.id,
            quantity_required=12, unit='bộ'))
        db.session.commit()

        result = ProductionPlanService().purchase_suggestions(
            seed['company_id'])
        assert _suggested(result, str(material.id)) == 8, (
            'needs 12, holds 4, so 8 — the plan has no production site of its '
            "own and must read the order's branch, as it always did")
