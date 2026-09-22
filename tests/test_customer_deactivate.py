"""Retiring a customer who has stopped buying.

A CRUD audit across every entity turned this up: materials, stores and users
can all be deactivated, and `Customer.is_active` exists and is honoured by every
customer query — but no route ever sets it. A customer who has closed down, or
a duplicate record created by a typo, stays in the picker forever.

Deactivate rather than delete, and for the same reason templates are not always
deletable: orders, quotations and contracts point at the customer, and removing
the row would lose the name on documents already issued. Deactivating keeps the
history and takes the customer out of the way.
"""
import pytest


@pytest.fixture()
def customer(app, seed):
    from app.config import db
    from app.models import Customer

    with app.app_context():
        record = Customer(company_id=seed['company_id'],
                          store_id=seed['store_id'],
                          customer_code='KH-OFF', name='Khách đã nghỉ')
        db.session.add(record)
        db.session.commit()
        # **seed FIRST: it carries its own customer_id, and spreading it last
        # would overwrite the one just created — which made the first test pass
        # while deactivating a different customer entirely.
        return {**seed, 'customer_id': str(record.id)}


def _customer(customer_id):
    from app.models import Customer
    return Customer.query.get(customer_id)


def test_a_customer_can_be_deactivated(app, client, login, customer):
    login('admin')
    client.post(f"/customers/{customer['customer_id']}/deactivate",
                follow_redirects=True)

    with app.app_context():
        assert _customer(customer['customer_id']).is_active is False


def test_the_record_is_kept_not_deleted(app, client, login, customer):
    """Documents already issued carry this customer's name."""
    login('admin')
    client.post(f"/customers/{customer['customer_id']}/deactivate",
                follow_redirects=True)

    with app.app_context():
        assert _customer(customer['customer_id']) is not None


def test_a_deactivated_customer_leaves_the_list(client, login, customer):
    login('admin')
    client.post(f"/customers/{customer['customer_id']}/deactivate",
                follow_redirects=True)

    body = client.get(f"/customers?store_id={customer['store_id']}").get_data(
        as_text=True)
    assert 'KH-OFF' not in body


def test_a_customer_with_orders_is_still_deactivatable(app, client, login,
                                                        customer):
    """Unlike deleting, this cannot orphan anything, so nothing blocks it."""
    from app.config import db
    from app.models import Order

    with app.app_context():
        db.session.add(Order(company_id=customer['company_id'],
                             store_id=customer['store_id'],
                             customer_id=customer['customer_id'],
                             order_code='DH-OFF', title='Sofa'))
        db.session.commit()

    login('admin')
    client.post(f"/customers/{customer['customer_id']}/deactivate",
                follow_redirects=True)

    with app.app_context():
        assert _customer(customer['customer_id']).is_active is False


def test_another_company_customer_cannot_be_touched(app, client, login, seed):
    from app.config import db
    from app.models import Company, Customer, Store

    with app.app_context():
        rival = Company(company_code='CDA', name='Rival', email='r@cda.test')
        db.session.add(rival)
        db.session.flush()
        store = Store(company_id=rival.id, store_code='CDS', name='S')
        db.session.add(store)
        db.session.flush()
        stranger = Customer(company_id=rival.id, store_id=store.id,
                            customer_code='KH-RIVAL', name='Khách đối thủ')
        db.session.add(stranger)
        db.session.commit()
        stranger_id = str(stranger.id)

    login('admin')
    client.post(f'/customers/{stranger_id}/deactivate', follow_redirects=True)

    with app.app_context():
        assert _customer(stranger_id).is_active is True


def test_deactivating_asks_first(client, login, customer):
    login('admin')
    body = client.get(f"/customers/{customer['customer_id']}").get_data(
        as_text=True)

    index = body.find(f"/customers/{customer['customer_id']}/deactivate")
    assert index != -1, 'the customer screen must offer this'
    around = body[max(0, index - 500):index + 500]
    assert 'confirm(' in around or 'data-bs-toggle="modal"' in around


def test_a_missing_customer_says_so(client, login):
    import uuid

    login('admin')
    body = client.post(f'/customers/{uuid.uuid4()}/deactivate',
                       follow_redirects=True).get_data(as_text=True)
    assert ('không tìm thấy' in body.lower() or 'not found' in body.lower())
