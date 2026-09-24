""""No results" and "nothing here yet" are different, and must read differently.

A regression I introduced. The procurement lists guard their empty state with
`{% if pos %}` — true emptiness and an unmatched search are the same thing to
that test. The message was already wrong before ("Chưa có đơn mua nào" on a
filtered list), but moving to the shared `empty_state()` macro added a **Tạo
đơn mua** button to it. So a user who mistypes a search is now told they have
no purchase orders and invited to create one — and if they do, they have made a
duplicate of a record that was there all along, one search term away.

Telling someone their data is missing when it is merely filtered is bad. Handing
them a button that creates a second copy of it is worse.

The list knows which case it is in: it has the search term. When one is present
the screen says nothing matched and offers a way to clear it; when there is
genuinely nothing, it says so and offers to create the first one.
"""
import datetime as dt

import pytest


@pytest.fixture()
def one_purchase_order(app, seed):
    from app.config import db
    from app.models.models import PurchaseOrder, Supplier

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-EMPTY', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add(supplier)
        db.session.flush()
        db.session.add(PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_number='PO-REAL', order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_DRAFT))
        db.session.commit()
        return seed


def test_a_search_with_no_matches_does_not_claim_the_list_is_empty(
        client, login, one_purchase_order):
    login('admin')
    body = client.get('/purchase-orders?search=KHONGTONTAI').get_data(
        as_text=True)

    assert 'Chưa có đơn mua nào' not in body, (
        'a filtered list tells the user they have no purchase orders')


def test_a_search_with_no_matches_does_not_offer_to_create_a_duplicate(
        client, login, one_purchase_order):
    """The button is the harmful half: it makes a second copy of what exists."""
    import re

    login('admin')
    body = client.get('/purchase-orders?search=KHONGTONTAI').get_data(
        as_text=True)

    empty = re.search(r'<div class="text-center text-muted py-5">.*?</div>',
                      body, re.S)
    assert empty, 'no empty state rendered at all'
    assert '/purchase-orders/create' not in empty.group(0), (
        'a mistyped search invites the user to create a duplicate record')


def test_a_search_with_no_matches_offers_to_clear_the_search(
        client, login, one_purchase_order):
    login('admin')
    body = client.get('/purchase-orders?search=KHONGTONTAI').get_data(
        as_text=True)
    assert 'Không tìm thấy kết quả' in body, (
        'the screen does not say the search is what emptied the list')


def test_a_genuinely_empty_list_still_offers_to_create(client, login, seed):
    """The other half must keep working: nothing here yet, start one."""
    login('admin')
    body = client.get('/purchase-orders').get_data(as_text=True)
    assert 'Chưa có đơn mua nào' in body
    assert '/purchase-orders/create' in body


def test_the_list_still_shows_what_matches(client, login, one_purchase_order):
    login('admin')
    body = client.get('/purchase-orders?search=PO-REAL').get_data(as_text=True)
    assert 'PO-REAL' in body
