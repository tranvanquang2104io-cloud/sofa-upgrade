"""A store user's dashboard must show that store's recent orders.

The dashboard asked for the COMPANY's ten newest orders and only then dropped
the ones belonging to other stores. So a store whose orders are not among the
company's ten newest shows an empty "recent orders" panel — and the busier the
company, the emptier that user's dashboard gets, which is exactly backwards.

It reads as "you have no orders", not as "the list was cut before your rows
were reached", so nobody reports it as a bug. It is the same shape as filtering
after LIMIT anywhere else: the limit has to be applied to the rows you want,
not to the rows you are going to throw away.
"""
import pytest


@pytest.fixture()
def busy_company(app, seed):
    """Another store with newer orders than the user's own store.

    Twelve newer orders elsewhere is enough to push every order of the user's
    store past a limit of ten.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import Store

    with app.app_context():
        own_store = seed['store_id']
        other = Store(company_id=seed['company_id'], store_code='CH-KHAC',
                      name='Chi nhánh Quận 7', is_active=True)
        db.session.add(other)
        db.session.flush()

        # The user's own store ordered first...
        for n in range(2):
            db.session.add(Order(company_id=seed['company_id'],
                                 store_id=own_store,
                                 customer_id=seed['customer_id'],
                                 order_code=f'DH-MINE-{n}',
                                 title='Sofa băng 3 chỗ'))
        db.session.flush()
        # ...and the other branch has been busy since.
        for n in range(12):
            db.session.add(Order(company_id=seed['company_id'],
                                 store_id=other.id,
                                 customer_id=seed['customer_id'],
                                 order_code=f'DH-OTHER-{n}',
                                 title='Sofa góc L'))
        db.session.commit()
        return {**seed, 'other_store_id': str(other.id)}


def test_a_store_user_sees_their_own_recent_orders(client, login, busy_company):
    login('staff')
    body = client.get('/').get_data(as_text=True)
    assert 'DH-MINE-0' in body, (
        "the store's own orders were cut off before the store filter ran")


def test_a_store_user_does_not_see_another_store_s_orders(client, login,
                                                          busy_company):
    login('staff')
    body = client.get('/').get_data(as_text=True)
    assert 'DH-OTHER-0' not in body


def test_a_company_admin_still_sees_every_store(client, login, busy_company):
    login('admin')
    body = client.get('/').get_data(as_text=True)
    assert 'DH-OTHER-11' in body
