"""Two prints left the building and left no trace.

The purchase order and the production plan are built by hardcoded Python and
were streamed straight to the browser. Nothing was kept: no file, no `Document`
row. So those screens could show no printing history, the audit trail had a
hole in exactly the two places where paper goes to an OUTSIDE party, and
nobody could answer "which version did we send the supplier?" — the question
that starts the argument.

This does NOT make them template-driven. That is T-22b, and it needs a
template authored: a purchase-order layout has a row loop that cannot be
mechanically inverted out of the Python that writes it. Saying so plainly
matters, because "the PO is recorded now" could easily be read as "the PO is
Cách A now", and it is not.

What is fixed is the half that costs something today: the record.

The recording is deliberately allowed to FAIL without stopping the print. The
person is standing at the screen waiting for a file to send a supplier;
refusing to give it to them because a row would not insert is the wrong trade,
and it is the same rule the transition ledger follows.
"""
import datetime as dt

import pytest


@pytest.fixture()
def a_purchase_order(app, seed):
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-PRT', name='Cong ty vai',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-PRT', name='Vai nhung',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'], supplier_id=supplier.id,
                           po_number='PO-PRINT', order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        db.session.add(PurchaseOrderLine(
            po_id=po.id, material_id=material.id, quantity_ordered=10,
            unit='m', unit_price=100_000))
        db.session.commit()
        return {**seed, 'po_id': str(po.id)}


def test_printing_a_purchase_order_records_it(app, client, login,
                                              a_purchase_order):
    pytest.importorskip('docx')

    import os

    from app.models.models import Document

    login('admin')
    response = client.get(
        f"/purchase-orders/{a_purchase_order['po_id']}/print")
    assert response.status_code == 200, 'the print itself stopped working'
    assert len(response.data) > 0, 'an empty file was sent'

    with app.app_context():
        recorded = Document.query.filter_by(
            document_type='purchase_order').first()
        assert recorded is not None, (
            'the purchase order was sent to a supplier and nothing was kept; '
            'the screen can show no history of it')
        assert recorded.source_type == 'purchase_order'
        assert str(recorded.source_id) == a_purchase_order['po_id']
        assert os.path.exists(recorded.file_path), (
            'a Document row was written for a file that is not on disk')


def test_the_purchase_order_screen_shows_what_has_been_printed(
        app, client, login, a_purchase_order):
    """A record nobody can see is the seventh instance all over again."""
    pytest.importorskip('docx')

    login('admin')
    client.get(f"/purchase-orders/{a_purchase_order['po_id']}/print")

    body = client.get(
        f"/purchase-orders/{a_purchase_order['po_id']}").get_data(as_text=True)
    assert 'PO-PRINT' in body
    # Case-insensitive: the heading is translated ("Tài Liệu Đã Tạo") and my
    # first version of this line guessed the casing, so it failed while the
    # feature worked — the same mistake as asserting a path I assumed.
    assert 'tài liệu đã tạo' in body.lower(), (
        'the PO screen keeps a printing history it never shows')


def test_a_failure_to_record_does_not_stop_the_print(app, client, login,
                                                     a_purchase_order,
                                                     monkeypatch):
    """The person is waiting for a file to send a supplier.

    Same trade as the transition ledger: a gap in the record is visible
    afterwards, a print that will not come out is a problem right now.
    """
    pytest.importorskip('docx')

    from app.services.services import DocumentService

    def explode(*args, **kwargs):
        raise RuntimeError('the documents disk is full')

    monkeypatch.setattr(DocumentService, 'record_prebuilt_document', explode)

    login('admin')
    response = client.get(
        f"/purchase-orders/{a_purchase_order['po_id']}/print")
    assert response.status_code == 200, (
        'a failure to record the print stopped the print')
    assert len(response.data) > 0
