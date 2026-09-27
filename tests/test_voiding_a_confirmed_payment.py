"""A confirmed payment can be voided with a reason — and everything it touched moves back.

The owner: "hủy có lý do rồi tạo lại, chứng từ hủy muốn hủy thì phải được
duyệt và hủy xong thì các data liên quan cũng phải được update lại."

What it cost to have no way back. A 9.703.200 advance confirmed against the
wrong order left the customer showing as having paid, understated the
receivable by that amount, and could be put right only by editing the
database. `can_cancel()` and `can_edit()` both required `not is_confirmed`,
and no unconfirm route existed anywhere.

Three parts, and the third is where the danger is:

* **A reason is mandatory.** Voiding money without one leaves the next reader
  — an inspector, or the same person in six months — with a hole and no
  explanation. Luật Kế toán 2015 Đ.27: corrected, never erased.
* **A staff user asks; a branch manager decides.** Already true of cancelling
  through `payment.cancel`, and it matters more here: this is the action that
  moves money back.
* **Everything the confirmation touched moves back.** The revert branch in
  `cancel_payment` handles ONLY `payment_type == 'advance'`, and it has never
  run at all — `can_cancel()` refused every confirmed payment, so the branch
  was dead code. Opening this door wakes a path nobody has executed, and it
  does half the job: void a FINAL payment and the order stays `completed`,
  `fully_paid` stays true, and the system says a customer has paid in full
  while their money has been given back.

`can_edit()` is deliberately NOT relaxed. Void and re-create, never edit in
place: an accounting record that can be silently rewritten is worth less than
one that shows it was corrected.
"""
import datetime as dt

import pytest


@pytest.fixture()
def order_paid_in_full(app, seed):
    """A contract, an advance and a final payment, both confirmed."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus, PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-VOID',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-VOID', contract_date=dt.date(2026, 9, 1),
            contract_value=30_000_000, is_signed=True, is_active=True))
        advance = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-ADV', report_date=dt.date(2026, 9, 2),
            payment_date=dt.date(2026, 9, 2), payment_type='advance',
            amount=9_000_000, is_confirmed=True)
        final = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-FIN', report_date=dt.date(2026, 9, 20),
            payment_date=dt.date(2026, 9, 20), payment_type='final',
            amount=21_000_000, is_confirmed=True)
        lifecycle = LifecycleStatus(order_id=order.id, contract_signed=True,
                                    advance_paid=True, fully_paid=True)
        db.session.add_all([advance, final, lifecycle])
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'advance_id': str(advance.id), 'final_id': str(final.id)}


# --------------------------------------------------------------------------
# It is possible at all, and it needs a reason.
# --------------------------------------------------------------------------

def test_a_confirmed_payment_can_be_voided(app, order_paid_in_full):
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        PaymentReportService().cancel_payment(
            order_paid_in_full['advance_id'], order_paid_in_full['order_id'],
            reason='Ghi nhầm sang đơn khác')

        voided = PaymentReport.query.get(order_paid_in_full['advance_id'])
        assert voided.is_canceled is True
        assert voided.canceled_reason == 'Ghi nhầm sang đơn khác'


def test_voiding_without_a_reason_is_refused(app, order_paid_in_full):
    """Money moved back and nothing says why is a hole in the record."""
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        with pytest.raises(ValueError):
            PaymentReportService().cancel_payment(
                order_paid_in_full['advance_id'],
                order_paid_in_full['order_id'], reason='')

        assert PaymentReport.query.get(
            order_paid_in_full['advance_id']).is_canceled is False


def test_the_record_is_kept_not_deleted(app, order_paid_in_full):
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        PaymentReportService().cancel_payment(
            order_paid_in_full['advance_id'], order_paid_in_full['order_id'],
            reason='Ghi nhầm')
        assert PaymentReport.query.get(
            order_paid_in_full['advance_id']) is not None, (
            'the slip was deleted; an inspector has nothing to look at')


def test_a_confirmed_payment_still_cannot_be_edited(app, order_paid_in_full):
    """Void and re-create, never rewrite."""
    from app.models.models import PaymentReport

    with app.app_context():
        assert PaymentReport.query.get(
            order_paid_in_full['advance_id']).can_edit() is False


# --------------------------------------------------------------------------
# Everything the confirmation touched moves back. The dangerous half.
# --------------------------------------------------------------------------

def test_voiding_the_final_payment_reopens_the_order(app, order_paid_in_full):
    """The branch that only handled advances, and had never run.

    Void a final payment and the order used to stay `completed` with
    `fully_paid` true — the system saying a customer has paid in full while
    their money has been given back.
    """
    from app.models.models import LifecycleStatus
    from app.services.services import PaymentReportService

    with app.app_context():
        PaymentReportService().cancel_payment(
            order_paid_in_full['final_id'], order_paid_in_full['order_id'],
            reason='Chuyển khoản bị hoàn')

        lifecycle = LifecycleStatus.query.filter_by(
            order_id=order_paid_in_full['order_id']).one()
        assert lifecycle.fully_paid is False, (
            'the final payment was voided and the order still says paid in '
            'full')


def test_voiding_the_advance_clears_the_advance_flag(app, order_paid_in_full):
    from app.models.models import LifecycleStatus
    from app.services.services import PaymentReportService

    with app.app_context():
        PaymentReportService().cancel_payment(
            order_paid_in_full['advance_id'], order_paid_in_full['order_id'],
            reason='Ghi nhầm')

        lifecycle = LifecycleStatus.query.filter_by(
            order_id=order_paid_in_full['order_id']).one()
        assert lifecycle.advance_paid is False


def test_the_receivable_goes_back_up(app, order_paid_in_full):
    """The figure the business actually reads.

    Understating what a customer owes by 9.000.000 is the harm; the flags are
    how the screens find out.
    """
    from app.services.services import order_amount_collected
    from app.services.services import PaymentReportService

    with app.app_context():
        before = float(order_amount_collected(
            order_paid_in_full['order_id']))
        PaymentReportService().cancel_payment(
            order_paid_in_full['advance_id'], order_paid_in_full['order_id'],
            reason='Ghi nhầm')
        after = float(order_amount_collected(order_paid_in_full['order_id']))

        assert before - after == 9_000_000, (
            f'collected went {before} -> {after}; the voided advance is still '
            'counted as money received')


def test_another_confirmed_advance_keeps_the_flag_set(app, order_paid_in_full):
    """Voiding one of two must not clear a flag the other still earns."""
    from app.config import db
    from app.models.models import LifecycleStatus, PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        db.session.add(PaymentReport(
            company_id=order_paid_in_full['company_id'],
            order_id=order_paid_in_full['order_id'],
            report_number='TT-ADV2', report_date=dt.date(2026, 9, 3),
            payment_date=dt.date(2026, 9, 3), payment_type='advance',
            amount=500_000, is_confirmed=True))
        db.session.commit()

        PaymentReportService().cancel_payment(
            order_paid_in_full['advance_id'], order_paid_in_full['order_id'],
            reason='Ghi nhầm')

        lifecycle = LifecycleStatus.query.filter_by(
            order_id=order_paid_in_full['order_id']).one()
        assert lifecycle.advance_paid is True, (
            'a second confirmed advance still exists and the flag was cleared')
