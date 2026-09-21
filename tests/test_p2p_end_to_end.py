"""Procure-to-pay, correct to the đồng at every step.

One purchase walked the whole way — purchase order, goods receipt, supplier
invoice, payment — with every figure asserted against hand-computed values,
and the stock and moving-average cost checked at each point where they move.

The numbers, fixed once so a drift anywhere fails:

    order   100 m velvet @ 250,000  = 25,000,000  + VAT 8% 2,000,000 = 27,000,000
    receive  60 m                   → stock 60 m, average cost 250,000
    invoice  60 m @ 250,000         = 15,000,000  + VAT 8% 1,200,000 = 16,200,000
    pay      10,000,000             → outstanding 6,200,000

Then the second receipt at a different price, which is the only way the
average cost can be wrong without anybody noticing:

    receive  40 m @ 300,000         → stock 100 m, average (60x250k + 40x300k)/100
                                    = 270,000
"""
import datetime as dt
from decimal import Decimal

import pytest

from app.models.models import PurchaseOrder, SupplierInvoice
from app.services.payables_service import PayablesService
from app.services.procurement_service import ProcurementService

TODAY = dt.date(2026, 6, 20)

QTY_ORDERED = 100
PRICE = 250_000
ORDER_NET = QTY_ORDERED * PRICE            # 25,000,000
ORDER_VAT = 2_000_000
ORDER_GROSS = 27_000_000

QTY_RECEIVED = 60
INVOICE_NET = QTY_RECEIVED * PRICE         # 15,000,000
INVOICE_VAT = 1_200_000
INVOICE_GROSS = 16_200_000

PAID = 10_000_000
OUTSTANDING = INVOICE_GROSS - PAID         # 6,200,000

SECOND_QTY = 40
SECOND_PRICE = 300_000
BLENDED_COST = 270_000


@pytest.fixture()
def p2p(app, seed):
    """An ordered PO for 100 m @ 250,000, nothing received yet."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialUnit, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-P2P', name='NCC Vải Nhung',
                            tax_code='0109876543')
        unit = MaterialUnit(company_id=seed['company_id'], name='mét')
        category = MaterialCategory(company_id=seed['company_id'], name='Vải')
        db.session.add_all([supplier, unit, category])
        db.session.flush()

        material = Material(company_id=seed['company_id'],
                            material_code='VAI-NHUNG', name='Vải nhung xanh',
                            unit_id=unit.id, category_id=category.id)
        db.session.add(material)
        db.session.flush()

        order = PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            store_id=seed['store_id'], po_number='PO-P2P', order_date=TODAY,
            vat_rate=8, status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(order)
        db.session.flush()

        line = PurchaseOrderLine(
            po_id=order.id, material_id=material.id,
            quantity_ordered=QTY_ORDERED, quantity_received=0,
            quantity_invoiced=0, unit='mét', unit_price=PRICE,
            line_total=ORDER_NET)
        db.session.add(line)
        db.session.commit()

        return {'po_id': str(order.id), 'line_id': str(line.id),
                'material_id': str(material.id),
                'supplier_id': str(supplier.id), **seed}


def _po(po_id):
    return PurchaseOrder.query.get(po_id)


def _material(material_id):
    from app.models.models import Material
    return Material.query.get(material_id)


def _stock(material_id, company_id):
    from app.models.models import MaterialStock
    rows = MaterialStock.query.filter_by(material_id=material_id).all()
    return sum(float(r.current_quantity or 0) for r in rows)


# --- the order ------------------------------------------------------------

def test_the_order_line_total_is_quantity_times_price(app, p2p):
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(p2p['line_id'])
        assert float(line.line_total) == ORDER_NET


def test_the_order_gross_adds_vat_to_the_net(app, p2p):
    from app.services.money import compute_totals

    totals = compute_totals(subtotal=ORDER_NET, vat_rate=8)
    assert totals['vat_amount'] == ORDER_VAT
    assert totals['total_amount'] == ORDER_GROSS


# --- receiving ------------------------------------------------------------

@pytest.fixture()
def after_receipt(app, p2p):
    """60 of the 100 metres received."""
    with app.app_context():
        ProcurementService().receive(_po(p2p['po_id']),
                                     {p2p['line_id']: QTY_RECEIVED},
                                     store_id=p2p['store_id'])
        return p2p


def test_receiving_raises_stock_by_exactly_what_arrived(app, after_receipt):
    with app.app_context():
        assert _stock(after_receipt['material_id'],
                      after_receipt['company_id']) == QTY_RECEIVED


def test_the_first_receipt_sets_the_average_cost_to_the_order_price(
        app, after_receipt):
    with app.app_context():
        assert float(_material(after_receipt['material_id']).avg_cost) == PRICE


def test_a_partial_receipt_leaves_the_order_partially_received(app,
                                                               after_receipt):
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(after_receipt['line_id'])
        assert float(line.quantity_received) == QTY_RECEIVED
        assert float(line.quantity_ordered) - float(line.quantity_received) == 40


def test_a_second_receipt_at_another_price_blends_the_cost(app, after_receipt):
    """60 at 250,000 then 40 at 300,000 averages to 270,000."""
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(after_receipt['line_id'])
        line.unit_price = SECOND_PRICE
        db.session.commit()

        ProcurementService().receive(_po(after_receipt['po_id']),
                                     {after_receipt['line_id']: SECOND_QTY},
                                     store_id=after_receipt['store_id'])

        assert _stock(after_receipt['material_id'],
                      after_receipt['company_id']) == QTY_ORDERED
        assert float(_material(
            after_receipt['material_id']).avg_cost) == BLENDED_COST


# --- invoicing ------------------------------------------------------------

@pytest.fixture()
def after_invoice(app, after_receipt):
    with app.app_context():
        invoice = PayablesService.create_invoice(
            _po(after_receipt['po_id']), invoice_number='HD-NCC-1',
            invoice_date=TODAY,
            lines=[{'po_line_id': after_receipt['line_id'],
                    'quantity': QTY_RECEIVED, 'unit_price': PRICE}],
            vat_rate=8)
        PayablesService.confirm_invoice(invoice)
        return {'invoice_id': str(invoice.id), **after_receipt}


def _invoice(invoice_id):
    return SupplierInvoice.query.get(invoice_id)


def test_the_invoice_totals_match_hand_calculation(app, after_invoice):
    with app.app_context():
        invoice = _invoice(after_invoice['invoice_id'])
        assert float(invoice.subtotal) == INVOICE_NET
        assert float(invoice.vat_amount) == INVOICE_VAT
        assert float(invoice.total_amount) == INVOICE_GROSS


def test_invoicing_exactly_what_arrived_matches_cleanly(app, after_invoice):
    with app.app_context():
        assert _invoice(
            after_invoice['invoice_id']).match_status == SupplierInvoice.MATCH_OK


def test_the_invoiced_quantity_is_recorded_on_the_order_line(app,
                                                             after_invoice):
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        line = PurchaseOrderLine.query.get(after_invoice['line_id'])
        assert float(line.quantity_invoiced) == QTY_RECEIVED


def test_invoicing_more_than_arrived_is_flagged(app, after_receipt):
    """Warned, never blocked — that is the deliberate SME choice."""
    with app.app_context():
        invoice = PayablesService.create_invoice(
            _po(after_receipt['po_id']), invoice_number='HD-NCC-QUA',
            invoice_date=TODAY,
            lines=[{'po_line_id': after_receipt['line_id'],
                    'quantity': QTY_RECEIVED + 20, 'unit_price': PRICE}],
            vat_rate=8)
        assert invoice.match_status != SupplierInvoice.MATCH_OK
        assert invoice.id is not None, 'the invoice must still be recorded'


def test_a_price_above_tolerance_is_flagged(app, after_receipt):
    """250,000 ordered, 260,000 invoiced is 4% — over the 2% tolerance."""
    with app.app_context():
        invoice = PayablesService.create_invoice(
            _po(after_receipt['po_id']), invoice_number='HD-NCC-GIA',
            invoice_date=TODAY,
            lines=[{'po_line_id': after_receipt['line_id'],
                    'quantity': QTY_RECEIVED, 'unit_price': 260_000}],
            vat_rate=8)
        assert invoice.match_status != SupplierInvoice.MATCH_OK


# --- paying ---------------------------------------------------------------

def test_a_part_payment_leaves_the_rest_outstanding(app, after_invoice):
    with app.app_context():
        invoice = _invoice(after_invoice['invoice_id'])
        payment = PayablesService.create_payment(
            after_invoice['company_id'], after_invoice['supplier_id'],
            'CHI-1', TODAY, amount=PAID)
        PayablesService.allocate(payment, invoice, PAID)
        PayablesService.confirm_payment(payment)

        invoice = _invoice(after_invoice['invoice_id'])
        assert float(invoice.amount_paid) == PAID
        assert float(invoice.amount_outstanding) == OUTSTANDING
        assert invoice.is_paid is False


def test_paying_the_rest_settles_the_invoice(app, after_invoice):
    with app.app_context():
        invoice = _invoice(after_invoice['invoice_id'])
        for reference, amount in (('CHI-1', PAID), ('CHI-2', OUTSTANDING)):
            payment = PayablesService.create_payment(
                after_invoice['company_id'], after_invoice['supplier_id'],
                reference, TODAY, amount=amount)
            PayablesService.allocate(payment, invoice, amount)
            PayablesService.confirm_payment(payment)

        invoice = _invoice(after_invoice['invoice_id'])
        assert float(invoice.amount_outstanding) == 0
        assert invoice.is_paid is True


def test_what_we_owe_this_supplier_is_the_unpaid_part(app, after_invoice):
    with app.app_context():
        invoice = _invoice(after_invoice['invoice_id'])
        payment = PayablesService.create_payment(
            after_invoice['company_id'], after_invoice['supplier_id'],
            'CHI-1', TODAY, amount=PAID)
        PayablesService.allocate(payment, invoice, PAID)
        PayablesService.confirm_payment(payment)

        assert PayablesService.outstanding_for_supplier(
            after_invoice['company_id'],
            after_invoice['supplier_id']) == Decimal(OUTSTANDING)


def test_an_unconfirmed_payment_reduces_nothing(app, after_invoice):
    with app.app_context():
        invoice = _invoice(after_invoice['invoice_id'])
        payment = PayablesService.create_payment(
            after_invoice['company_id'], after_invoice['supplier_id'],
            'CHI-CHUA', TODAY, amount=PAID)
        PayablesService.allocate(payment, invoice, PAID)

        invoice = _invoice(after_invoice['invoice_id'])
        assert float(invoice.amount_outstanding) == INVOICE_GROSS
