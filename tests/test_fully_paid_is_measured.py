"""An order is paid in full when the money adds up, not when a slip says 'final'.

`mark_confirmed` set `fully_paid` and `completed` on any payment whose type is
`final`, with no comparison against what the order is worth or what has already
been collected. Paying the balance in two instalments is ordinary here, and it
produces two 'final' slips: confirming the first closed the order.

What makes it hard to notice is that the CASH figures stay right — the
receivable is computed from the payments, not from this flag. So the totals
agree while the work queue lies: the "chưa thanh toán đủ" filter stops listing
a customer who still owes money, and the completed count is overstated.

A second defect in the same place: the agreed value was resolved with
`Contract.query.filter_by(is_signed=True, is_canceled=False).first()` — no
`is_active` and no ORDER BY, so on a renegotiated order it could pick the
superseded contract, and which one it picked was whatever the database
returned first.
"""
import datetime as dt

import pytest


def _order(app, seed, code, value, advance_pct=0):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code=code,
                      title='Sofa góc L', total_amount=value)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True,
                                       handover_confirmed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number=f'HD-{code}', contract_date=dt.date(2026, 9, 1),
            contract_value=value, advance_percentage=advance_pct,
            is_signed=True, is_canceled=False, is_active=True))
        db.session.commit()
        return str(order.id)


def _pay(app, seed, order_id, number, amount, kind='final'):
    """Record a payment and confirm it through the service."""
    from app.config import db
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order_id,
            report_number=number, payment_type=kind,
            report_date=dt.date(2026, 9, 20), payment_date=dt.date(2026, 9, 20),
            amount=amount, remaining_amount=amount, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()
        PaymentReportService().mark_confirmed(str(payment.id), order_id)


def _lifecycle(app, order_id):
    from app.models.models import LifecycleStatus
    with app.app_context():
        return LifecycleStatus.query.filter_by(order_id=order_id).first()


def test_a_part_payment_does_not_close_the_order(app, seed):
    """20 million against a 50 million contract is not 'paid in full'."""
    order_id = _order(app, seed, 'PART', 50_000_000)
    _pay(app, seed, order_id, 'TT-1', 20_000_000)

    lifecycle = _lifecycle(app, order_id)
    assert not lifecycle.fully_paid, 'a part payment marked the order fully paid'
    assert not lifecycle.completed, 'a part payment completed the order'


def test_the_balance_closes_it(app, seed):
    order_id = _order(app, seed, 'BAL', 50_000_000)
    _pay(app, seed, order_id, 'TT-1', 20_000_000)
    _pay(app, seed, order_id, 'TT-2', 30_000_000)

    lifecycle = _lifecycle(app, order_id)
    assert lifecycle.fully_paid
    assert lifecycle.completed


def test_paying_the_whole_amount_at_once_still_closes_it(app, seed):
    """The ordinary case must not change."""
    order_id = _order(app, seed, 'WHOLE', 12_000_000)
    _pay(app, seed, order_id, 'TT-1', 12_000_000)

    assert _lifecycle(app, order_id).fully_paid


def test_an_advance_counts_towards_the_total(app, seed):
    """Money is money: a 30% advance plus the balance is payment in full."""
    order_id = _order(app, seed, 'ADV', 10_000_000, advance_pct=30)
    _pay(app, seed, order_id, 'TT-A', 3_000_000, kind='advance')
    _pay(app, seed, order_id, 'TT-B', 7_000_000)

    lifecycle = _lifecycle(app, order_id)
    assert lifecycle.advance_paid
    assert lifecycle.fully_paid


def test_the_agreed_value_comes_from_the_live_contract(app, seed):
    """A renegotiated order is worth what the CURRENT contract says."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract
    from app.services.services import order_agreed_value

    order_id = _order(app, seed, 'RENEG', 25_000_000)
    with app.app_context():
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order_id,
            contract_number='HD-RENEG-OLD', contract_date=dt.date(2026, 8, 1),
            contract_value=40_000_000, advance_percentage=0,
            is_signed=True, is_canceled=False, is_active=False))
        db.session.commit()

        order = Order.query.get(order_id)
        assert float(order_agreed_value(order)) == 25_000_000, (
            'the superseded contract was used as the order value')
