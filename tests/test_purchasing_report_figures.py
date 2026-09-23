"""The two headline numbers on the purchasing report were both wrong.

**"Open POs" counted a status that does not exist.** The filter was
`status in ('draft', 'submitted', 'partial')`. `submitted` is a purchase
REQUISITION status; a purchase ORDER that has gone to the supplier is
`ordered` (models.py PurchaseOrder.STATUS_ORDERED). So the orders actually
sitting with a supplier — the ones most obviously open — were the ones excluded,
while drafts nobody has sent were counted.

**"Outstanding" subtracted an ex-VAT figure from a VAT-inclusive one.**
`po_value` sums `PurchaseOrder.total_amount`, which is subtotal + VAT. `received`
is `Σ quantity_received × unit_price`, which is not. The difference therefore
carries the VAT on everything the company has ordered, including on goods
already standing in the warehouse — so the amount still owed to suppliers reads
high, and the more you receive the wronger it gets.

Both are the same kind of mistake as `list_supplier_invoices` matching the
`supplier` rule: a name that looks right in one domain borrowed into another.
"""
import datetime as dt

import pytest


@pytest.fixture()
def purchase_orders(app, seed):
    """One draft, one sent to the supplier, one part-received, one cancelled."""
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-01', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-100', name='Vải nhung',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()

        def po(number, status, qty, received, price):
            subtotal = qty * price
            vat = subtotal // 10                     # 10% for arithmetic clarity
            order = PurchaseOrder(
                company_id=seed['company_id'], supplier_id=supplier.id,
                po_number=number, order_date=dt.date(2026, 9, 1),
                status=status, subtotal=subtotal, vat_rate=10,
                vat_amount=vat, total_amount=subtotal + vat)
            db.session.add(order)
            db.session.flush()
            db.session.add(PurchaseOrderLine(
                po_id=order.id, material_id=material.id, quantity_ordered=qty,
                quantity_received=received, unit_price=price))
            return order

        po('PO-DRAFT', PurchaseOrder.STATUS_DRAFT, 10, 0, 100_000)
        po('PO-SENT', PurchaseOrder.STATUS_ORDERED, 20, 0, 100_000)
        po('PO-PART', PurchaseOrder.STATUS_PARTIAL, 10, 4, 100_000)
        po('PO-CANC', PurchaseOrder.STATUS_CANCELED, 5, 0, 100_000)
        db.session.commit()
        return seed


def test_an_order_sent_to_the_supplier_counts_as_open(app, purchase_orders):
    from app.services.report_service import ReportService

    with app.app_context():
        data = ReportService().purchasing(purchase_orders['company_id'])

    assert data['open_pos'] == 3, (
        'draft + ordered + partial are all open; the one actually with the '
        f"supplier was being dropped (got {data['open_pos']})")


def test_outstanding_compares_like_with_like(app, purchase_orders):
    """Both sides ex-VAT: what is ordered but not yet in the warehouse."""
    from app.services.report_service import ReportService

    with app.app_context():
        data = ReportService().purchasing(purchase_orders['company_id'])

    # ex-VAT ordered on live POs: (10 + 20 + 10) x 100,000 = 4,000,000
    # ex-VAT received:                        4 x 100,000 =   400,000
    assert data['received_value'] == 400_000
    assert data['outstanding'] == 3_600_000, (
        'outstanding mixes a VAT-inclusive total with an ex-VAT receipt, so '
        f"it carries the VAT on everything (got {data['outstanding']:,.0f})")


def test_a_cancelled_order_is_not_outstanding(app, purchase_orders):
    """Nothing is owed on an order that was called off."""
    from app.services.report_service import ReportService

    with app.app_context():
        data = ReportService().purchasing(purchase_orders['company_id'])

    assert data['po_count'] == 3, 'the cancelled order is still being counted'
