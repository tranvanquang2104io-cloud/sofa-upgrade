"""Opening a branch must give it a place to hold every material.

This is the scenario that made the issuing fallback look load-bearing, and the
reason it is safe to remove once this is fixed.

`ensure_stock_entries_for_stores` creates a stock row per active branch, and it
runs when a material is created and when somebody opens a material's screen. So
a branch opened AFTER the materials exist has no row for any of them until a
person happens to visit each material page. Until then `_stock_for(material,
new_branch)` finds nothing.

With the old fallback that silently resolved to the company-level row: the new
workshop issued fabric it did not hold, out of a warehouse nobody named — an
undocumented transfer, and the shape this whole separation exists to remove.
Without the fallback and without this fix, the same workshop reads zero for
everything and cannot start.

Neither is acceptable, and the fallback was the wrong half to keep. The right
answer is that opening a branch creates its rows, at zero — which is the honest
figure: a new workshop holds nothing until something is delivered to it.

Measured before changing anything: removing the fallback broke exactly one test
in the suite, the one written to pin the fallback itself. The claim recorded in
`e2042b2` — that `MaterialService` puts all stock at company level, so removing
it would stop production on day one — was wrong. `create_material` in the
service does create only the company-level row, but the ROUTE then calls
`ensure_stock_entries_for_stores`, which creates one per branch. Reading one
layer and concluding about the system is the same mistake as every other
"checked by name" defect in this programme; this one reached a commit message.
"""
import pytest


@pytest.fixture()
def a_material_exists(app, seed):
    from app.config import db
    from app.models.models import Material
    from app.services.services import MaterialService

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-NEW', name='Vải bố',
                            is_active=True)
        db.session.add(material)
        db.session.commit()
        MaterialService().ensure_stock_entries_for_stores(
            material.id, seed['company_id'])
        return {**seed, 'material_id': str(material.id)}


def test_opening_a_branch_gives_it_a_row_for_every_material(app,
                                                            a_material_exists):
    from app.config import db
    from app.models.models import MaterialStock
    from app.services.services import StoreService

    with app.app_context():
        workshop = StoreService().create_store(
            company_id=a_material_exists['company_id'],
            store_code='XUONG-N', name='Xưởng mới')
        db.session.commit()

        row = MaterialStock.query.filter_by(
            material_id=a_material_exists['material_id'],
            store_id=workshop.id).first()
        assert row is not None, (
            'the new branch has no stock row for an existing material, so it '
            'reads nothing and cannot start work')
        assert float(row.current_quantity) == 0, (
            'a new branch was credited with stock it has never received')


def test_the_existing_branches_are_untouched(app, a_material_exists):
    """Creating a branch must not move anybody else's stock."""
    from app.config import db
    from app.models.models import MaterialStock
    from app.services.services import MaterialService, StoreService

    with app.app_context():
        MaterialService().update_stock(
            a_material_exists['material_id'], a_material_exists['company_id'],
            a_material_exists['store_id'], 40)
        db.session.commit()

        StoreService().create_store(
            company_id=a_material_exists['company_id'],
            store_code='XUONG-N2', name='Xưởng mới 2')
        db.session.commit()

        showroom = MaterialStock.query.filter_by(
            material_id=a_material_exists['material_id'],
            store_id=a_material_exists['store_id']).one()
        assert float(showroom.current_quantity) == 40


def test_issuing_at_a_branch_no_longer_draws_from_the_company_warehouse(
        app, a_material_exists):
    """The fallback is gone, and this is what it was hiding.

    100m sits in the company warehouse; the new workshop holds none. Before,
    the workshop could issue from it without any document saying the fabric had
    moved. Now it reads zero and says so.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import (
        MaterialStock, ProductionMaterialLine, ProductionPlan,
    )
    from app.services.services import ProductionPlanService, StoreService

    with app.app_context():
        # The company-level row already exists — the fixture's
        # `ensure_stock_entries_for_stores` made it, and a partial unique index
        # forbids a second. Put the stock IN it rather than adding another.
        company_level = MaterialStock.query.filter_by(
            material_id=a_material_exists['material_id'],
            store_id=None).one()
        company_level.current_quantity = 100
        workshop = StoreService().create_store(
            company_id=a_material_exists['company_id'],
            store_code='XUONG-N3', name='Xưởng mới 3')
        order = Order(company_id=a_material_exists['company_id'],
                      store_id=a_material_exists['store_id'],
                      customer_id=a_material_exists['customer_id'],
                      order_code='DH-NB', title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=a_material_exists['company_id'],
                              order_id=order.id, plan_number='KH-NB',
                              production_store_id=workshop.id)
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=a_material_exists['material_id'],
            quantity_required=10, unit='m'))
        db.session.commit()

        levels = ProductionPlanService().stock_levels(
            ProductionPlan.query.get(plan.id))
        row = list(levels.values())[0]
        assert row['available'] == 0, (
            f"the workshop reads {row['available']}m of fabric it does not "
            'hold, drawn from the company warehouse with no document saying '
            'it moved')
        assert row['short'] is True
