"""The product list and the F11 reconciliation review screen.

The review screen is the whole point of phase 1: the owner has to be able to
SEE what is in the data before any product master is built from it.
"""
import datetime as dt

import pytest

from app.models.models import Product


@pytest.fixture()
def documents(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Quotation

    def items(*rows):
        return [{'name': n, 'unit': u, 'quantity': 1, 'unit_price': p,
                 'total': p} for n, u, p in rows]

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-PS",
                      title="Screen order")
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order.id,
            quotation_number="QT-PS1", quotation_date=dt.date(2026, 1, 1),
            total_amount=0,
            items=items(('Sofa 3 cho', 'bo', 10_000_000))))
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order.id,
            quotation_number="QT-PS2", quotation_date=dt.date(2026, 2, 1),
            total_amount=0,
            items=items(('sofa 3 cho', 'bo', 12_000_000))))
        db.session.commit()
        return seed


def test_product_list_renders_when_empty(client, login):
    login("admin")
    resp = client.get('/products')
    assert resp.status_code == 200


def test_reconcile_page_shows_the_names_from_documents(client, login, documents):
    login("admin")
    body = client.get('/products/reconcile').get_data(as_text=True)
    assert 'Sofa 3 cho' in body


def test_reconcile_page_shows_the_price_spread(client, login, documents):
    """One product sold at two prices is what an owner needs to notice."""
    login("admin")
    body = client.get('/products/reconcile').get_data(as_text=True)
    assert '10,000,000' in body and '12,000,000' in body


def test_reconcile_page_can_filter_to_groups_needing_review(client, login,
                                                            documents):
    login("admin")
    resp = client.get('/products/reconcile?only=review')
    assert resp.status_code == 200
    assert 'Sofa 3 cho' in resp.get_data(as_text=True)


def test_creating_a_product_from_the_screen(app, client, login, documents):
    login("admin")
    client.post('/products/reconcile/create', data={
        'match_key': 'sofa 3 cho',
        'name': 'Sofa 3 cho',
    }, follow_redirects=True)

    with app.app_context():
        p = Product.query.filter_by(match_key='sofa 3 cho').first()
        assert p is not None
        assert p.source == 'reconciled'


def test_the_operator_can_correct_the_name_before_it_becomes_master_data(
        app, client, login, documents):
    """The suggested name is the most common spelling, not necessarily right."""
    login("admin")
    client.post('/products/reconcile/create', data={
        'match_key': 'sofa 3 cho',
        'name': 'Sofa 3 chỗ (đã sửa)',
    }, follow_redirects=True)

    with app.app_context():
        p = Product.query.filter_by(match_key='sofa 3 cho').first()
        assert p.name == 'Sofa 3 chỗ (đã sửa)'


def test_creating_without_a_match_key_does_nothing(app, client, login,
                                                   documents):
    login("admin")
    client.post('/products/reconcile/create', data={'name': 'X'},
                follow_redirects=True)
    with app.app_context():
        assert Product.query.count() == 0


def test_creating_from_a_name_no_longer_present_does_nothing(app, client, login,
                                                             documents):
    login("admin")
    client.post('/products/reconcile/create',
                data={'match_key': 'khong-ton-tai'}, follow_redirects=True)
    with app.app_context():
        assert Product.query.count() == 0


def test_a_created_product_appears_in_the_list(app, client, login, documents):
    login("admin")
    client.post('/products/reconcile/create',
                data={'match_key': 'sofa 3 cho', 'name': 'Sofa 3 cho'},
                follow_redirects=True)

    body = client.get('/products').get_data(as_text=True)
    assert 'Sofa 3 cho' in body
    assert 'SP-0001' in body


def test_reconciliation_is_company_admin_only(client, login):
    """It exposes every product name and price the company has ever quoted."""
    login("staff")
    resp = client.get('/products/reconcile', follow_redirects=False)
    assert resp.status_code in (302, 403)


def test_reconcile_page_does_not_show_another_tenant_names(app, client, login,
                                                           seed, documents):
    from app.config import db
    from app.models import Company, Customer, Order, Store
    from app.models.models import Quotation

    with app.app_context():
        c = Company(company_code="PRX", name="Rival", email="r@prx.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="PRXS", name="S")
        db.session.add(st)
        db.session.flush()
        cu = Customer(company_id=c.id, store_id=st.id, customer_code="PRXC",
                      name="C")
        db.session.add(cu)
        db.session.flush()
        o = Order(company_id=c.id, store_id=st.id, customer_id=cu.id,
                  order_code="PRXORD", title="T")
        db.session.add(o)
        db.session.flush()
        db.session.add(Quotation(
            company_id=c.id, order_id=o.id, quotation_number="PRXQT",
            quotation_date=dt.date(2026, 1, 1), total_amount=0,
            items=[{'name': 'ZZRIVALPRODUCT', 'unit': 'x', 'quantity': 1,
                    'unit_price': 1, 'total': 1}]))
        db.session.commit()

    login("admin")
    body = client.get('/products/reconcile').get_data(as_text=True)
    assert 'ZZRIVALPRODUCT' not in body
