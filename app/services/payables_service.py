"""Supplier invoices, payments and the 3-way match — the "Pay" of P2P.

WHAT WAS MISSING
----------------
The procurement chain ran PR → PO → GR → stock and then stopped. There was no
supplier invoice, no payable and no payment, so a purchase could never be
closed out: the sales side had ``PaymentReport`` for customer money, the buy
side had nothing equivalent.

THE 3-WAY MATCH
---------------
Compared per PO LINE, because that is where real discrepancies live:

    ordered   (PurchaseOrderLine.quantity_ordered)
    received  (PurchaseOrderLine.quantity_received, from goods receipts)
    invoiced  (PurchaseOrderLine.quantity_invoiced, from supplier invoices)

plus unit price on the invoice against unit price on the PO.

WARN, DO NOT BLOCK. SAP blocks an out-of-tolerance invoice for payment via a
tolerance-key configuration. For a single SME that is both over-engineered and
hostile: the usual cause of a mismatch is paperwork arriving out of order, not
fraud. So a discrepancy is recorded on the invoice as ``match_status`` and
shown to a human, who decides. Tolerances are two constants, not a table.

DELIBERATELY NOT BUILT (would be over-engineering here): GR/IR clearing
accounts and journal postings (there is no general ledger in this app),
configurable tolerance keys, multi-PO or PO-less invoices, supplier credit
notes, foreign currency, and aging/statement reporting.
"""
import logging
from decimal import Decimal

from app.config.database import db
from app.models.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierPayment,
    SupplierPaymentAllocation,
)

logger = logging.getLogger(__name__)


def _round_dong(value):
    """Round to whole đồng the way the rest of the product rounds.

    This used to be a bare `.quantize(Decimal('1'))`, which takes Decimal's
    DEFAULT rounding — ROUND_HALF_EVEN. `money.py` rounds ROUND_HALF_UP, so on
    an exact half a payable rounded down to even while the matching receivable
    rounded up, and which way depended on whether the preceding digit happened
    to be odd. One đồng, unpredictably, in one product.

    Going through the shared rule rather than copying its constant means the
    next money calculation inherits it instead of choosing again.
    """
    from app.services.money import ROUND_HALF_UP_RULE
    return value.quantize(Decimal('1'), rounding=ROUND_HALF_UP_RULE)


def _dec(value):
    return Decimal(str(value or 0))


class PayablesService:
    """Supplier invoices and payments against a purchase order."""

    # ---- invoices ----------------------------------------------------

    @staticmethod
    def create_invoice(po, invoice_number, invoice_date, lines,
                       invoice_series=None, vat_rate=None, supplier_id=None,
                       seller_tax_code=None, notes=None):
        """Record a supplier invoice against ``po``.

        ``lines``: list of dicts with ``po_line_id``, ``quantity``,
        ``unit_price`` (and optionally ``unit``).
        """
        if po is None:
            raise ValueError('Purchase order not found')
        if po.status == PurchaseOrder.STATUS_DRAFT:
            raise ValueError('Cannot invoice a purchase order that is still a draft')
        if po.status == PurchaseOrder.STATUS_CANCELED:
            # Cancelling means "nothing more is coming", not "what came does
            # not count". A part-received order can be cancelled — twelve of
            # twenty metres turn up and the supplier cannot fill the rest — and
            # refusing the invoice outright left the fabric on the shelf with
            # the supplier's hóa đơn GTGT nowhere to go: no payable, no input
            # VAT, and the stock figure describing events the money figure did
            # not. What stays refused is an order that received NOTHING, where
            # there is no delivery to bill for.
            received = sum(Decimal(str(line.quantity_received or 0))
                           for line in po.lines)
            if received <= 0:
                raise ValueError(
                    'Cannot invoice a canceled purchase order that never '
                    'received anything')
        if not lines:
            raise ValueError('An invoice must have at least one line')

        supplier_id = supplier_id or po.supplier_id
        if not supplier_id:
            raise ValueError('The purchase order has no supplier to invoice')

        duplicate = SupplierInvoice.query.filter_by(
            company_id=po.company_id, supplier_id=supplier_id,
            invoice_series=invoice_series, invoice_number=invoice_number,
        ).first()
        if duplicate:
            raise ValueError(
                f'Invoice {invoice_series or ""}/{invoice_number} from this '
                f'supplier has already been recorded'
            )

        rate = _dec(vat_rate if vat_rate is not None else po.vat_rate)

        invoice = SupplierInvoice(
            company_id=po.company_id, supplier_id=supplier_id, po_id=po.id,
            invoice_series=invoice_series, invoice_number=invoice_number,
            invoice_date=invoice_date, vat_rate=rate,
            seller_tax_code=seller_tax_code or getattr(po.supplier, 'tax_code', None),
            notes=notes,
        )
        db.session.add(invoice)
        db.session.flush()

        subtotal = Decimal('0')
        for raw in lines:
            po_line = PurchaseOrderLine.query.get(raw['po_line_id'])
            if po_line is None or str(po_line.po_id) != str(po.id):
                raise ValueError('Invoice line does not belong to this purchase order')

            qty = _dec(raw.get('quantity'))
            price = _dec(raw.get('unit_price', po_line.unit_price))
            if qty < 0 or price < 0:
                raise ValueError('Invoice quantity and price cannot be negative')

            line_total = qty * price
            subtotal += line_total

            db.session.add(SupplierInvoiceLine(
                invoice_id=invoice.id, po_line_id=po_line.id,
                material_id=po_line.material_id, quantity=qty,
                unit=raw.get('unit') or po_line.unit, unit_price=price,
                line_total=line_total,
            ))

            po_line.quantity_invoiced = _dec(po_line.quantity_invoiced) + qty

        invoice.subtotal = subtotal
        invoice.vat_amount = _round_dong(subtotal * rate / Decimal('100'))
        invoice.total_amount = subtotal + invoice.vat_amount

        PayablesService.evaluate_match(invoice)

        db.session.commit()
        logger.info("Supplier invoice %s recorded against PO %s",
                    invoice_number, po.po_number)
        return invoice

    @staticmethod
    def evaluate_match(invoice):
        """Run the 3-way match and record the verdict on the invoice.

        Never raises and never blocks — it annotates.
        """
        problems = []
        status = SupplierInvoice.MATCH_OK

        for line in invoice.lines:
            po_line = line.po_line
            if po_line is None:
                continue

            ordered = _dec(po_line.quantity_ordered)
            received = _dec(po_line.quantity_received)
            invoiced = _dec(po_line.quantity_invoiced)

            qty_tol = Decimal(str(SupplierInvoice.QTY_TOLERANCE_PCT)) / Decimal('100')

            # Invoiced more than ordered (beyond tolerance).
            if ordered > 0 and invoiced > ordered * (Decimal('1') + qty_tol):
                status = SupplierInvoice.MATCH_OVER_INVOICED
                problems.append(
                    f'{invoiced} invoiced against {ordered} ordered')
            # Invoiced more than actually received: the goods receipt is the
            # gate, so this is the classic "billed for goods not delivered".
            elif invoiced > received * (Decimal('1') + qty_tol):
                if status == SupplierInvoice.MATCH_OK:
                    status = SupplierInvoice.MATCH_NO_RECEIPT
                problems.append(
                    f'{invoiced} invoiced but only {received} received')

            # Unit price variance against the PO.
            po_price = _dec(po_line.unit_price)
            inv_price = _dec(line.unit_price)
            if po_price > 0:
                variance = abs(inv_price - po_price) / po_price * Decimal('100')
                if variance > Decimal(str(SupplierInvoice.PRICE_TOLERANCE_PCT)):
                    if status == SupplierInvoice.MATCH_OK:
                        status = SupplierInvoice.MATCH_PRICE_VARIANCE
                    problems.append(
                        f'price {inv_price} vs ordered {po_price} '
                        f'({variance.quantize(Decimal("0.01"))}%)')

        invoice.match_status = status
        invoice.match_notes = '; '.join(problems) if problems else None
        return status, problems

    @staticmethod
    def confirm_invoice(invoice):
        if invoice.status != SupplierInvoice.STATUS_DRAFT:
            raise ValueError('Only a draft invoice can be confirmed')
        invoice.status = SupplierInvoice.STATUS_CONFIRMED
        db.session.commit()
        return invoice

    @staticmethod
    def cancel_invoice(invoice, reason=None):
        """Cancelling releases the quantities it had claimed."""
        if invoice.status == SupplierInvoice.STATUS_CANCELED:
            return invoice
        if invoice.allocations:
            raise ValueError(
                'Cannot cancel an invoice that has payments allocated to it')

        for line in invoice.lines:
            po_line = line.po_line
            if po_line is not None:
                po_line.quantity_invoiced = max(
                    Decimal('0'),
                    _dec(po_line.quantity_invoiced) - _dec(line.quantity))

        invoice.status = SupplierInvoice.STATUS_CANCELED
        if reason:
            invoice.notes = ((invoice.notes or '') + f'\n[Canceled] {reason}').strip()
        db.session.commit()
        return invoice

    # ---- payments ----------------------------------------------------

    @staticmethod
    def create_payment(company_id, supplier_id, payment_number, payment_date,
                       amount, method=SupplierPayment.METHOD_TRANSFER,
                       reference_number=None, notes=None):
        if _dec(amount) <= 0:
            raise ValueError('Payment amount must be positive')

        duplicate = SupplierPayment.query.filter_by(
            company_id=company_id, payment_number=payment_number).first()
        if duplicate:
            raise ValueError(f'Payment {payment_number} already exists')

        payment = SupplierPayment(
            company_id=company_id, supplier_id=supplier_id,
            payment_number=payment_number, payment_date=payment_date,
            amount=_dec(amount), method=method,
            reference_number=reference_number, notes=notes,
        )
        db.session.add(payment)
        db.session.commit()
        return payment

    @staticmethod
    def allocate(payment, invoice, amount):
        """Apply part of a payment to an invoice.

        Refuses to allocate more than the payment holds or more than the
        invoice still owes — the two invariants that keep "is it paid?"
        answerable.
        """
        amount = _dec(amount)
        if amount <= 0:
            raise ValueError('Allocated amount must be positive')
        if str(payment.supplier_id) != str(invoice.supplier_id):
            raise ValueError('Payment and invoice belong to different suppliers')
        if amount > payment.unallocated_amount:
            raise ValueError(
                f'Only {payment.unallocated_amount} of this payment is unallocated')
        if amount > invoice.amount_outstanding + _dec(0):
            raise ValueError(
                f'Invoice only has {invoice.amount_outstanding} outstanding')

        existing = SupplierPaymentAllocation.query.filter_by(
            payment_id=payment.id, invoice_id=invoice.id).first()
        if existing:
            existing.allocated_amount = _dec(existing.allocated_amount) + amount
        else:
            db.session.add(SupplierPaymentAllocation(
                payment_id=payment.id, invoice_id=invoice.id,
                allocated_amount=amount))

        db.session.commit()
        return payment

    @staticmethod
    def confirm_payment(payment):
        if payment.status != SupplierPayment.STATUS_DRAFT:
            raise ValueError('Only a draft payment can be confirmed')
        payment.status = SupplierPayment.STATUS_CONFIRMED
        db.session.commit()
        return payment

    # ---- PO-level status --------------------------------------------

    @staticmethod
    def invoice_status(po):
        """'nothing_to_invoice' | 'to_invoice' | 'fully_invoiced'."""
        lines = po.lines or []
        if not lines:
            return 'nothing_to_invoice'

        received = sum((_dec(l.quantity_received) for l in lines), Decimal('0'))
        invoiced = sum((_dec(l.quantity_invoiced) for l in lines), Decimal('0'))

        if invoiced <= 0:
            return 'nothing_to_invoice' if received <= 0 else 'to_invoice'
        if invoiced >= received and all(
                _dec(l.quantity_invoiced) >= _dec(l.quantity_ordered) for l in lines):
            return 'fully_invoiced'
        return 'to_invoice'

    @staticmethod
    def payment_status(po):
        """'not_invoiced' | 'not_paid' | 'partially_paid' | 'paid'."""
        invoices = [i for i in (po.invoices or [])
                    if i.status == SupplierInvoice.STATUS_CONFIRMED]
        if not invoices:
            return 'not_invoiced'

        total = sum((_dec(i.total_amount) for i in invoices), Decimal('0'))
        paid = sum((i.amount_paid for i in invoices), Decimal('0'))

        if paid <= 0:
            return 'not_paid'
        if paid >= total:
            return 'paid'
        return 'partially_paid'

    @staticmethod
    def outstanding_for_supplier(company_id, supplier_id):
        """What the business still owes this supplier on confirmed invoices."""
        invoices = SupplierInvoice.query.filter_by(
            company_id=company_id, supplier_id=supplier_id,
            status=SupplierInvoice.STATUS_CONFIRMED).all()
        return sum((i.amount_outstanding for i in invoices), Decimal('0'))
