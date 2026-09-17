"""The supplier-invoice screens — the last engine that had no UI.

Covers recording an invoice against a PO, the match warning surfacing on
screen, confirming, and paying.
"""
import datetime as dt

import pytest

from app.models.models import PurchaseOrder, SupplierInvoice

TODAY = dt.date(2026, 6, 20)


@pytest.fixture()
def po(app, seed):
    """A received PO: 10 units @ 100,000."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialUnit, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed["company_id"], supplier_code="SUP-UI",
                            name="NCC Test", tax_code="0101234567")
        unit = MaterialUnit(company_id=seed["company_id"], name="met")
        cat = MaterialCategory(company_id=seed["company_id"], name="Vai")
        db.session.add_all([supplier, unit, cat])
        db.session.flush()
        material = Material(company_id=seed["company_id"], material_code="MAT-UI",
                            name="Vai nhung", unit_id=unit.id, category_id=cat.id)
        db.session.add(material)
        db.session.flush()
        order = PurchaseOrder(company_id=seed["company_id"],
                              supplier_id=supplier.id, store_id=seed["store_id"],
                              po_number="PO-UI-1",
                              status=PurchaseOrder.STATUS_RECEIVED,
                              order_date=TODAY, vat_rate=8)
        db.session.add(order)
        db.session.flush()
        line = PurchaseOrderLine(po_id=order.id, material_id=material.id,
                                 quantity_ordered=10, quantity_received=10,
                                 quantity_invoiced=0, unit="met",
                                 unit_price=100_000, line_total=1_000_000)
        db.session.add(line)
        db.session.commit()
        return {"po_id": str(order.id), "line_id": str(line.id), **seed}


def test_invoice_list_page_renders(client, login):
    login("admin")
    assert client.get('/supplier-invoices').status_code == 200


def test_invoice_create_page_renders_with_the_po_lines(client, login, po):
    login("admin")
    body = client.get(f'/purchase-orders/{po["po_id"]}/invoice').get_data(as_text=True)
    assert 'Vai nhung' in body
    assert f'qty_{po["line_id"]}' in body


def test_recording_an_invoice_through_the_form(app, client, login, po):
    login("admin")
    resp = client.post(f'/purchase-orders/{po["po_id"]}/invoice', data={
        'invoice_series': '1C26TAA',
        'invoice_number': '0000999',
        'invoice_date': '2026-06-20',
        'vat_rate': '8',
        f'qty_{po["line_id"]}': '10',
        f'price_{po["line_id"]}': '100000',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        inv = SupplierInvoice.query.filter_by(invoice_number='0000999').first()
        assert inv is not None
        assert float(inv.total_amount) == 1_080_000
        assert inv.match_status == SupplierInvoice.MATCH_OK


def test_a_mismatch_is_surfaced_on_the_page_not_blocked(app, client, login, po):
    """Billing more than was received must warn, and still record."""
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(po["line_id"])
        line.quantity_received = 2
        db.session.commit()

    login("admin")
    resp = client.post(f'/purchase-orders/{po["po_id"]}/invoice', data={
        'invoice_number': '0001000',
        'invoice_date': '2026-06-20',
        'vat_rate': '8',
        f'qty_{po["line_id"]}': '10',
        f'price_{po["line_id"]}': '100000',
    }, follow_redirects=True)

    body = resp.get_data(as_text=True)
    with app.app_context():
        inv = SupplierInvoice.query.filter_by(invoice_number='0001000').first()
        assert inv is not None, "the invoice must still be recorded"
        assert inv.match_status == SupplierInvoice.MATCH_NO_RECEIPT
    assert 'discrepancy' in body.lower() or 'match' in body.lower()


def test_confirm_then_pay_settles_the_invoice(app, client, login, po):
    from app.services.payables_service import PayablesService

    login("admin")
    client.post(f'/purchase-orders/{po["po_id"]}/invoice', data={
        'invoice_number': '0001001', 'invoice_date': '2026-06-20',
        'vat_rate': '8',
        f'qty_{po["line_id"]}': '10', f'price_{po["line_id"]}': '100000',
    }, follow_redirects=True)

    with app.app_context():
        inv = SupplierInvoice.query.filter_by(invoice_number='0001001').first()
        inv_id, total = str(inv.id), float(inv.total_amount)

    client.post(f'/supplier-invoices/{inv_id}/confirm', follow_redirects=True)
    with app.app_context():
        assert SupplierInvoice.query.get(inv_id).status == 'confirmed'

    client.post(f'/supplier-invoices/{inv_id}/pay', data={
        'payment_number': 'PAY-UI-1',
        'payment_date': '2026-06-25',
        'amount': str(int(total)),
        'method': 'bank_transfer',
    }, follow_redirects=True)

    with app.app_context():
        assert SupplierInvoice.query.get(inv_id).is_paid is True


def test_a_cash_payment_is_flagged_for_vat_review(app, client, login, po):
    """Input-VAT deduction depends on non-cash evidence — make it visible."""
    login("admin")
    client.post(f'/purchase-orders/{po["po_id"]}/invoice', data={
        'invoice_number': '0001002', 'invoice_date': '2026-06-20',
        'vat_rate': '8',
        f'qty_{po["line_id"]}': '10', f'price_{po["line_id"]}': '100000',
    }, follow_redirects=True)

    with app.app_context():
        inv = SupplierInvoice.query.filter_by(invoice_number='0001002').first()
        inv_id, total = str(inv.id), float(inv.total_amount)

    client.post(f'/supplier-invoices/{inv_id}/confirm', follow_redirects=True)
    resp = client.post(f'/supplier-invoices/{inv_id}/pay', data={
        'payment_number': 'PAY-CASH-1', 'payment_date': '2026-06-25',
        'amount': str(int(total)), 'method': 'cash',
    }, follow_redirects=True)

    assert 'VAT' in resp.get_data(as_text=True), (
        "a cash payment should prompt the user to check VAT deductibility"
    )


def test_supplier_invoices_are_tenant_scoped(app, client, login, seed, po):
    from app.config import db
    from app.models.models import Company, Supplier

    with app.app_context():
        rival = Company(company_code="RVP", name="Rival", email="r@rvp.test")
        db.session.add(rival)
        db.session.flush()
        sup = Supplier(company_id=rival.id, supplier_code="RS", name="RS")
        db.session.add(sup)
        db.session.flush()
        rival_po = PurchaseOrder(company_id=rival.id, supplier_id=sup.id,
                                 po_number="PO-RIVAL",
                                 status=PurchaseOrder.STATUS_RECEIVED)
        db.session.add(rival_po)
        db.session.flush()
        theirs = SupplierInvoice(company_id=rival.id, supplier_id=sup.id,
                                 po_id=rival_po.id, invoice_number="RIVAL-INV",
                                 invoice_date=TODAY, total_amount=1)
        db.session.add(theirs)
        db.session.commit()
        theirs_id = str(theirs.id)

    login("admin")
    resp = client.get(f'/supplier-invoices/{theirs_id}', follow_redirects=True)
    assert 'RIVAL-INV' not in resp.get_data(as_text=True)
