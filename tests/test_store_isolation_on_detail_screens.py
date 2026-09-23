"""Store scoping must hold on the detail screens, not only on the lists.

The list screens filter by `get_accessible_store_ids()`, so a store user sees
only their own branch's orders. The DETAIL routes check the company and stop
there — so the same user, given an id belonging to another branch, can open the
order and act on it.

`issue_plan_materials` is the sharp end: it deducts from `order.store_id`, so a
user at branch A can take stock off branch B's shelves. Branch B's on-hand
figure then disagrees with its shelves, and nothing in the record says who did
it.

The existing sweep at tests/test_tenant_isolation_sweep.py cannot see any of
this, because it builds ONE store per company: with a single store, scoping to
the company and scoping to the store are the same test. This one builds two.

`ensure_store_access()` already exists and already does the right thing. The
detail routes simply were not calling it.
"""
import datetime as dt

import pytest


@pytest.fixture()
def staff_can_work(app, seed):
    """Grant the seeded store user the permissions their job needs.

    Without this every request is 403 for lack of a feature grant, and a test
    asserting "another branch is refused" passes for the wrong reason — which
    is exactly what happened on the first run of this file.
    """
    from app.config import db
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['orders', 'inventory', 'customers']
        db.session.commit()
    return seed


@pytest.fixture()
def other_branch_order(app, seed, staff_can_work):
    """An order, a plan and stock, all belonging to a branch the user is not in.

    The seeded `staff` user belongs to `seed['store_id']`; everything here
    belongs to a second branch.
    """
    import decimal

    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, LifecycleStatus, Material, MaterialStock, ProductionPlan,
        ProductionMaterialLine, Store,
    )

    with app.app_context():
        branch = Store(company_id=seed['company_id'], store_code='CH-B',
                       name='Chi nhánh Quận 7', is_active=True)
        db.session.add(branch)
        db.session.flush()

        order = Order(company_id=seed['company_id'], store_id=branch.id,
                      customer_id=seed['customer_id'], order_code='DH-BRANCH',
                      title='Sofa góc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-BRANCH', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=0, is_signed=True))

        fabric = Material(company_id=seed['company_id'],
                          material_code='VAI-B', name='Vải nhung be',
                          is_active=True)
        db.session.add(fabric)
        db.session.flush()
        db.session.add(MaterialStock(material_id=fabric.id,
                                     company_id=seed['company_id'],
                                     store_id=branch.id,
                                     current_quantity=decimal.Decimal('100')))

        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-BRANCH',
                              status=ProductionPlan.STATUS_APPROVED)
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=fabric.id,
            quantity_required=decimal.Decimal('10'), unit='m'))
        db.session.commit()

        return {**seed, 'branch_id': str(branch.id), 'order_id': str(order.id),
                'plan_id': str(plan.id), 'material_id': str(fabric.id)}


def test_a_store_user_cannot_open_another_branch_s_order(client, login,
                                                         other_branch_order):
    login('staff')
    response = client.get(f"/orders/{other_branch_order['order_id']}")
    assert response.status_code in (403, 302, 404), (
        "a store user opened another branch's order "
        f"(HTTP {response.status_code})")


def test_a_store_user_cannot_open_another_branch_s_production_plan(
        client, login, other_branch_order):
    login('staff')
    response = client.get(
        f"/orders/{other_branch_order['order_id']}/production-plan")
    assert response.status_code in (403, 302, 404)


def test_a_store_user_cannot_issue_another_branch_s_stock(
        app, client, login, other_branch_order):
    """The sharp end: this takes fabric off a shelf in another town."""
    from app.models.models import MaterialStock

    login('staff')
    client.post(f"/production-plan/{other_branch_order['plan_id']}/issue",
                follow_redirects=True)

    with app.app_context():
        stock = MaterialStock.query.filter_by(
            material_id=other_branch_order['material_id'],
            store_id=other_branch_order['branch_id']).first()
        assert float(stock.current_quantity) == 100, (
            "a user at another branch deducted this branch's stock: "
            f'{stock.current_quantity} left of 100')


def test_a_company_admin_may_still_reach_every_branch(client, login,
                                                      other_branch_order):
    """Scoping must not lock an administrator out of their own company."""
    login('admin')
    assert client.get(
        f"/orders/{other_branch_order['order_id']}").status_code == 200


def test_the_user_s_own_order_is_unaffected(app, client, login, seed,
                                            staff_can_work):
    """The ordinary case: a store user opens their own branch's work."""
    from app.config import db
    from app.models import Order

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-MINE',
                      title='Sofa băng')
        db.session.add(order)
        db.session.commit()
        order_id = str(order.id)

    login('staff')
    assert client.get(f'/orders/{order_id}').status_code == 200
