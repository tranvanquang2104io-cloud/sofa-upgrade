"""A debt figure must lead to the orders that make it up.

The receivables table named the customer and the amount, both as plain text.
Chasing a debt starts with "which jobs is this?" — and the customer screen
already answers that, listing every order with its value and stage. The only
thing missing was the link between the two, which made the report a thing to
read rather than a thing to work from.
"""
import datetime as dt

import pytest


@pytest.fixture()
def customer_with_debt(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DEBT',
                      title='Sofa băng 3 chỗ')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id, contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-DEBT', contract_date=dt.date(2026, 9, 1),
            contract_value=40_000_000, advance_percentage=0, is_signed=True))
        db.session.commit()
        return seed


def test_each_debtor_links_to_their_orders(client, login, customer_with_debt):
    login('admin')
    body = client.get('/reports/receivables').get_data(as_text=True)
    assert f"/customers/{customer_with_debt['customer_id']}" in body, (
        'the debt names a customer with no way to reach their orders')
