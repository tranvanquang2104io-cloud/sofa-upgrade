"""A date that is not set yet must not take the page down.

Found by opening every seeded record through the UI: three pages returned 500
with `'None' has no attribute 'strftime'`. A payment that has not been confirmed
has no `confirmed_date`, one that has not been cancelled has no `canceled_at`,
and the templates called `.strftime()` on them regardless.

The tests never caught it because a fixture that builds a payment tends to fill
in every field. Real data has holes in exactly the places the schema allows
them — which is what the demo seed is for.

This is the same shape as the `file_size / 1024` crash fixed earlier: a value
the schema permits to be NULL, used as though it never is. The guard is one
expression, and the em dash it falls back to already means "nothing recorded"
everywhere else in the product.
"""
import datetime as dt
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'


@pytest.fixture()
def order_with_pending_documents(app, seed):
    """An order whose handover and payment are still drafts.

    Draft is the state with the most empty dates, and the state every document
    passes through, so it is the one most likely to be opened.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, HandoverRecord, LifecycleStatus, PaymentReport,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-NULL',
                      title='Sofa góc')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-NULL', contract_date=dt.date(2026, 9, 1),
            contract_value=10_000_000, advance_percentage=0, is_signed=True))

        # CONFIRMED but with no confirmed_date — the combination the schema
        # permits and the templates assume away. This is the shape that took
        # three pages down when the demo data was opened; a fixture that fills
        # in every field never produces it.
        handover = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-NULL', report_date=dt.date(2026, 9, 10),
            handover_date=dt.date(2026, 9, 12),
            is_confirmed=True, confirmed_date=None)
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-NULL', payment_type='final',
            report_date=dt.date(2026, 9, 10),
            payment_date=dt.date(2026, 9, 10),
            amount=5_000_000, is_confirmed=True, confirmed_date=None)
        db.session.add_all([handover, payment])
        db.session.commit()

        return {**seed, 'order_id': str(order.id),
                'handover_id': str(handover.id),
                'payment_id': str(payment.id)}


def test_an_unconfirmed_payment_page_opens(client, login,
                                           order_with_pending_documents):
    login('admin')
    response = client.get(
        f"/payment/{order_with_pending_documents['payment_id']}")
    assert response.status_code == 200


def test_an_unconfirmed_handover_page_opens(client, login,
                                            order_with_pending_documents):
    login('admin')
    response = client.get(
        f"/handover/{order_with_pending_documents['handover_id']}")
    assert response.status_code == 200


def test_the_order_page_opens_with_pending_documents(client, login,
                                                     order_with_pending_documents):
    """The order screen renders both documents inline, so it breaks too."""
    login('admin')
    response = client.get(
        f"/orders/{order_with_pending_documents['order_id']}")
    assert response.status_code == 200


def test_a_missing_date_reads_as_nothing_recorded(client, login,
                                                  order_with_pending_documents):
    """Not blank: blank looks like a rendering fault."""
    login('admin')
    body = client.get(
        f"/payment/{order_with_pending_documents['payment_id']}").get_data(
            as_text=True)
    assert '—' in body


def test_no_template_calls_strftime_without_a_guard():
    """Closes the class rather than the three instances that crashed.

    A guard is either the inline `... if x else ...` form or an enclosing
    `{% if x %}`. Anything else is a page that dies the first time the field is
    empty — and every one of these fields is nullable in the schema.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'\{\{\s*([a-zA-Z_][\w.]*)\.strftime\(', text):
            expression = match.group(1)
            head = text[match.start():match.start() + 300].split('}}')[0]
            if ' if ' in head:
                continue
            before = text[max(0, match.start() - 250):match.start()]
            leaf = expression.split('.')[-1]
            if re.search(r'\{%\s*if[^%]*' + re.escape(leaf), before):
                continue
            line = text[:match.start()].count('\n') + 1
            offenders.append(
                f"{'/'.join(path.relative_to(TEMPLATES).parts)}:{line} {expression}")

    assert offenders == [], (
        'these call .strftime() on a value the schema allows to be NULL, so '
        f'the page dies the first time it is: {offenders}'
    )
