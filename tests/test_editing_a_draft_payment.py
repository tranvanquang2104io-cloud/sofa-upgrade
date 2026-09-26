"""A draft payment's lines can be corrected; a confirmed one still cannot.

`edit_payment` updated dates, method and notes and left the line items alone —
"items/financials are locked to contract values". For a CONFIRMED payment that
is clearly right: an accounting record that can be silently edited is worth
less than one that shows it was corrected.

For a draft it was wrong, and the ledger deferred it on the grounds that it is
the same question as §3.2 (correcting a confirmed payment) and §3.4 (the
supplier side). The accounting review settled that: a draft is not in the books
yet — `create_material`-style bookkeeping has not happened, nothing has been
declared, `can_edit()` already allows editing an unconfirmed slip — so
correcting one is not correcting an accounting record at all. The three are not
one question; two of them are.

What a clerk faced today: a wrong quantity on a line, no field to fix it, and
no explanation. The answer was to cancel the slip and raise another, which
burns a document number and leaves a cancelled record somebody has to explain.

Confirmed payments are unchanged, and pinned here so that opening the draft
case cannot quietly open the other.
"""
import datetime as dt

import pytest


@pytest.fixture()
def draft_payment(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-EDIT',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-EDIT', report_date=dt.date(2026, 9, 1),
            payment_date=dt.date(2026, 9, 1), payment_type='advance',
            items=[{'name': 'Thi công khung ghế', 'unit': 'bộ',
                    'quantity': 1, 'unit_price': 12_000_000,
                    'total': 12_000_000}],
            subtotal=12_000_000, vat_rate=8, vat_amount=960_000,
            amount=12_960_000, is_confirmed=False)
        db.session.add(payment)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'payment_id': str(payment.id)}


def _edit(client, payment_id, **extra):
    data = {
        'report_number': 'TT-EDIT',
        'report_date': '2026-09-01',
        'payment_date': '2026-09-01',
        'vat_rate': '8',
    }
    data.update(extra)
    return client.post(f'/payment/{payment_id}/edit', data=data,
                       follow_redirects=True)


def test_a_draft_payment_s_lines_can_be_corrected(app, client, login,
                                                  draft_payment):
    from app.models.models import PaymentReport

    login('admin')
    _edit(client, draft_payment['payment_id'],
          **{'item_name[]': ['Thi công khung ghế'],
             'item_quantity[]': ['2'],          # was 1
             'item_price[]': ['12000000']})

    with app.app_context():
        payment = PaymentReport.query.get(draft_payment['payment_id'])
        assert float(payment.items[0]['quantity']) == 2, (
            'the corrected quantity was ignored, so the clerk still has to '
            'cancel the slip and raise another')


def test_the_totals_follow_the_corrected_lines(app, client, login,
                                               draft_payment):
    """A line the totals do not follow is worse than a locked line.

    It would show a quantity of 2 beside an amount for 1, and both would look
    equally authoritative.
    """
    from app.models.models import PaymentReport

    login('admin')
    _edit(client, draft_payment['payment_id'],
          **{'item_name[]': ['Thi công khung ghế'],
             'item_quantity[]': ['2'],
             'item_price[]': ['12000000']})

    with app.app_context():
        payment = PaymentReport.query.get(draft_payment['payment_id'])
        assert float(payment.subtotal) == 24_000_000
        assert float(payment.vat_amount) == 1_920_000
        assert float(payment.amount) == 25_920_000


def test_a_confirmed_payment_s_lines_are_still_untouchable(app, client, login,
                                                           draft_payment):
    """The half that must NOT move."""
    from app.config import db
    from app.models.models import PaymentReport

    with app.app_context():
        payment = PaymentReport.query.get(draft_payment['payment_id'])
        payment.is_confirmed = True
        db.session.commit()

    login('admin')
    _edit(client, draft_payment['payment_id'],
          **{'item_name[]': ['Thi công khung ghế'],
             'item_quantity[]': ['99'],
             'item_price[]': ['12000000']})

    with app.app_context():
        payment = PaymentReport.query.get(draft_payment['payment_id'])
        assert float(payment.items[0]['quantity']) == 1, (
            'a confirmed payment was silently rewritten')
        assert float(payment.amount) == 12_960_000


def test_sending_no_lines_leaves_the_existing_ones_alone(app, client, login,
                                                         draft_payment):
    """A screen that does not offer the fields must not wipe them.

    The edit form is reached from more than one place, and a POST without
    `item_name[]` means "I did not touch the lines", not "delete them".
    """
    from app.models.models import PaymentReport

    login('admin')
    _edit(client, draft_payment['payment_id'], notes='Ghi chú mới')

    with app.app_context():
        payment = PaymentReport.query.get(draft_payment['payment_id'])
        assert payment.items, 'the line items were wiped by an unrelated edit'
        assert float(payment.amount) == 12_960_000


def test_the_edit_screen_offers_the_line_fields_for_a_draft(app, client, login,
                                                            draft_payment):
    """Checked, because a field nothing renders is a field nobody has."""
    login('admin')
    body = client.get(
        f"/payment/{draft_payment['payment_id']}/edit").get_data(as_text=True)
    assert 'name="item_quantity[]"' in body, (
        'the draft can be corrected and the screen shows no line fields')
