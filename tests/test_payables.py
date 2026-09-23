"""Supplier invoices, payments and the 3-way match.

The chain now runs PR -> PO -> GR -> INVOICE -> PAYMENT. These tests pin the
match verdicts and the "is it paid?" invariants, and assert the deliberate
design choice that a mismatch WARNS rather than blocks.
"""
import datetime as dt
from decimal import Decimal

import pytest

from app.models.models import (
    PurchaseOrder,
    SupplierInvoice,
    SupplierPayment,
)
from app.services.payables_service import PayablesService

TODAY = dt.date(2026, 6, 20)


@pytest.fixture()
def po(app, seed):
    """An ordered PO: 10 units @ 100,000, of which 10 have been received."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialUnit, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed["company_id"],
                            supplier_code="SUP-1", name="NCC Vải Đẹp",
                            tax_code="0101234567")
        unit = MaterialUnit(company_id=seed["company_id"], name="mét")
        cat = MaterialCategory(company_id=seed["company_id"], name="Vải")
        db.session.add_all([supplier, unit, cat])
        db.session.flush()

        material = Material(company_id=seed["company_id"],
                            material_code="MAT-1", name="Vải nhung",
                            unit_id=unit.id, category_id=cat.id)
        db.session.add(material)
        db.session.flush()

        order = PurchaseOrder(
            company_id=seed["company_id"], supplier_id=supplier.id,
            store_id=seed["store_id"], po_number="PO-001",
            status=PurchaseOrder.STATUS_RECEIVED, order_date=TODAY, vat_rate=8)
        db.session.add(order)
        db.session.flush()

        line = PurchaseOrderLine(
            po_id=order.id, material_id=material.id, quantity_ordered=10,
            quantity_received=10, quantity_invoiced=0, unit="mét",
            unit_price=100_000, line_total=1_000_000)
        db.session.add(line)
        db.session.commit()

        return {"po_id": str(order.id), "line_id": str(line.id),
                "supplier_id": str(supplier.id),
                "company_id": seed["company_id"]}


def _po(po_id):
    return PurchaseOrder.query.get(po_id)


def _invoice_lines(line_id, qty, price=100_000):
    return [{'po_line_id': line_id, 'quantity': qty, 'unit_price': price}]


# --- the happy path -------------------------------------------------------

def test_invoice_matching_the_receipt_is_ok(app, po):
    with app.app_context():
        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000123", invoice_date=TODAY,
            invoice_series="1C26TAA", lines=_invoice_lines(po["line_id"], 10))

        assert inv.match_status == SupplierInvoice.MATCH_OK
        assert inv.match_notes is None
        assert float(inv.subtotal) == 1_000_000
        assert float(inv.vat_amount) == 80_000
        assert float(inv.total_amount) == 1_080_000


def test_invoice_captures_the_vat_invoice_identifiers(app, po):
    """ND 123/2020 fields must be captured for input-VAT purposes."""
    with app.app_context():
        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000124", invoice_date=TODAY,
            invoice_series="1C26TAA", lines=_invoice_lines(po["line_id"], 10))

        assert inv.invoice_series == "1C26TAA"
        assert inv.invoice_number == "0000124"
        assert inv.invoice_date == TODAY
        assert inv.seller_tax_code == "0101234567", "MST người bán must be frozen"


def test_quantity_invoiced_accumulates_on_the_po_line(app, po):
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000125", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 4))
        PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000126", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 6))

        line = PurchaseOrderLine.query.get(po["line_id"])
        assert float(line.quantity_invoiced) == 10


# --- the 3-way match verdicts --------------------------------------------

def test_invoicing_more_than_was_received_is_flagged(app, po):
    """The goods receipt is the gate: billed for goods not delivered."""
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(po["line_id"])
        line.quantity_received = 4          # only 4 actually arrived
        db.session.commit()

        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000127", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 10))

        assert inv.match_status == SupplierInvoice.MATCH_NO_RECEIPT
        assert 'received' in inv.match_notes


def test_price_above_tolerance_is_flagged(app, po):
    with app.app_context():
        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000128", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 10, price=120_000))

        assert inv.match_status == SupplierInvoice.MATCH_PRICE_VARIANCE
        assert '%' in inv.match_notes


def test_price_within_tolerance_is_not_flagged(app, po):
    """A 1% drift must not raise noise; the tolerance is 2%."""
    with app.app_context():
        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000129", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 10, price=101_000))
        assert inv.match_status == SupplierInvoice.MATCH_OK


def test_invoicing_more_than_ordered_is_flagged(app, po):
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(po["line_id"])
        line.quantity_received = 20
        db.session.commit()

        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000130", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 20))
        assert inv.match_status == SupplierInvoice.MATCH_OVER_INVOICED


def test_a_mismatch_warns_but_does_not_block(app, po):
    """Deliberate design choice for an SME: annotate, never refuse."""
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(po["line_id"])
        line.quantity_received = 0
        db.session.commit()

        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000131", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 10))

        assert inv.id is not None, "the invoice must still be recorded"
        assert inv.match_status != SupplierInvoice.MATCH_OK


# --- guards ---------------------------------------------------------------

def test_cannot_invoice_a_draft_po(app, po):
    from app.config import db

    with app.app_context():
        order = _po(po["po_id"])
        order.status = PurchaseOrder.STATUS_DRAFT
        db.session.commit()

        with pytest.raises(ValueError, match='draft'):
            PayablesService.create_invoice(
                _po(po["po_id"]), invoice_number="0000132",
                invoice_date=TODAY, lines=_invoice_lines(po["line_id"], 1))


def test_duplicate_supplier_invoice_number_is_refused(app, po):
    with app.app_context():
        PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="DUP-1", invoice_series="AA",
            invoice_date=TODAY, lines=_invoice_lines(po["line_id"], 1))
        with pytest.raises(ValueError, match='already been recorded'):
            PayablesService.create_invoice(
                _po(po["po_id"]), invoice_number="DUP-1", invoice_series="AA",
                invoice_date=TODAY, lines=_invoice_lines(po["line_id"], 1))


def test_invoice_line_from_another_po_is_refused(app, po, seed):
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        other = PurchaseOrder(company_id=seed["company_id"], po_number="PO-OTHER",
                              status=PurchaseOrder.STATUS_ORDERED,
                              supplier_id=po["supplier_id"])
        db.session.add(other)
        db.session.flush()
        stray = PurchaseOrderLine(po_id=other.id,
                                  material_id=PurchaseOrderLine.query.get(
                                      po["line_id"]).material_id,
                                  quantity_ordered=1, unit_price=1)
        db.session.add(stray)
        db.session.commit()

        with pytest.raises(ValueError, match='does not belong'):
            PayablesService.create_invoice(
                _po(po["po_id"]), invoice_number="0000133", invoice_date=TODAY,
                lines=[{'po_line_id': str(stray.id), 'quantity': 1,
                        'unit_price': 1}])


def test_canceling_an_invoice_releases_the_invoiced_quantity(app, po):
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        inv = PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="0000134", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 10))
        assert float(PurchaseOrderLine.query.get(po["line_id"]).quantity_invoiced) == 10

        PayablesService.cancel_invoice(inv, reason='Wrong invoice')
        assert float(PurchaseOrderLine.query.get(po["line_id"]).quantity_invoiced) == 0


# --- payments and allocation ---------------------------------------------

def _confirmed_invoice(po, number="INV-P1", qty=10):
    inv = PayablesService.create_invoice(
        _po(po["po_id"]), invoice_number=number, invoice_date=TODAY,
        lines=_invoice_lines(po["line_id"], qty))
    return PayablesService.confirm_invoice(inv)


def test_full_payment_settles_the_invoice(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po)
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-001", TODAY,
            amount=inv.total_amount)
        PayablesService.allocate(pay, inv, inv.total_amount)
        PayablesService.confirm_payment(pay)

        assert inv.is_paid is True
        assert inv.amount_outstanding == 0


def test_partial_payment_leaves_the_balance_outstanding(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="INV-P2")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-002", TODAY,
            amount=500_000)
        PayablesService.allocate(pay, inv, 500_000)
        PayablesService.confirm_payment(pay)

        assert inv.is_paid is False
        assert inv.amount_outstanding == Decimal('580000.00')


def test_cannot_allocate_more_than_the_payment_holds(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="INV-P3")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-003", TODAY, amount=100)
        with pytest.raises(ValueError, match='unallocated'):
            PayablesService.allocate(pay, inv, 500)


def test_cannot_allocate_more_than_the_invoice_owes(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="INV-P4")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-004", TODAY,
            amount=99_999_999)
        with pytest.raises(ValueError, match='outstanding'):
            PayablesService.allocate(pay, inv, 99_999_999)


def test_one_payment_can_settle_two_invoices(app, po):
    """The reason the allocation table exists at all."""
    with app.app_context():
        inv1 = _confirmed_invoice(po, number="INV-P5", qty=3)
        inv2 = _confirmed_invoice(po, number="INV-P6", qty=2)
        total = inv1.total_amount + inv2.total_amount

        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-005", TODAY, amount=total)
        PayablesService.allocate(pay, inv1, inv1.total_amount)
        PayablesService.allocate(pay, inv2, inv2.total_amount)
        PayablesService.confirm_payment(pay)

        assert inv1.is_paid and inv2.is_paid
        assert pay.unallocated_amount == 0


def test_an_unconfirmed_payment_does_not_count_as_paid(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="INV-P7")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-006", TODAY,
            amount=inv.total_amount)
        PayablesService.allocate(pay, inv, inv.total_amount)
        # not confirmed
        assert inv.is_paid is False


def test_cash_payments_are_identifiable_for_vat_review(app, po):
    """Input-VAT deduction depends on non-cash evidence; make it visible."""
    with app.app_context():
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-007", TODAY,
            amount=1_000, method=SupplierPayment.METHOD_CASH)
        assert pay.is_cash is True


def test_cannot_cancel_an_invoice_that_has_payments_allocated(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="INV-P8")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-008", TODAY, amount=1_000)
        PayablesService.allocate(pay, inv, 1_000)

        with pytest.raises(ValueError, match='payments allocated'):
            PayablesService.cancel_invoice(inv)


# --- PO-level status ------------------------------------------------------

def test_po_invoice_status_progresses(app, po):
    with app.app_context():
        assert PayablesService.invoice_status(_po(po["po_id"])) == 'to_invoice'

        PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="ST-1", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 4))
        assert PayablesService.invoice_status(_po(po["po_id"])) == 'to_invoice'

        PayablesService.create_invoice(
            _po(po["po_id"]), invoice_number="ST-2", invoice_date=TODAY,
            lines=_invoice_lines(po["line_id"], 6))
        assert PayablesService.invoice_status(_po(po["po_id"])) == 'fully_invoiced'


def test_po_payment_status_progresses(app, po):
    with app.app_context():
        assert PayablesService.payment_status(_po(po["po_id"])) == 'not_invoiced'

        inv = _confirmed_invoice(po, number="ST-3")
        assert PayablesService.payment_status(_po(po["po_id"])) == 'not_paid'

        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-ST", TODAY, amount=500_000)
        PayablesService.allocate(pay, inv, 500_000)
        PayablesService.confirm_payment(pay)
        assert PayablesService.payment_status(_po(po["po_id"])) == 'partially_paid'


def test_outstanding_for_supplier_sums_confirmed_invoices(app, po):
    with app.app_context():
        inv = _confirmed_invoice(po, number="ST-4", qty=5)
        outstanding = PayablesService.outstanding_for_supplier(
            po["company_id"], po["supplier_id"])
        assert outstanding == inv.total_amount


def test_the_invoice_page_shows_how_the_whole_order_stands(app, client, login, po):
    """The route computed the PO-wide payment state and threw it away.

    Whether THIS invoice is paid is only half the question for someone about to
    pay: the other half is whether the order it belongs to still has money
    outstanding on other invoices. The value was already computed and passed to
    the template, which never referenced it.
    """
    with app.app_context():
        inv = _confirmed_invoice(po, number="ST-VIEW")
        pay = PayablesService.create_payment(
            po["company_id"], po["supplier_id"], "PAY-VIEW", TODAY, amount=500_000)
        PayablesService.allocate(pay, inv, 500_000)
        PayablesService.confirm_payment(pay)
        invoice_id = str(inv.id)

    login("admin")
    body = client.get(f'/supplier-invoices/{invoice_id}').get_data(as_text=True)
    # Asserted against the status map rather than a literal, so translating a
    # label cannot make this test fail while the screen stays correct — which
    # is exactly what happened when these labels were given Vietnamese.
    from app.utils.status_tokens import status_meta
    _token, label = status_meta('partially_paid', 'po_payment')
    from app.utils.i18n import t
    assert t(label) in body, (
        "the order's overall payment state must be visible on the invoice page"
    )
