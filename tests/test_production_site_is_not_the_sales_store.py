"""Where a sofa is BUILT is not where it was SOLD.

`ProductionPlanService` reads `plan.order.store_id` — the branch the CUSTOMER
bought at — and uses it as the place the work happens, in three spots: the
stock column on the plan screen, the availability check before issuing, and the
deduction itself.

With one address that is invisible, because the two are the same row. With two
it is simply wrong: a customer ordering at the Nguyễn Trãi showroom does not
mean the sofa is built at Nguyễn Trãi — the workshop is in Hoài Đức. Material
would be checked against, and deducted from, a showroom that holds none.

`ProductionPlan.production_store_id` says where the work happens. It is
backfilled from `order.store_id`, so nothing moves for anybody today: the two
are the same until somebody says otherwise, and that is the point — the concept
gets a name of its own before it has to carry different data.

Pinned here rather than left to the warehouse work that follows, because this
is the half that can be got right without touching stock at all.
"""
import pytest


@pytest.fixture()
def order_at_the_showroom(app, seed):
    """An order taken at one branch, to be built at another."""
    from app.config import db
    from app.models import Order, Store

    with app.app_context():
        workshop = Store(company_id=seed['company_id'], store_code='XUONG',
                         name='Xưởng Hoài Đức', is_active=True,
                         is_sales_site=False, is_production_site=True)
        db.session.add(workshop)
        db.session.flush()
        order = Order(company_id=seed['company_id'],
                      store_id=seed['store_id'],      # the showroom
                      customer_id=seed['customer_id'],
                      order_code='DH-SITE', title='Sofa góc L')
        db.session.add(order)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'workshop_id': str(workshop.id)}


def _plan_for(app, fixture):
    from app.config import db
    from app.models.models import ProductionPlan

    with app.app_context():
        plan = ProductionPlan(company_id=fixture['company_id'],
                              order_id=fixture['order_id'],
                              plan_number='KH-SITE')
        db.session.add(plan)
        db.session.commit()
        return str(plan.id)


def test_a_plan_records_where_the_work_happens(app, order_at_the_showroom):
    from app.models.models import ProductionPlan

    plan_id = _plan_for(app, order_at_the_showroom)
    with app.app_context():
        plan = ProductionPlan.query.get(plan_id)
        assert hasattr(plan, 'production_store_id'), (
            'a plan cannot say where the sofa is built, only where it was sold')


def test_it_defaults_to_the_selling_branch_so_nothing_moves_today(
        app, order_at_the_showroom):
    """Naming the concept must not change anybody's behaviour on day one."""
    from app.models.models import ProductionPlan
    from app.services.services import production_site_of

    plan_id = _plan_for(app, order_at_the_showroom)
    with app.app_context():
        plan = ProductionPlan.query.get(plan_id)
        assert str(production_site_of(plan)) == order_at_the_showroom['store_id']


def test_once_set_it_is_the_workshop_that_counts(app, order_at_the_showroom):
    from app.config import db
    from app.models.models import ProductionPlan
    from app.services.services import production_site_of

    plan_id = _plan_for(app, order_at_the_showroom)
    with app.app_context():
        plan = ProductionPlan.query.get(plan_id)
        plan.production_store_id = order_at_the_showroom['workshop_id']
        db.session.commit()
        assert str(production_site_of(plan)) == \
            order_at_the_showroom['workshop_id'], (
            'the plan says it is built at the workshop and the service still '
            'reads the showroom')


def test_the_stock_the_plan_shows_follows_the_production_site(
        app, order_at_the_showroom):
    """The number on the screen must be the number the workshop can reach.

    Showing showroom stock on a plan built in Hoài Đức tells the foreman he has
    fabric he cannot touch — and the shortage appears on the day of cutting.
    """
    from app.config import db
    from app.models.models import (
        Material, MaterialStock, ProductionMaterialLine, ProductionPlan,
    )
    from app.services.services import ProductionPlanService

    plan_id = _plan_for(app, order_at_the_showroom)
    with app.app_context():
        material = Material(company_id=order_at_the_showroom['company_id'],
                            material_code='VAI-S', name='Vải bố',
                            is_active=True)
        db.session.add(material)
        db.session.flush()
        # 50m at the workshop, none at the showroom.
        db.session.add(MaterialStock(
            company_id=order_at_the_showroom['company_id'],
            material_id=material.id,
            store_id=order_at_the_showroom['workshop_id'],
            current_quantity=50))
        plan = ProductionPlan.query.get(plan_id)
        plan.production_store_id = order_at_the_showroom['workshop_id']
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=material.id,
            quantity_required=10, unit='m'))
        db.session.commit()

        # Keyed by material line id, not a list — read from the service
        # rather than assumed; the first version of this test indexed it as a
        # list and failed on the shape, which says nothing about the branch.
        levels = ProductionPlanService().stock_levels(
            ProductionPlan.query.get(plan_id))
        row = list(levels.values())[0]
        assert row['available'] == 50, (
            'the plan reads stock from the branch that SOLD the order, so a '
            f'workshop with 50m of fabric is shown as having {row["available"]}')
        assert row['short'] is False
