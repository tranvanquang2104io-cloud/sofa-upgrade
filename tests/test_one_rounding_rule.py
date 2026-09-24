"""The two sides of the business must round a half-đồng the same way.

`money.py` rounds with ROUND_HALF_UP — the rule Vietnamese invoicing uses, and
the one every sales figure in the product follows. The supplier-invoice VAT was
computed with `.quantize(Decimal('1'))` and no rounding argument, which is
Decimal's default: ROUND_HALF_EVEN, banker's rounding.

So on an exact half a payable rounded DOWN to even while the matching
receivable rounded UP. One đồng, and only on exact halves — but it is the same
arithmetic performed two ways in one product, and the direction depends on
whether the preceding digit happens to be odd. A discrepancy nobody can predict
is worse to chase than a larger one that is consistent.

The fix is to use the shared helper rather than to copy its constant, so the
next money calculation inherits the rule instead of choosing again.
"""
import decimal

import pytest


def test_the_shared_helper_rounds_half_up():
    """The rule the rest of the product follows."""
    from app.services.money import _round

    assert _round(decimal.Decimal('0.005')) == decimal.Decimal('0.01')
    assert _round(decimal.Decimal('0.015')) == decimal.Decimal('0.02')


@pytest.mark.parametrize('subtotal, rate, expected', [
    # 8% of 6.25 is 0.5 exactly — half-even would give 0, half-up gives 1.
    (decimal.Decimal('6.25'), decimal.Decimal('8'), decimal.Decimal('1')),
    # 10% of 25 is 2.5 exactly — half-even would give 2, half-up gives 3.
    (decimal.Decimal('25'), decimal.Decimal('10'), decimal.Decimal('3')),
])
def test_vat_on_an_exact_half_rounds_up(subtotal, rate, expected):
    """Computed the way the payables service computes it."""
    from app.services.payables_service import _round_dong

    assert _round_dong(subtotal * rate / decimal.Decimal('100')) == expected


def test_a_recorded_invoice_rounds_its_vat_half_up(app, seed):
    """Through the service, not by reading the source.

    The first version of this scanned payables_service.py for a bare
    `.quantize(Decimal('1'))` — and then matched the phrase inside the
    docstring explaining why it was removed. Text that looks like code is not
    code; assert the behaviour instead.
    """
    import datetime as dt

    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )
    from app.services.payables_service import PayablesService

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-RND', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-RND', name='Vải nhung',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()

        order = PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_number='PO-RND', order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_ORDERED, vat_rate=10)
        db.session.add(order)
        db.session.flush()
        line = PurchaseOrderLine(po_id=order.id, material_id=material.id,
                                 quantity_ordered=1, quantity_received=1,
                                 unit_price=25)
        db.session.add(line)
        db.session.commit()

        # 10% of 25 is 2.5 exactly: half-even gives 2, half-up gives 3.
        invoice = PayablesService.create_invoice(
            order, invoice_number='0004444',
            invoice_date=dt.date(2026, 9, 20), vat_rate=10,
            lines=[{'po_line_id': str(line.id), 'quantity': 1,
                    'unit_price': 25}])
        vat = decimal.Decimal(str(invoice.vat_amount))

    assert vat == decimal.Decimal('3'), (
        f'VAT rounded to {vat}; the sales side would have rounded up to 3')
