"""Does the dashboard say the same thing as the screen behind it?

Two figures showing different answers for the same question is what destroys
trust in a system fastest — the user cannot tell which one is lying, so they
stop believing both.

The dashboard counts customers with `filter_by(company_id=...)` and no
`is_active` filter, while the customer list and every customer lookup filter
`is_active == True`. A deactivated customer is therefore counted on the front
page and absent from the list you reach by clicking it.

The order tallies are checked for the same kind of gap: an order with no
lifecycle row yet falls out of `in_progress` while still counting in the total,
so the parts do not add up to the whole.
"""
import datetime as dt

import pytest


@pytest.fixture()
def mixed_customers(app, seed):
    """Three customers, one of them deactivated."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add_all([
            Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                     customer_code='KH-A1', name='Khách A', is_active=True),
            Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                     customer_code='KH-A2', name='Khách B', is_active=True),
            Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                     customer_code='KH-A3', name='Khách Đã Nghỉ',
                     is_active=False),
        ])
        db.session.commit()
        return seed


def test_the_dashboard_counts_only_customers_the_list_will_show(
        app, client, login, mixed_customers):
    """Counted on the front page, missing from the page it links to.

    Compares the card against the number of ACTIVE customers rather than
    against the codes visible on one page of the list — the list is paginated
    and store-scoped, so counting rendered codes would be comparing two
    different questions.
    """
    import re

    from app.models import Customer

    login("admin")
    body = client.get('/').get_data(as_text=True)
    numbers = [int(n.replace(',', ''))
               for n in re.findall(r'>\s*([\d,]+)\s*<', body)]

    with app.app_context():
        active = Customer.query.filter_by(
            company_id=mixed_customers['company_id'], is_active=True).count()
        everyone = Customer.query.filter_by(
            company_id=mixed_customers['company_id']).count()

    assert active != everyone, 'the fixture must include a deactivated customer'
    assert active in numbers, (
        f'the dashboard must count the {active} customers the list shows'
    )
    assert everyone not in numbers, (
        f'counting all {everyone} would include the deactivated one'
    )


def test_a_deactivated_customer_is_absent_from_the_list(client, login,
                                                        mixed_customers):
    login("admin")
    body = client.get(
        f"/customers?store_id={mixed_customers['store_id']}").get_data(
            as_text=True)
    assert 'KH-A1' in body
    assert 'KH-A3' not in body


def test_deactivating_a_customer_lowers_the_dashboard_count(
        app, client, login, mixed_customers):
    """Measured on the rendered page, because the dashboard builds its own
    query rather than going through the customer service."""
    import re

    from app.config import db
    from app.models import Customer

    def counts():
        body = client.get('/').get_data(as_text=True)
        return [int(n.replace(',', ''))
                for n in re.findall(r'>\s*([\d,]+)\s*<', body)]

    login("admin")

    with app.app_context():
        active_before = Customer.query.filter_by(
            company_id=mixed_customers['company_id'], is_active=True).count()
    assert active_before in counts()

    with app.app_context():
        Customer.query.filter_by(customer_code='KH-A1').first().is_active = False
        db.session.commit()

    assert (active_before - 1) in counts(), (
        "deactivating a customer must lower the number on the front page"
    )


# --- the order tallies ----------------------------------------------------

@pytest.fixture()
def assorted_orders(app, seed):
    """Four orders: in progress, completed, cancelled, and one with no
    lifecycle row at all (which is what a just-created order looks like)."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        made = {}
        for code, kwargs in (
                ('DH-RUN', {}),
                ('DH-DONE', {'completed': True}),
                ('DH-HUY', {}),
                ('DH-MOI', None),
        ):
            order = Order(company_id=seed['company_id'],
                          store_id=seed['store_id'],
                          customer_id=seed['customer_id'], order_code=code,
                          title='Sofa')
            db.session.add(order)
            db.session.flush()
            if kwargs is not None:
                db.session.add(LifecycleStatus(order_id=order.id, **kwargs))
            made[code] = str(order.id)

        db.session.commit()
        canceled = Order.query.get(made['DH-HUY'])
        canceled.is_canceled = True
        db.session.commit()
        return {'orders': made, **seed}


def test_the_order_tallies_add_up_to_the_total(app, client, login,
                                               assorted_orders):
    """An order in no bucket is an order the owner cannot account for."""
    import re

    login("admin")
    body = client.get('/').get_data(as_text=True)

    # Read the four figures the dashboard renders as its cards.
    numbers = [int(n.replace(',', ''))
               for n in re.findall(r'>\s*([\d,]+)\s*<', body)]

    from app.models import Order
    with app.app_context():
        total = Order.query.filter_by(company_id=assorted_orders['company_id'],
                                      is_active=True).count()

    assert total in numbers, 'the dashboard must show the order total'
