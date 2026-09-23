"""HỢP ĐỒNG NGUYÊN TẮC (framework agreement) and its release orders.

THE BUSINESS PROBLEM
--------------------
Today every approved quotation produces a full contract. When a framework
agreement already governs the relationship, re-negotiating a whole contract
per order is wasted paperwork.

THE DOCUMENT MODEL, AND WHY IT IS NOT A PHỤ LỤC
-----------------------------------------------
A phụ lục (BLDS 2015 Đ.403) exists to *detail or amend a term of one
contract*. It is the right instrument for refreshing a price list; it is
strained as a repeating per-transaction artifact.

The per-order document is an **ĐƠN ĐẶT HÀNG** (order confirmation). Once
accepted it is itself a complete contract for that transaction (BLDS 2015
Đ.386 offer + Đ.393 acceptance), inheriting the framework's general terms by
citing its number and date.

The decisive constraint is tax, not contract law: **NĐ 123/2020 Đ.9** ties
invoice timing to a specific delivery and requires an invoice per delivery for
repeated shipments. A HĐNT carries no quantity, price or date, so it cannot
substantiate a hóa đơn GTGT on its own. The chain must be:

    HĐNT  →  ĐƠN ĐẶT HÀNG  →  biên bản giao nhận  →  hóa đơn GTGT

WHAT IS INHERITED
-----------------
Price (from the agreement's price list as at the order date), payment terms
and delivery terms flow down. Quantity, specification, delivery date and the
document's own number/date are release-specific. Prices are SNAPSHOTTED onto
the confirmation, so a later price revision never rewrites a past order.
"""
import logging
from datetime import date

from app.config.database import db
from app.models.models import (
    MasterAgreement,
    MasterAgreementPriceLine,
    OrderConfirmation,
)
from app.services.money import compute_totals, subtotal_from_items

logger = logging.getLogger(__name__)

# Workflow actions this module contributes.
ACTION_CONFIRMATION_CREATE = 'order_confirmation.create'

# Document kinds an order can take at the "contract" step.
DOC_CONTRACT = 'contract'
DOC_ORDER_CONFIRMATION = 'order_confirmation'


def product_key(name):
    """Normalized key for price-list matching (mirrors MaterialNorm)."""
    return (name or '').strip().lower()


class AgreementService:
    """Framework agreements and the release orders issued under them."""

    # ---- agreements --------------------------------------------------

    @staticmethod
    def find_active_for_customer(company_id, customer_id, on_date=None):
        """The agreement governing this customer on ``on_date``, if any.

        Returns None when the customer has no usable framework agreement, in
        which case the order follows the ordinary contract route.
        """
        if not customer_id:
            return None
        on_date = on_date or date.today()

        candidates = MasterAgreement.query.filter_by(
            company_id=company_id, customer_id=customer_id,
            status=MasterAgreement.STATUS_ACTIVE,
        ).order_by(MasterAgreement.effective_from.desc()).all()

        for agreement in candidates:
            if agreement.is_effective_on(on_date):
                return agreement
        return None

    @staticmethod
    def activate(agreement):
        if agreement.status not in (MasterAgreement.STATUS_DRAFT,
                                    MasterAgreement.STATUS_SUSPENDED):
            raise ValueError('Only a draft or suspended agreement can be activated')
        agreement.status = MasterAgreement.STATUS_ACTIVE
        db.session.commit()
        return agreement

    @staticmethod
    def suspend(agreement, reason=None):
        """Block NEW releases without ending the agreement.

        Real need: a customer in payment dispute should not be able to place
        new orders, but the relationship is not over.
        """
        if agreement.status != MasterAgreement.STATUS_ACTIVE:
            raise ValueError('Only an active agreement can be suspended')
        agreement.status = MasterAgreement.STATUS_SUSPENDED
        if reason:
            agreement.notes = ((agreement.notes or '') +
                               f'\n[Suspended] {reason}').strip()
        db.session.commit()
        return agreement

    @staticmethod
    def terminate(agreement, reason=None):
        agreement.status = MasterAgreement.STATUS_TERMINATED
        if reason:
            agreement.notes = ((agreement.notes or '') +
                               f'\n[Terminated] {reason}').strip()
        db.session.commit()
        return agreement

    # ---- pricing -----------------------------------------------------

    @staticmethod
    def price_for(agreement, name, on_date=None):
        """Agreed price line for a product on a date, or None.

        Line-level validity means a revision closes the old line rather than
        mutating it, so historical orders still resolve to their own price.
        """
        if agreement is None:
            return None
        on_date = on_date or date.today()
        key = product_key(name)

        lines = MasterAgreementPriceLine.query.filter_by(
            agreement_id=agreement.id, product_key=key,
        ).all()

        for line in lines:
            if line.effective_from and on_date < line.effective_from:
                continue
            if line.effective_to and on_date > line.effective_to:
                continue
            return line
        return None

    @classmethod
    def apply_agreement_prices(cls, agreement, items, on_date=None):
        """Rewrite item prices from the agreement's price list.

        An absolute agreed price wins; otherwise a discount percentage is
        applied to the quoted price. Items with no price line are left as they
        are, so an agreement need only cover the products it actually prices.
        """
        if agreement is None or not items:
            return items or []

        priced = []
        for item in items:
            item = dict(item)
            line = cls.price_for(agreement, item.get('name'), on_date)
            if line is not None:
                if line.agreed_unit_price is not None:
                    item['unit_price'] = float(line.agreed_unit_price)
                    item['price_source'] = 'agreement'
                elif line.discount_pct is not None:
                    base = float(item.get('unit_price') or 0)
                    item['unit_price'] = round(
                        base * (100 - float(line.discount_pct)) / 100, 2)
                    item['price_source'] = 'agreement_discount'
                qty = float(item.get('quantity') or 0)
                item['total'] = round(qty * float(item['unit_price']), 2)
            priced.append(item)
        return priced

    # ---- the routing decision ---------------------------------------

    @staticmethod
    def resolve_document_kind(order, on_date=None):
        """Which document should this order's 'contract' step produce?

        Returns ``(kind, agreement)``. An order whose customer has no active
        framework agreement keeps producing an ordinary Contract, so existing
        customers and historical orders need no migration at all.
        """
        agreement = AgreementService.find_active_for_customer(
            order.company_id, order.customer_id, on_date)
        if agreement is None:
            return DOC_CONTRACT, None
        return DOC_ORDER_CONFIRMATION, agreement

    # ---- release orders ----------------------------------------------

    @classmethod
    def create_confirmation(cls, order, agreement, items, confirmation_number,
                            confirmation_date=None, quotation_id=None,
                            vat_rate=None, shipping_fee=0, another_fee=0,
                            delivery_date=None, delivery_address=None,
                            notes=None, company=None):
        """Issue an ĐƠN ĐẶT HÀNG under ``agreement``."""
        confirmation_date = confirmation_date or date.today()

        if not agreement.is_effective_on(confirmation_date):
            raise ValueError(
                f'Framework agreement {agreement.agreement_number} is not in '
                f'effect on {confirmation_date}'
            )

        existing = OrderConfirmation.query.filter_by(
            company_id=order.company_id,
            confirmation_number=confirmation_number).first()
        if existing:
            raise ValueError(
                f'Order confirmation {confirmation_number} already exists')

        priced_items = cls.apply_agreement_prices(agreement, items,
                                                  confirmation_date)
        totals = compute_totals(
            subtotal=subtotal_from_items(priced_items),
            vat_rate=vat_rate,
            shipping_fee=shipping_fee,
            another_fee=another_fee,
            company=company,
        )

        confirmation = OrderConfirmation(
            order_id=order.id,
            company_id=order.company_id,
            master_agreement_id=agreement.id,
            quotation_id=quotation_id,
            confirmation_number=confirmation_number,
            confirmation_date=confirmation_date,
            # Snapshot: the printed document must keep citing what it cited.
            cited_agreement_number=agreement.agreement_number,
            cited_agreement_date=agreement.signed_date or agreement.effective_from,
            items=priced_items,
            subtotal=totals['subtotal'],
            vat_rate=totals['vat_rate'],
            vat_amount=totals['vat_amount'],
            shipping_fee=totals['shipping_fee'],
            another_fee=totals['another_fee'],
            total_amount=totals['total_amount'],
            delivery_date=delivery_date,
            delivery_address=delivery_address,
            payment_terms=agreement.payment_terms,
            notes=notes,
        )
        db.session.add(confirmation)
        db.session.commit()
        logger.info("Order confirmation %s created under agreement %s",
                    confirmation_number, agreement.agreement_number)
        return confirmation

    @staticmethod
    def confirm(confirmation):
        """Accept the order — the moment it becomes a binding contract.

        Marks the order's lifecycle as contract-created AND contract-signed:
        an accepted ĐƠN ĐẶT HÀNG evidences offer + acceptance in one step,
        with no separate signing ceremony.
        """
        if not confirmation.can_confirm():
            raise ValueError('Order confirmation cannot be confirmed')

        from app.repositories.repository import LifecycleStatusRepository
        from datetime import datetime

        confirmation.status = OrderConfirmation.STATUS_CONFIRMED

        lifecycle = LifecycleStatusRepository().get_or_create_for_order(
            confirmation.order_id)
        now = datetime.utcnow()
        if not lifecycle.contract_created:
            lifecycle.contract_created = True
            lifecycle.contract_created_at = now
        if not lifecycle.contract_signed:
            lifecycle.contract_signed = True
            lifecycle.contract_signed_at = now

        db.session.add(lifecycle)
        db.session.commit()

        # An Đơn đặt hàng is this order's commitment, exactly as a signed
        # contract is on the ordinary path — so it starts the workshop the same
        # way. Without this the job never got a production plan, and its
        # materials were never taken off stock.
        from app.services.services import ProductionPlanService
        ProductionPlanService().create_from_contract(confirmation)

        return confirmation

    @staticmethod
    def cancel(confirmation, reason=None):
        from datetime import datetime
        if not confirmation.can_cancel():
            raise ValueError('Order confirmation cannot be canceled')
        confirmation.status = OrderConfirmation.STATUS_CANCELED
        confirmation.is_canceled = True
        confirmation.is_active = False
        confirmation.canceled_at = datetime.utcnow()
        confirmation.canceled_reason = reason
        db.session.commit()
        return confirmation
