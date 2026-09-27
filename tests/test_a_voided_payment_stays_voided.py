"""A cancelled payment cannot be confirmed — including by posting to the URL.

`PaymentReport.can_confirm()` checks two things: not already confirmed, and
not cancelled. `payments/view.html` uses it to decide whether to show the
button. `PaymentReportService.mark_confirmed` checks only the first.

So the second condition lived entirely in a template. Hiding a button is a
convenience for the person looking at the screen; it is not a rule, and a POST
to the URL was never subject to it.

What that produced: confirm → cancel (the money goes back) → POST the confirm
URL again → `is_confirmed` True and `is_canceled` True at once, and the
lifecycle flags say the customer has paid. A record that says both things is
worse than either, because every screen downstream picks one.

This got worse with the void-with-a-reason work, and that is the honest shape
of it: cancelling a CONFIRMED payment was impossible before, so the sequence
could not be reached. Opening one door made a missing check on another door
reachable. A rule enforced only where it happened to be unreachable is not a
rule that was working — it was a rule nobody had tested.

Fixed in the SERVICE, not the route. The route is one of several ways in — the
approval queue performs the same action when a manager approves it — and a
check on the route would be a third place holding half the rule.
"""
import datetime as dt

import pytest


@pytest.fixture()
def a_cancelled_payment(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-VOIDC',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-VOIDC', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            amount=9_000_000, is_confirmed=False, is_canceled=True,
            canceled_at=dt.datetime(2026, 9, 5),
            canceled_reason='Ghi nhầm đơn')
        db.session.add(payment)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'payment_id': str(payment.id)}


def test_the_service_refuses_to_confirm_a_cancelled_payment(
        app, a_cancelled_payment):
    """In the service, because the route is only one of the ways in."""
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        with pytest.raises(ValueError):
            PaymentReportService().mark_confirmed(
                a_cancelled_payment['payment_id'],
                a_cancelled_payment['order_id'])

        payment = PaymentReport.query.get(a_cancelled_payment['payment_id'])
        assert payment.is_confirmed is False, (
            'a cancelled payment was confirmed, so the record says both at '
            'once and every screen downstream picks one')


def test_posting_to_the_url_does_not_get_round_the_hidden_button(
        app, client, login, a_cancelled_payment):
    """The button is hidden by `can_confirm()`; the rule must not live there."""
    from app.models.models import LifecycleStatus, PaymentReport

    login('admin')
    client.post(f"/payment/{a_cancelled_payment['payment_id']}/confirm",
                follow_redirects=True)

    with app.app_context():
        payment = PaymentReport.query.get(a_cancelled_payment['payment_id'])
        assert payment.is_confirmed is False

        lifecycle = LifecycleStatus.query.filter_by(
            order_id=a_cancelled_payment['order_id']).first()
        if lifecycle is not None:
            assert lifecycle.advance_paid is not True, (
                'the order was marked as having received an advance that was '
                'cancelled')


def test_the_whole_sequence_the_void_work_made_reachable(app, seed):
    """confirm → cancel → confirm again. The third step must refuse."""
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport
    from app.services.services import (
        PaymentReportService, order_amount_collected,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-SEQ',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-SEQ', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            amount=5_000_000, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()
        payment_id, order_id = str(payment.id), str(order.id)

        service = PaymentReportService()
        service.mark_confirmed(payment_id, order_id)
        service.cancel_payment(payment_id, order_id, reason='Ghi nhầm đơn')

        with pytest.raises(ValueError):
            service.mark_confirmed(payment_id, order_id)

        again = PaymentReport.query.get(payment_id)
        assert again.is_canceled is True

        # `is_confirmed` STAYS true, and that is right: the record has to show
        # this payment was once confirmed and then voided. That IS the audit
        # trail — Luật Kế toán 2015 Đ.27, corrected rather than erased. What
        # makes it stop counting as money is `is_canceled`, which
        # `order_amount_collected` filters on.
        #
        # The first version of this test asserted is_confirmed False and was
        # wrong about the design, not about a bug. Asserting the flag would
        # have pushed me into erasing the very evidence the void exists to
        # leave behind.
        assert again.is_confirmed is True
        assert float(order_amount_collected(order_id)) == 0, (
            'a voided payment is still counted as money received')


def test_an_ordinary_payment_still_confirms(app, seed):
    """The guard must not close the door it was not aimed at."""
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-OK',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-OK', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            amount=1_000_000, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()

        PaymentReportService().mark_confirmed(str(payment.id), str(order.id))
        assert PaymentReport.query.get(payment.id).is_confirmed is True
