"""Cancelling the rest of an order does not unmake the part that arrived.

A purchase order may be cancelled from `partial` — after goods have been
received and stock increased. That is ordinary: twelve of the twenty metres
turn up, the supplier cannot fill the rest, and you close the order.

`create_invoice` then refused outright: "Cannot invoice a canceled purchase
order." So the fabric is on the shelf, the supplier has issued a hóa đơn GTGT
for it, and the system has nowhere to put it — no payable, no input VAT to
reclaim, and the accountant keeps that invoice in a spreadsheet outside the
product. The stock figure and the money figure stop describing the same events.

Cancelling means "nothing more is coming", not "what came does not count".
What must still be refused is invoicing an order that never received anything
— there is no delivery to bill for — and a draft, which was never placed. The
3-way match already warns when an invoice exceeds what was received, so the
quantity itself stays governed.
"""
import datetime as dt
import decimal

import pytest


@pytest.fixture()
def part_received_then_cancelled(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-CANC', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-CANC', name='Vải nhung',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()

        order = PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_number='PO-CANC', order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(order)
        db.session.flush()
        line = PurchaseOrderLine(po_id=order.id, material_id=material.id,
                                 quantity_ordered=20, unit_price=100_000)
        db.session.add(line)
        db.session.commit()
        return {**seed, 'po_id': str(order.id), 'line_id': str(line.id)}


def _receive_then_cancel(app, data, quantity):
    from app.config import db
    from app.models.models import PurchaseOrder
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        order = PurchaseOrder.query.get(data['po_id'])
        if quantity:
            ProcurementService().receive(
                order, {data['line_id']: decimal.Decimal(str(quantity))})
        order = PurchaseOrder.query.get(data['po_id'])
        order.status = PurchaseOrder.STATUS_CANCELED
        db.session.commit()


def test_what_actually_arrived_can_still_be_invoiced(
        app, part_received_then_cancelled):
    from app.models.models import PurchaseOrder
    from app.services.payables_service import PayablesService

    data = part_received_then_cancelled
    _receive_then_cancel(app, data, 12)

    with app.app_context():
        order = PurchaseOrder.query.get(data['po_id'])
        invoice = PayablesService.create_invoice(
            order, invoice_number='0001111',
            invoice_date=dt.date(2026, 9, 20),
            lines=[{'po_line_id': data['line_id'], 'quantity': 12,
                    'unit_price': 100_000}])
        assert invoice is not None
        assert float(invoice.subtotal) == 1_200_000


def test_an_order_that_received_nothing_still_cannot_be_invoiced(
        app, part_received_then_cancelled):
    """There is no delivery to bill for."""
    from app.models.models import PurchaseOrder
    from app.services.payables_service import PayablesService

    data = part_received_then_cancelled
    _receive_then_cancel(app, data, 0)

    with app.app_context():
        order = PurchaseOrder.query.get(data['po_id'])
        with pytest.raises(ValueError):
            PayablesService.create_invoice(
                order, invoice_number='0002222',
                invoice_date=dt.date(2026, 9, 20),
                lines=[{'po_line_id': data['line_id'], 'quantity': 5,
                        'unit_price': 100_000}])


def test_a_draft_order_still_cannot_be_invoiced(app,
                                                part_received_then_cancelled):
    """It was never placed with anyone."""
    from app.config import db
    from app.models.models import PurchaseOrder
    from app.services.payables_service import PayablesService

    data = part_received_then_cancelled
    with app.app_context():
        order = PurchaseOrder.query.get(data['po_id'])
        order.status = PurchaseOrder.STATUS_DRAFT
        db.session.commit()

        order = PurchaseOrder.query.get(data['po_id'])
        with pytest.raises(ValueError):
            PayablesService.create_invoice(
                order, invoice_number='0003333',
                invoice_date=dt.date(2026, 9, 20),
                lines=[{'po_line_id': data['line_id'], 'quantity': 1,
                        'unit_price': 100_000}])
