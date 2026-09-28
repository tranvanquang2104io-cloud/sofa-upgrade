"""The receive form arrived pre-filled with "all of it", one click from done.

`po_view.html` rendered every line's quantity input already containing the
full outstanding amount. The form is always open on the purchase-order screen,
so viewing an order and recording a warehouse movement were the same screen,
and the movement was one click away with every number already agreeing.

Partial deliveries are normal in this trade — a supplier sends what they have.
A pre-filled "all of it" is a default that is wrong more often than it is
right, and it is wrong in the expensive direction: stock goes up for goods
nobody has seen, the shelves disagree with the system, and the discrepancy is
found weeks later by somebody standing in front of the rack.

The quantity is now empty, with the outstanding amount shown beside it as
information rather than as an answer. The storeman states what arrived.

This does NOT restructure the screen. Moving receiving to its own page is the
rest of T-11 and it changes the layout, which runs into "giữ diện mạo" — this
is the part that removes the accident without changing what anything looks
like.
"""
import datetime as dt

import pytest


@pytest.fixture()
def sent_po(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-RC', name='NCC', is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-RC2', name='Vai', is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'], supplier_id=supplier.id,
                           po_number='PO-RECV', order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            po_id=po.id, material_id=material.id, quantity_ordered=100,
            unit='m', unit_price=50_000))
        db.session.commit()
        return {**seed, 'po_id': str(po.id), 'material_id': str(material.id)}


def test_the_quantity_is_not_pre_filled_with_the_whole_order(client, login,
                                                             sent_po):
    """An empty box asks a question; a filled one states an answer."""
    login('admin')
    body = client.get(f"/purchase-orders/{sent_po['po_id']}").get_data(
        as_text=True)

    assert 'name="qty_' in body, 'the receiving form disappeared entirely'
    filled = 'value="100.0"' in body or 'value="100"' in body
    assert not filled, (
        'the quantity box still arrives pre-filled with the full outstanding '
        'amount, so one click records the whole order as received')


def test_the_outstanding_amount_is_still_shown(client, login, sent_po):
    """Removing the default must not remove the information.

    The storeman needs to know what is still owed; they just should not have
    it typed into the box for them.
    """
    login('admin')
    body = client.get(f"/purchase-orders/{sent_po['po_id']}").get_data(
        as_text=True)
    assert '100' in body, 'the outstanding quantity is no longer visible'


def test_receiving_a_partial_delivery_still_works(app, client, login,
                                                  sent_po):
    """The normal case in this trade: the supplier sent part of it."""
    from app.models.models import MaterialStock, PurchaseOrder

    with app.app_context():
        line_id = str(PurchaseOrder.query.get(sent_po['po_id']).lines[0].id)

    login('admin')
    client.post(f"/purchase-orders/{sent_po['po_id']}/receive", data={
        'receipt_date': '2026-09-10', f'qty_{line_id}': '40',
    }, follow_redirects=True)

    with app.app_context():
        stock = MaterialStock.query.filter_by(
            material_id=sent_po['material_id']).first()
        assert stock is not None and float(stock.current_quantity) == 40, (
            'a partial delivery did not reach the stock record')
        po = PurchaseOrder.query.get(sent_po['po_id'])
        assert po.status == PurchaseOrder.STATUS_PARTIAL, (
            f'the order should be partially received, is {po.status!r}')
