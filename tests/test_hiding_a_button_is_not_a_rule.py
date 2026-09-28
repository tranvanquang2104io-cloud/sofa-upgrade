"""Every one of these is reachable by typing the URL. The button is not the rule.

The owner, unambiguously: *"Khong duoc giai quyet van de Security chi bang cach
an button tren UI."*

Exactly one test in this suite ever posted to an endpoint whose button the
screen had hidden -- `test_a_voided_payment_stays_voided.py` -- and it found a
real hole on its first run: a cancelled payment could be confirmed by posting
the confirm URL, leaving a record that said both things at once.

That is not evidence that one endpoint was special. It is evidence that nobody
had looked at the others. This file looks at the rest of the state-changing
ones: an action already done, an action on a document past the point where it
makes sense, an action on something cancelled.

Each test presses the URL directly as a legitimate, logged-in, permitted user.
Nothing here is about permissions -- it is about whether the RULE lives in the
service or only in the template that decided whether to draw a button.

All five pass, so the product already defends these paths. That is only worth
believing because the strongest one was CHECKED: deleting the `can_receive()`
guard from `ProcurementService.receive` must turn the draft-PO test red.

The first time I tried that, it stayed green -- and the fault was mine. That
test posted only a date and no quantities, so nothing would have been received
with or without the guard. An empty request is not a test of a refusal. With a
real quantity posted, removing the guard fails it at "a goods receipt was
created for an order that was never sent to the supplier".
"""
import datetime as dt

import pytest


@pytest.fixture()
def paperwork(app, seed):
    """A signed contract, an approved quotation, and a draft purchase order."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, LifecycleStatus, Material, PurchaseOrder,
        PurchaseOrderLine, Quotation, Supplier,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-BYPASS',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       quotation_approved=True,
                                       quotation_approved_at=dt.datetime(
                                           2026, 9, 1, 8, 0),
                                       contract_created=True,
                                       contract_signed=True))
        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-BYPASS', quotation_date=dt.date(2026, 9, 1),
            total_amount=20_000_000, is_approved=True)
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-BYPASS', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=50,
            is_signed=True, signed_date=dt.datetime(2026, 9, 1),
            is_active=True)
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-BP', name='NCC', is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-BP', name='Vai', is_active=True)
        db.session.add_all([quotation, contract, supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'], supplier_id=supplier.id,
                           po_number='PO-BYPASS',
                           order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_DRAFT)
        db.session.add(po)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            po_id=po.id, material_id=material.id, quantity_ordered=10,
            unit='m', unit_price=100_000))
        db.session.commit()

        return {**seed, 'order_id': str(order.id),
                'quotation_id': str(quotation.id),
                'contract_id': str(contract.id), 'po_id': str(po.id),
                'material_id': str(material.id)}


def test_signing_an_already_signed_contract_changes_nothing(app, client,
                                                            login, paperwork):
    """The screen hides the Sign button once signed. That is not a rule."""
    from app.models.models import Contract

    with app.app_context():
        before = Contract.query.get(paperwork['contract_id']).signed_date

    login('admin')
    client.post(f"/contracts/{paperwork['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        after = Contract.query.get(paperwork['contract_id'])
        assert after.signed_date == before, (
            'signing an already-signed contract moved the signing date, so '
            'the date on our record no longer matches the paper the customer '
            'signed')


def test_approving_an_already_approved_quotation_changes_nothing(
        app, client, login, paperwork):
    from app.models.models import LifecycleStatus, Quotation

    with app.app_context():
        before = LifecycleStatus.query.filter_by(
            order_id=paperwork['order_id']).first().quotation_approved_at

    login('admin')
    client.post(f"/quotations/{paperwork['quotation_id']}/approve",
                follow_redirects=True)

    with app.app_context():
        assert Quotation.query.get(
            paperwork['quotation_id']).is_approved is True
        after = LifecycleStatus.query.filter_by(
            order_id=paperwork['order_id']).first().quotation_approved_at
        assert after == before, (
            're-approving moved the approval timestamp, so the record says it '
            'was approved at a time nobody approved it')


def test_receiving_against_a_draft_purchase_order_is_refused(app, client,
                                                            login, paperwork):
    """The screen now explains why it cannot receive. The service must agree.

    T-14 replaced a hidden section with an explanation. An explanation is
    still only a screen -- if `receive` does not check, posting the URL puts
    stock on the shelves against an order the supplier was never sent.
    """
    from app.models.models import GoodsReceipt, MaterialStock, PurchaseOrder

    # The QUANTITIES matter. My first version posted only a date, so nothing
    # would have been received whether the guard existed or not — the test
    # passed with the guard deliberately deleted, which means it was proving
    # nothing. An empty request is not a test of a refusal.
    with app.app_context():
        line_id = str(PurchaseOrder.query.get(
            paperwork['po_id']).lines[0].id)

    login('admin')
    client.post(f"/purchase-orders/{paperwork['po_id']}/receive", data={
        'receipt_date': '2026-09-10', f'qty_{line_id}': '10',
    }, follow_redirects=True)

    with app.app_context():
        assert GoodsReceipt.query.count() == 0, (
            'a goods receipt was created for an order that was never sent to '
            'the supplier')
        stock = MaterialStock.query.filter_by(
            material_id=paperwork['material_id']).first()
        assert stock is None or float(stock.current_quantity) == 0, (
            'stock went up for goods nobody ordered')


def test_deleting_a_document_twice_does_not_crash(app, client, login,
                                                  paperwork):
    """The second press is a stale tab, not an attack -- it must not 500."""
    from app.config import db
    from app.models.models import Document

    with app.app_context():
        document = Document(
            company_id=paperwork['company_id'],
            order_id=paperwork['order_id'],
            document_name='HD.docx', document_type='contract',
            document_format='docx', file_path='uploads/hd-bypass.docx')
        db.session.add(document)
        db.session.commit()
        document_id = str(document.id)

    login('admin')
    first = client.post(f'/documents/delete/{document_id}',
                        follow_redirects=True)
    second = client.post(f'/documents/delete/{document_id}',
                         follow_redirects=True)

    assert first.status_code == 200
    assert second.status_code != 500, (
        'deleting an already-deleted document crashed the screen')


def test_cancelling_an_already_cancelled_contract_keeps_the_first_reason(
        app, client, login, paperwork):
    """Two cancellations would overwrite the first reason with the second."""
    from app.config import db
    from app.models.models import Contract

    with app.app_context():
        contract = Contract.query.get(paperwork['contract_id'])
        contract.is_signed = False
        db.session.commit()

    login('admin')
    client.post(f"/contracts/{paperwork['contract_id']}/cancel",
                data={'canceled_reason': 'Ly do that su'},
                follow_redirects=True)
    client.post(f"/contracts/{paperwork['contract_id']}/cancel",
                data={'canceled_reason': 'Ly do sai'}, follow_redirects=True)

    with app.app_context():
        after = Contract.query.get(paperwork['contract_id'])
        assert after.canceled_reason == 'Ly do that su', (
            'the second cancellation overwrote the reason recorded by the '
            'first, so the record no longer says why it was really cancelled')
