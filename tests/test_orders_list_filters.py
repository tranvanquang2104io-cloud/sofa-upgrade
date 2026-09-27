"""Finding an order the two ways people actually look for one.

**By the paper in their hand.** The search covered the order code, the job
title and the customer name. But a customer rings about "hợp đồng HĐ-2026-014"
and the staff member is holding a printed contract — the one number they can
read out is the one number the search did not look at. Same for a quotation, a
handover record or a payment slip. Every one of those numbers already exists in
the database and is printed on the document.

**By where it has got to.** "Which orders are not paid yet" and "what is still
waiting to be handed over" are the daily questions, and the only way to answer
them was to page through the whole list reading badges.

Both filters are on the orders list, which is the screen this product opens on.
"""
import datetime as dt
import re

import pytest


def rows(response):
    """Just the table body.

    Asserting on the whole page catches the search box echoing the query back
    — `value="DH-A"` made a filter look broken when it was working.
    """
    body = response.get_data(as_text=True)
    match = re.search(r'<tbody>(.*?)</tbody>', body, re.S)
    return match.group(1) if match else ''


@pytest.fixture()
def orders_at_different_stages(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, HandoverRecord, LifecycleStatus, PaymentReport, Quotation,
    )

    with app.app_context():
        made = {}
        for code, title in [('DH-A', 'Sofa băng 3 chỗ'),
                            ('DH-B', 'Sofa góc L'),
                            ('DH-C', 'Ghế thư giãn')]:
            order = Order(company_id=seed['company_id'],
                          store_id=seed['store_id'],
                          customer_id=seed['customer_id'],
                          order_code=code, title=title)
            db.session.add(order)
            db.session.flush()
            made[code] = order

        # A is quoted only.
        db.session.add(LifecycleStatus(order_id=made['DH-A'].id,
                                       quotation_created=True))
        db.session.add(Quotation(
            company_id=seed['company_id'], order_id=made['DH-A'].id,
            quotation_number='BG-2026-0007',
            quotation_date=dt.date(2026, 9, 1), total_amount=10_000_000))

        # B is signed and handed over, not yet paid in full.
        db.session.add(LifecycleStatus(order_id=made['DH-B'].id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True,
                                       handover_confirmed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=made['DH-B'].id,
            contract_number='HD-2026-014', contract_date=dt.date(2026, 9, 2),
            contract_value=50_000_000, advance_percentage=30, is_signed=True))
        db.session.add(HandoverRecord(
            company_id=seed['company_id'], order_id=made['DH-B'].id,
            report_number='BB-2026-0021', report_date=dt.date(2026, 9, 20),
            handover_date=dt.date(2026, 9, 20), is_confirmed=True))

        # C is paid in full and finished.
        db.session.add(LifecycleStatus(order_id=made['DH-C'].id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True,
                                       handover_confirmed=True,
                                       fully_paid=True, completed=True))
        db.session.add(PaymentReport(
            company_id=seed['company_id'], order_id=made['DH-C'].id,
            report_number='TT-2026-0033', payment_type='final',
            report_date=dt.date(2026, 9, 21), payment_date=dt.date(2026, 9, 21),
            amount=20_000_000, is_confirmed=True))
        db.session.commit()
        return seed


@pytest.mark.parametrize('number, expected_order', [
    ('HD-2026-014', 'DH-B'),     # the contract the customer names on the phone
    ('BG-2026-0007', 'DH-A'),    # a quotation
    ('BB-2026-0021', 'DH-B'),    # a handover record
    ('TT-2026-0033', 'DH-C'),    # a payment slip
])
def test_an_order_is_found_by_the_number_on_its_paperwork(
        client, login, orders_at_different_stages, number, expected_order):
    login('admin')
    body = rows(client.get(f'/orders?search={number}'))
    assert expected_order in body, (
        f'searching {number} did not find the order it belongs to')


def test_searching_a_document_number_does_not_return_every_order(
        client, login, orders_at_different_stages):
    login('admin')
    body = rows(client.get('/orders?search=HD-2026-014'))
    assert 'DH-A' not in body
    assert 'DH-C' not in body


def test_the_existing_searches_still_work(client, login,
                                          orders_at_different_stages):
    """Order code, title and customer name were already covered."""
    login('admin')
    assert 'DH-B' in rows(client.get('/orders?search=Sofa góc'))
    assert 'DH-A' in rows(client.get('/orders?search=DH-A'))


@pytest.mark.parametrize('status, present, absent', [
    ('unpaid', 'DH-B', 'DH-C'),          # signed but not settled
    ('completed', 'DH-C', 'DH-A'),
    ('awaiting_handover', 'DH-A', 'DH-C'),
])
def test_orders_can_be_filtered_by_where_they_have_got_to(
        client, login, orders_at_different_stages, status, present, absent):
    login('admin')
    body = rows(client.get(f'/orders?status={status}'))
    assert present in body
    assert absent not in body


def test_a_filter_and_a_search_apply_together(client, login,
                                              orders_at_different_stages):
    """Narrowing twice must narrow, not reset."""
    login('admin')
    body = rows(client.get('/orders?status=completed&search=DH-A'))
    assert 'DH-A' not in body, 'DH-A is not completed, so it must not appear'


def test_paging_keeps_the_filter(app, client, login, seed,
                                 orders_at_different_stages):
    """Page 2 must not quietly widen the list back out.

    This assertion used to sit inside `if 'page=2' in body:` over a fixture of
    three orders, against a page size of twenty. Page two could not exist, so
    the assertion never ran and the test was green for every implementation,
    working or not. A conditional assertion is only as real as its condition,
    and nobody had checked the condition could be true.
    """
    from app.config import db
    from app.models import Order

    with app.app_context():
        # Cancelled, because that filter reads `Order.is_canceled` alone.
        # `in_progress` and `awaiting_handover` read LifecycleStatus through an
        # OUTER join, and an order with no lifecycle row compares NULL != True
        # → NULL → excluded. Worth knowing separately; here it would only make
        # the fixture silently empty and the test fail for the wrong reason.
        for index in range(25):
            db.session.add(Order(
                company_id=seed['company_id'], store_id=seed['store_id'],
                customer_id=seed['customer_id'],
                order_code=f'DH-FILT-{index:03d}', title='Sofa góc L',
                is_canceled=True))
        db.session.commit()

    login('admin')
    body = client.get('/orders?status=canceled').get_data(as_text=True)
    assert 'page=2' in body, 'the fixture no longer exercises paging'
    next_link = body[body.rindex('page=2') - 250:body.index('page=2') + 10]
    assert 'status=canceled' in next_link, (
        'the next-page link drops the filter the user is looking through')
