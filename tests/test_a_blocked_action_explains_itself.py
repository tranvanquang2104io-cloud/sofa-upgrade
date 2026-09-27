"""A button that disappears teaches nothing; a button that explains teaches once.

The owner's users are not technical. For them a vanished control is worse than
a greyed-out one: they do not know the control ever existed, so they cannot
ask "why is this off?" — they conclude the product cannot do the thing.

Measured before changing anything: `disabled` appears seven times across all
templates and NOT ONE of them is "blocked, with the reason". Every blocked
action in this product is hidden.

The sharpest instance is the purchase order. While it is a draft,
`po_view.html` hides the entire goods-receipt section, and nothing anywhere
says "send it to the supplier first". A storeman with materials physically
arriving sees a screen with no way to record them.

The explanation comes from the status the document already has. T-14 was
written as depending on the state machine (T-07); the purchase order does not
need it, because `PurchaseOrder.status` and `can_receive()` already say both
what is true now and what has to happen next.
"""
import datetime as dt

import pytest


@pytest.fixture()
def draft_po(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-DRAFT', name='NCC nhap',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-DRAFT', name='Vai nhung',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'], supplier_id=supplier.id,
                           po_number='PO-DRAFT', order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_DRAFT)
        db.session.add(po)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            po_id=po.id, material_id=material.id, quantity_ordered=10,
            unit='m', unit_price=100_000))
        db.session.commit()
        return {**seed, 'po_id': str(po.id)}


def test_a_draft_po_says_why_it_cannot_receive_yet(client, login, draft_po):
    """Not a hidden section: a sentence naming the next step."""
    login('admin')
    body = client.get(f"/purchase-orders/{draft_po['po_id']}").get_data(
        as_text=True)

    assert 'Gửi NCC' in body or 'gửi cho nhà cung cấp' in body.lower(), (
        'the receiving section is hidden on a draft PO and nothing tells the '
        'user that sending it to the supplier is what unlocks it')


def test_the_explanation_names_the_current_state(client, login, draft_po):
    """"Why can I not do this?" is answered by where the document stands."""
    login('admin')
    body = client.get(f"/purchase-orders/{draft_po['po_id']}").get_data(
        as_text=True)

    assert 'Nháp' in body or 'draft' in body.lower(), (
        'the screen does not say what state the order is in, so the '
        'explanation has nothing to hang on')


def test_an_ordered_po_still_shows_the_real_form(app, client, login, draft_po):
    """The explanation must not replace the thing it explains."""
    from app.config import db
    from app.models.models import PurchaseOrder

    with app.app_context():
        po = PurchaseOrder.query.get(draft_po['po_id'])
        po.status = PurchaseOrder.STATUS_ORDERED
        db.session.commit()

    login('admin')
    body = client.get(f"/purchase-orders/{draft_po['po_id']}").get_data(
        as_text=True)

    assert 'name="qty_' in body, (
        'the goods-receipt form is missing on an order that CAN receive')
