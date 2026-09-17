"""Contract creation invariants.

Two defects found 2026-09 in the create-contract route, which writes through
``ContractRepository`` directly instead of ``ContractService``:

F6  — when the form carries no line items the route copies the quotation's
      items onto the contract, but ``contract_value`` was computed from the
      (empty) form subtotal. The contract then shows items worth X while its
      value column says 0.

F22 — ``ContractService.create_contract`` deactivates any previously active
      contract on the order ("single-active-contract constraint", an explicit
      invariant in that service). The route does not, so an order can end up
      with two active contracts. Downstream code picks the fee source with
      ``next((c for c in order.contracts if c.is_active ...))`` — i.e. an
      arbitrary one of the two.
"""
import datetime as dt

import pytest


@pytest.fixture()
def order_with_quotation(app, seed):
    """An order carrying an approved quotation worth 10,000,000 + 8% VAT."""
    from app.config import db
    from app.models import Order
    from app.models.models import Quotation

    items = [{'name': 'Sofa 3 chỗ', 'unit': 'bộ', 'quantity': 1,
              'unit_price': 10_000_000, 'total': 10_000_000}]

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-CT1",
                      title="Contract integrity order")
        db.session.add(order)
        db.session.flush()
        q = Quotation(company_id=seed["company_id"], order_id=order.id,
                      quotation_number="QT-500", quotation_date=dt.date(2026, 1, 5),
                      items=items, subtotal=10_000_000, vat_rate=8,
                      vat_amount=800_000, total_amount=10_800_000,
                      is_approved=True)
        db.session.add(q)
        db.session.commit()
        return {**seed, "order_id": str(order.id), "quotation_id": str(q.id)}


def _post_contract(client, order_id, number, quotation_id=None, with_items=False):
    data = {
        'contract_number': number,
        'contract_date': '2026-01-10',
        'vat_rate': '8',
    }
    if quotation_id:
        data['quotation_id'] = quotation_id
    if with_items:
        data.update({
            'item_name[]': 'Sofa 3 chỗ',
            'item_unit[]': 'bộ',
            'item_quantity[]': '1',
            'item_price[]': '10000000',
        })
    return client.post(f'/contracts/{order_id}/create', data=data,
                       follow_redirects=True)


def test_contract_value_matches_items_copied_from_quotation(
        app, client, login, order_with_quotation):
    """F6: value must not be 0 while the contract carries 10m worth of items."""
    login("admin")
    resp = _post_contract(client, order_with_quotation["order_id"], "CT-500",
                          quotation_id=order_with_quotation["quotation_id"])
    assert resp.status_code == 200, resp.data[:400]

    from app.models.models import Contract
    with app.app_context():
        c = Contract.query.filter_by(contract_number="CT-500").first()
        assert c is not None, "contract was not created"

        from app.services.money import subtotal_from_items
        items_worth = float(subtotal_from_items(c.items))

        assert items_worth > 0, "precondition: items should have been copied"
        assert float(c.contract_value) >= items_worth, (
            f"contract_value ({c.contract_value}) is less than the value of the "
            f"items it carries ({items_worth}) — the value column and the items "
            f"have diverged"
        )


def test_creating_a_second_contract_deactivates_the_first(
        app, client, login, order_with_quotation):
    """F22: an order must never end up with two active contracts."""
    login("admin")
    order_id = order_with_quotation["order_id"]

    _post_contract(client, order_id, "CT-601", with_items=True)
    _post_contract(client, order_id, "CT-602", with_items=True)

    from app.models.models import Contract
    with app.app_context():
        active = Contract.query.filter_by(order_id=order_id, is_active=True).all()
        numbers = sorted(c.contract_number for c in active)
        assert len(active) == 1, (
            f"single-active-contract invariant broken: {numbers} are all active. "
            f"Downstream fee lookups pick an arbitrary one of these."
        )
        assert active[0].contract_number == "CT-602", "the newest should be active"
