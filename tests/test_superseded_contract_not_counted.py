"""A contract that was replaced must not still count as revenue.

Renegotiating is ordinary: the customer changes the fabric, the price moves,
and a second contract is written for the same order. `create_contract` already
enforces one active contract per order — it sets `is_active = False` on the old
one — but it leaves `is_signed = True` and `is_canceled = False`, because the
old contract genuinely was signed and genuinely was not cancelled.

The reports filter on `is_signed` and `is_canceled` and never look at
`is_active`. So both contracts are summed, and one order books twice.

The rest of the product resolves "the contract" as the ACTIVE one — the
handover, the payment and the printed documents all do. The reports were the
only place that disagreed, which is what let this sit: the screens a user
compares against each other were consistent, and only the totals were wrong.

It lands hardest on exactly the customers who renegotiated, in the screen built
for chasing debt.
"""
import datetime as dt

import pytest


@pytest.fixture()
def renegotiated_order(app, seed):
    """One order, one superseded contract, one live contract."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-RENEG',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))

        # The first price, agreed and signed, then replaced.
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-OLD', contract_date=dt.date(2026, 9, 1),
            contract_value=29_300_000, advance_percentage=30,
            is_signed=True, is_canceled=False, is_active=False))
        # What the customer actually owes.
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-NEW', contract_date=dt.date(2026, 9, 5),
            contract_value=25_000_000, advance_percentage=30,
            is_signed=True, is_canceled=False, is_active=True))
        db.session.commit()
        return seed


def test_only_the_live_contract_is_booked(app, renegotiated_order):
    from app.services.report_service import ReportService

    with app.app_context():
        rows = ReportService()._booked_rows(renegotiated_order['company_id'])

    total = float(sum(value for _id, _name, value in rows))
    assert total == 25_000_000, (
        'the superseded contract is still counted, so this one order books '
        f'twice: booked {total:,.0f} instead of 25,000,000')


def test_the_customer_owes_what_the_live_contract_says(app,
                                                       renegotiated_order):
    """The screen built for the weekly debt-chasing job."""
    from app.services.report_service import ReportService

    with app.app_context():
        rows = ReportService().customer_receivables(
            renegotiated_order['company_id'])

    owed = sum(r['outstanding'] for r in rows)
    assert owed == 25_000_000, (
        f'the debt queue names {owed:,.0f} instead of 25,000,000')


def test_a_single_signed_contract_is_unaffected(app, seed):
    """The ordinary case must not change."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus
    from app.services.report_service import ReportService

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PLAIN',
                      title='Sofa băng')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-PLAIN', contract_date=dt.date(2026, 9, 1),
            contract_value=12_000_000, advance_percentage=0,
            is_signed=True, is_canceled=False, is_active=True))
        db.session.commit()

        rows = ReportService()._booked_rows(seed['company_id'])

    assert float(sum(v for _i, _n, v in rows)) == 12_000_000
