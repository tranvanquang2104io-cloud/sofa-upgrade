"""Finding an order on the busiest screen in the app.

Orders accumulate forever and never get archived, so the list screen was the
one place where "where is chị Lan's order from last month" had no answer but
paging through twenty at a time. Every other growing list — customers,
materials, purchase orders, requisitions, payables, agreements — already had a
search box; the orders list, the one people actually live on, did not.

Search covers the three things a user has in hand when they go looking: the
order code, what the job was called, and who it was for.
"""
import pytest


@pytest.fixture()
def three_orders(app, seed):
    from app.config import db
    from app.models import Customer, Order

    with app.app_context():
        lan = Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                       customer_code='KH-LAN', name='Nguyễn Thị Lan')
        hung = Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                        customer_code='KH-HUNG', name='Trần Văn Hùng')
        db.session.add_all([lan, hung])
        db.session.flush()

        db.session.add_all([
            Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=lan.id, order_code='DH-2026-001',
                  title='Sofa góc da bò'),
            Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=hung.id, order_code='DH-2026-002',
                  title='Ghế thư giãn'),
            Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=hung.id, order_code='DH-2026-003',
                  title='Bọc lại sofa cũ'),
        ])
        db.session.commit()
        return seed


def _codes(body):
    return {c for c in ('DH-2026-001', 'DH-2026-002', 'DH-2026-003') if c in body}


def test_the_orders_screen_offers_a_search_box(client, login, three_orders):
    login("admin")
    body = client.get('/orders').get_data(as_text=True)
    assert 'name="search"' in body


def test_search_by_order_code(client, login, three_orders):
    login("admin")
    body = client.get('/orders?search=DH-2026-002').get_data(as_text=True)
    assert _codes(body) == {'DH-2026-002'}


def test_search_by_what_the_job_was_called(client, login, three_orders):
    login("admin")
    body = client.get('/orders?search=thư giãn').get_data(as_text=True)
    assert _codes(body) == {'DH-2026-002'}


def test_search_by_customer_name(client, login, three_orders):
    """The way a user actually remembers an order: by whose it was."""
    login("admin")
    body = client.get('/orders?search=Hùng').get_data(as_text=True)
    assert _codes(body) == {'DH-2026-002', 'DH-2026-003'}


def test_search_is_case_insensitive(client, login, three_orders):
    login("admin")
    body = client.get('/orders?search=dh-2026-001').get_data(as_text=True)
    assert 'DH-2026-001' in body


def test_an_empty_search_still_lists_everything(client, login, three_orders):
    login("admin")
    body = client.get('/orders?search=').get_data(as_text=True)
    assert len(_codes(body)) == 3


def test_a_search_that_finds_nothing_says_so(client, login, three_orders):
    """A blank table with no explanation reads as a broken page."""
    login("admin")
    body = client.get('/orders?search=khongcogi').get_data(as_text=True)
    assert _codes(body) == set()
    assert ('Không tìm thấy' in body or 'No orders' in body
            or 'Chưa có' in body), "an empty result must explain itself"


def test_the_search_term_survives_on_the_page(client, login, three_orders):
    """Otherwise the box empties itself and the user cannot tell what they got."""
    login("admin")
    body = client.get('/orders?search=Hùng').get_data(as_text=True)
    assert 'value="Hùng"' in body


def test_paging_keeps_the_search_term(app, client, login, seed):
    """Page 2 of a search must still be that search, not the whole list.

    This test used to guard its own assertion with `if 'page=2' in body:` on a
    fixture of THREE orders, against a page size of twenty. Page two could not
    exist, so the assertion never ran — the test was green for every possible
    implementation, including a broken one. A conditional assertion is only as
    real as the condition, and nobody had checked that the condition could be
    true.

    Twenty-five orders now, so there IS a page two, and the link to it is
    asserted unconditionally.
    """
    from app.config import db
    from app.models import Order

    with app.app_context():
        for index in range(25):
            db.session.add(Order(
                company_id=seed['company_id'], store_id=seed['store_id'],
                customer_id=seed['customer_id'],
                order_code=f'DH-2026-{index:03d}', title='Sofa góc L'))
        db.session.commit()

    login("admin")
    body = client.get('/orders?search=DH-2026&page=1').get_data(as_text=True)

    assert 'page=2' in body, (
        'twenty-five matches and a page size of twenty produced no second '
        'page; the fixture no longer exercises paging')
    next_link = body[body.rindex('page=2') - 200:body.index('page=2') + 10]
    assert 'search=DH-2026' in next_link, (
        'the Next link drops the search, so page two of a search shows the '
        'whole list — the classic filter-lost-on-paging bug')


def test_search_does_not_cross_tenants(app, client, login, three_orders, seed):
    from app.config import db
    from app.models import Company, Customer, Order, Store

    with app.app_context():
        c = Company(company_code="OSR", name="Rival", email="r@osr.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="OSS", name="S")
        db.session.add(st)
        db.session.flush()
        cu = Customer(company_id=c.id, store_id=st.id, customer_code="OSC",
                      name="Trần Văn Hùng")
        db.session.add(cu)
        db.session.flush()
        db.session.add(Order(company_id=c.id, store_id=st.id, customer_id=cu.id,
                             order_code='ZZ-RIVAL-9', title='Sofa'))
        db.session.commit()

    login("admin")
    body = client.get('/orders?search=Hùng').get_data(as_text=True)
    assert 'ZZ-RIVAL-9' not in body
