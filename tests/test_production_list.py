"""The workshop needs a list of what it is building.

A production plan was reachable only through its own order, at
`/orders/<id>/production-plan`. So "what is in production this week" and "what
is running late" could only be answered by opening orders one at a time and
remembering — which is the one question a workshop floor asks every morning.

Every other document in the product has a list; production was the only working
area with no way in from the navigation at all.

The delayed ones come first, because a list sorted by date buries the only rows
that need a decision today.
"""
import pytest


@pytest.fixture()
def plans_in_various_states(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import ProductionPlan

    with app.app_context():
        made = []
        for code, number, status, delayed in [
            ('DH-P1', 'KH-001', ProductionPlan.STATUS_DRAFT, False),
            ('DH-P2', 'KH-002', ProductionPlan.STATUS_PROCESSING, False),
            ('DH-P3', 'KH-003', ProductionPlan.STATUS_PROCESSING, True),
            ('DH-P4', 'KH-004', ProductionPlan.STATUS_FINISHED, False),
        ]:
            order = Order(company_id=seed['company_id'],
                          store_id=seed['store_id'],
                          customer_id=seed['customer_id'],
                          order_code=code, title='Sofa băng 3 chỗ')
            db.session.add(order)
            db.session.flush()
            db.session.add(ProductionPlan(
                company_id=seed['company_id'], order_id=order.id,
                plan_number=number, status=status, is_delayed=delayed,
                delay_reason='Chờ vải về' if delayed else None))
            made.append(number)
        db.session.commit()
        return seed


def test_the_production_list_exists(client, login, plans_in_various_states):
    login('admin')
    assert client.get('/production').status_code == 200


def test_it_shows_every_plan(client, login, plans_in_various_states):
    login('admin')
    body = client.get('/production').get_data(as_text=True)
    for number in ('KH-001', 'KH-002', 'KH-003', 'KH-004'):
        assert number in body


def test_delayed_plans_come_first(client, login, plans_in_various_states):
    """A list sorted only by date buries the rows that need a decision today."""
    login('admin')
    body = client.get('/production').get_data(as_text=True)
    assert body.index('KH-003') < body.index('KH-001'), (
        'the delayed plan is not at the top')


def test_it_can_be_narrowed_to_what_is_being_built(client, login,
                                                   plans_in_various_states):
    login('admin')
    body = client.get('/production?status=processing').get_data(as_text=True)
    assert 'KH-002' in body
    assert 'KH-003' in body
    assert 'KH-004' not in body, 'a finished plan is not in production'


def test_it_can_be_narrowed_to_what_is_late(client, login,
                                            plans_in_various_states):
    login('admin')
    body = client.get('/production?status=delayed').get_data(as_text=True)
    assert 'KH-003' in body
    assert 'KH-002' not in body


def test_it_is_reachable_from_the_navigation(client, login,
                                             plans_in_various_states):
    """A screen with no link is a screen nobody finds."""
    login('admin')
    body = client.get('/').get_data(as_text=True)
    assert 'href="/production"' in body, (
        'the production list has no entry in the menu')


def test_a_store_user_sees_only_their_own_store(app, client, login, seed):
    """The same tenant scoping every other list has."""
    from app.config import db
    from app.models import Order
    from app.models.models import ProductionPlan, Store

    with app.app_context():
        other = Store(company_id=seed['company_id'], store_code='CH-X',
                      name='Chi nhánh khác', is_active=True)
        db.session.add(other)
        db.session.flush()
        order = Order(company_id=seed['company_id'], store_id=other.id,
                      customer_id=seed['customer_id'],
                      order_code='DH-OTHER', title='Sofa góc')
        db.session.add(order)
        db.session.flush()
        db.session.add(ProductionPlan(company_id=seed['company_id'],
                                      order_id=order.id,
                                      plan_number='KH-OTHER',
                                      status=ProductionPlan.STATUS_PROCESSING))
        db.session.commit()

    login('staff')
    body = client.get('/production').get_data(as_text=True)
    assert 'KH-OTHER' not in body
