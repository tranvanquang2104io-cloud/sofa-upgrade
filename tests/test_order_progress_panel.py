"""One progress panel on the order screen, not two.

The screen carried both "Tiến độ đơn hàng" — a compact stepper — and "Tiến
Trình Đơn Hàng", the full timeline with every document and action on it. They
answer the same question, and the owner chose to keep the timeline.

The stepper card was not only a stepper: it also carried the order's overall
status badge, which appears nowhere else on the page. Removing the card whole
would have quietly taken that away, so the badge moves to the title line where
a status badge belongs.

Deleting a panel must not delete information.
"""
import datetime as dt

import pytest


@pytest.fixture()
def an_order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PROG',
                      title='Sofa góc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-PROG', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=0,
            is_signed=True, is_active=True))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_the_full_timeline_is_the_one_that_stays(client, login, an_order):
    from app.utils.i18n import t

    login('admin')
    body = client.get(f"/orders/{an_order['order_id']}").get_data(as_text=True)
    assert t('Order Lifecycle') in body


def test_the_duplicate_stepper_panel_is_gone(client, login, an_order):
    from app.utils.i18n import t

    login('admin')
    body = client.get(f"/orders/{an_order['order_id']}").get_data(as_text=True)
    assert t('Order progress') not in body, (
        'both progress panels are still on the screen'
    )


def test_the_status_badge_survived_the_removal(client, login, an_order):
    """It lived in the panel that was deleted, and nowhere else."""
    from app.utils.status_tokens import order_status_meta
    from app.models import Order
    from app.utils.i18n import t

    login('admin')
    body = client.get(f"/orders/{an_order['order_id']}").get_data(as_text=True)

    # The order is signed but not handed over; whatever label the token map
    # gives it must be on the page.
    with client.application.app_context():
        order = Order.query.get(an_order['order_id'])
        _token, label = order_status_meta(order)

    assert t(label) in body, (
        "the order's status badge disappeared with the panel it lived in")
