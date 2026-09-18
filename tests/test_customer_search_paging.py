"""A customer search that quietly stopped at twenty.

The browse path paginated properly. The search path took a different route
entirely — `search_customers()`, whose signature carries `limit=20` — and then
set `pagination = None` and `total = len(customers)`.

So a shop with 25 customers called Nguyễn searched, got 20 rows, and had no
next-page link to suspect there were more. Nothing on screen distinguished
"these are all of them" from "these are the first twenty".

(`total` is also computed as len(page) on that branch, which is wrong — but the
template never renders it, so that part is latent, not visible. Left as it is
rather than claimed as a fix.)

Fixed by giving the search the same pagination as the browse path, which also
deletes the special case rather than adding to it.
"""
import pytest


@pytest.fixture()
def many_matching_customers(app, seed):
    """25 customers who all match the same search term."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        for i in range(1, 26):
            db.session.add(Customer(
                company_id=seed['company_id'], store_id=seed['store_id'],
                customer_code=f'KH-N{i:03d}', name=f'Nguyễn Văn Số {i:03d}'))
        db.session.commit()
        return seed


def test_a_search_with_more_than_one_page_offers_the_next_page(
        client, login, many_matching_customers):
    login("admin")
    body = client.get('/customers?search=Nguyễn').get_data(as_text=True)
    assert 'page=2' in body, (
        "a search with 25 matches must not stop silently at 20"
    )


def test_the_second_page_of_a_search_is_still_that_search(
        client, login, many_matching_customers):
    login("admin")
    body = client.get('/customers?search=Nguyễn&page=2').get_data(as_text=True)
    assert 'KH-N025' in body


def test_a_search_still_excludes_non_matches(app, client, login,
                                             many_matching_customers):
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add(Customer(
            company_id=many_matching_customers['company_id'],
            store_id=many_matching_customers['store_id'],
            customer_code='KH-ZZZ', name='Trần Thị Khác'))
        db.session.commit()

    login("admin")
    body = client.get('/customers?search=Nguyễn').get_data(as_text=True)
    assert 'KH-ZZZ' not in body


def test_search_matches_code_and_phone_too(app, client, login, seed):
    """The existing behaviour must survive the rewrite."""
    from app.config import db
    from app.models import Customer

    with app.app_context():
        db.session.add(Customer(company_id=seed['company_id'],
                                store_id=seed['store_id'],
                                customer_code='KH-PHONE', name='Le Van A',
                                phone='0912345678'))
        db.session.commit()

    login("admin")
    by_code = client.get('/customers?search=KH-PHONE').get_data(as_text=True)
    by_phone = client.get('/customers?search=0912345678').get_data(as_text=True)
    assert 'Le Van A' in by_code
    assert 'Le Van A' in by_phone


def test_search_does_not_cross_tenants(app, client, login,
                                       many_matching_customers):
    from app.config import db
    from app.models import Company, Customer, Store

    with app.app_context():
        c = Company(company_code="CSR", name="Rival", email="r@csr.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="CSS", name="S")
        db.session.add(st)
        db.session.flush()
        db.session.add(Customer(company_id=c.id, store_id=st.id,
                                customer_code='ZZ-RIVAL-KH',
                                name='Nguyễn Của Đối Thủ'))
        db.session.commit()

    login("admin")
    body = client.get('/customers?search=Nguyễn').get_data(as_text=True)
    assert 'ZZ-RIVAL-KH' not in body
