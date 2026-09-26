"""What the supplier's paper says, next to what the system computes.

`SupplierInvoice` recomputes its totals from its lines. A real invoice often
disagrees — a freight line the model has no room for, a volume discount as one
negative line at the bottom, or the seller rounding VAT on the total while this
system rounds per line.

The dangerous part is not the difference. It is what a clerk does with a paper
invoice that will not match and a screen that insists it must: they adjust a
unit price until the total agrees. That silently corrupts the price history the
three-way match runs its variance check against — the check stops comparing
what was ordered with what was billed, and nothing reports that it has stopped.

So: one optional field for the total the seller printed. The system keeps
computing its own, compares, and flags a difference the way it already flags an
over-invoiced quantity or a price variance. It does not model freight or
discounts — that needs to be decided against real invoices, and is recorded in
§8.10 — but it stops the difference being invisible, and it removes the reason
to falsify a price.

Left empty it changes nothing: an invoice nobody typed a stated total on
matches exactly as it did before.
"""
import datetime as dt

import pytest


@pytest.fixture()
def po_ready_to_invoice(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-ST', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-ST', name='Vải bố',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           supplier_id=supplier.id, po_number='PO-ST',
                           order_date=dt.date(2026, 9, 1), vat_rate=8,
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id, material_id=material.id,
                                 quantity_ordered=10, quantity_received=10,
                                 unit='m', unit_price=215_000)
        db.session.add(line)
        db.session.commit()
        return {**seed, 'po_id': str(po.id), 'line_id': str(line.id)}


def _record(app, fixture, **kwargs):
    from app.models.models import PurchaseOrder
    from app.services.payables_service import PayablesService

    po = PurchaseOrder.query.get(fixture['po_id'])
    return PayablesService.create_invoice(
        po, invoice_number=kwargs.pop('invoice_number', '0001'),
        invoice_date=dt.date(2026, 9, 20), vat_rate=8,
        lines=[{'po_line_id': fixture['line_id'], 'quantity': 10,
                'unit_price': 215_000}],
        **kwargs)


def test_an_invoice_with_no_stated_total_is_unchanged(app,
                                                      po_ready_to_invoice):
    """Nothing moves for anybody who does not use the field."""
    from app.models.models import SupplierInvoice

    with app.app_context():
        invoice = _record(app, po_ready_to_invoice)
        assert invoice.stated_total is None
        assert invoice.match_status == SupplierInvoice.MATCH_OK, (
            f'an ordinary invoice was flagged: {invoice.match_notes}')


def test_a_stated_total_that_agrees_does_not_flag(app, po_ready_to_invoice):
    from app.models.models import SupplierInvoice

    with app.app_context():
        # 10 × 215.000 = 2.150.000, VAT 8% = 172.000, total 2.322.000
        invoice = _record(app, po_ready_to_invoice, stated_total=2_322_000)
        assert invoice.match_status == SupplierInvoice.MATCH_OK


def test_a_rounding_difference_of_a_few_dong_does_not_flag(
        app, po_ready_to_invoice):
    """The seller rounding differently is not a discrepancy worth a warning.

    Flagging it would train people to ignore the flag, and then the flag stops
    working for the case it exists for.
    """
    with app.app_context():
        from app.models.models import SupplierInvoice

        invoice = _record(app, po_ready_to_invoice, stated_total=2_322_001)
        assert invoice.match_status == SupplierInvoice.MATCH_OK


def test_a_real_difference_is_flagged_and_says_how_much(app,
                                                        po_ready_to_invoice):
    """A freight line the model has no room for shows up as a gap, not a lie."""
    with app.app_context():
        from app.models.models import SupplierInvoice

        # The paper says 2.472.000 — 150.000 of freight the model cannot hold.
        invoice = _record(app, po_ready_to_invoice, stated_total=2_472_000)
        assert invoice.match_status == SupplierInvoice.MATCH_TOTAL_MISMATCH
        assert '150' in (invoice.match_notes or ''), (
            f'the note does not say how big the gap is: {invoice.match_notes}')


def test_the_stated_total_never_overwrites_the_computed_one(
        app, po_ready_to_invoice):
    """The system's own total stays the system's own.

    Taking the seller's figure as the payable would mean the lines no longer
    add up to the amount owed, and every downstream figure would be reading a
    number nothing explains.
    """
    with app.app_context():
        invoice = _record(app, po_ready_to_invoice, stated_total=2_472_000)
        assert float(invoice.total_amount) == 2_322_000
        assert float(invoice.stated_total) == 2_472_000


def test_a_mismatch_does_not_block_recording_the_invoice(app,
                                                         po_ready_to_invoice):
    """Warn, do not block — the accountant decides, the software reports.

    Refusing would leave the clerk with a paper invoice they cannot enter, and
    the workaround for that is the price falsification this exists to prevent.
    """
    from app.models.models import SupplierInvoice

    with app.app_context():
        invoice = _record(app, po_ready_to_invoice, stated_total=2_472_000)
        assert invoice.id is not None
        assert SupplierInvoice.query.count() == 1


def test_the_field_is_on_the_screen_and_reaches_the_service(
        app, client, login, po_ready_to_invoice):
    """Checked, because six times in this programme finished work had no way in."""
    from app.models.models import SupplierInvoice

    login('admin')
    body = client.get(
        f"/purchase-orders/{po_ready_to_invoice['po_id']}/invoice").get_data(
        as_text=True)
    assert 'name="stated_total"' in body, (
        'the field exists in the model and no screen offers it')
    assert 'ĐỪNG sửa đơn giá' in body, (
        'the screen does not say why the field is there, so a clerk with a '
        'paper that will not match still edits a price')

    client.post(f"/purchase-orders/{po_ready_to_invoice['po_id']}/invoice",
                data={
                    'invoice_number': '0009',
                    'invoice_date': '2026-09-20',
                    'vat_rate': '8',
                    'stated_total': '2472000',
                    f"qty_{po_ready_to_invoice['line_id']}": '10',
                    f"price_{po_ready_to_invoice['line_id']}": '215000',
                }, follow_redirects=True)

    with app.app_context():
        invoice = SupplierInvoice.query.filter_by(invoice_number='0009').one()
        assert float(invoice.stated_total) == 2_472_000, (
            'the figure typed on the screen never reached the invoice')
        assert invoice.match_status == SupplierInvoice.MATCH_TOTAL_MISMATCH
