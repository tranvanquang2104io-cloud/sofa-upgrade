"""If an action cannot be undone, the dialog has to say so.

Measured across the confirmation dialogs: signing a contract warns that it
cannot be edited afterwards, cancelling an order and cancelling a contract both
say the action cannot be undone. Three others are equally permanent and said
nothing at all:

    approve_quotation   Quotation.can_cancel() requires `not is_approved`
    confirm_handover    HandoverRecord.can_cancel() requires `not is_confirmed`
    confirm_payment     PaymentReport.can_cancel() AND can_edit() both require
                        `not is_confirmed`, and there is no unconfirm route

The payment one matters most, and is the one that said least. Confirming a
receipt that never arrived understates the receivable permanently — see
REVIEW-2026Q3.md §3.2 — and the dialog asked only "are you sure?", which is
what every dialog asks. A user cannot distinguish a routine confirmation from a
one-way door by being asked whether they are sure.

The wording states the consequence rather than shouting. A warning that reads
as alarm gets clicked through exactly like one that reads as routine.
"""
import datetime as dt

import pytest

FINALITY = ('không thể hoàn tác', 'cannot be undone', 'không thể sửa',
            'cannot be edited', 'không thể huỷ', 'không thể hủy')


def _says_it_is_final(body, action_url):
    """Look only at the dialog whose form posts to `action_url`.

    Anchored on the URL rather than on the dialog's wording: the page renders
    in Vietnamese, so searching for the English question finds nothing, and
    searching for the endpoint NAME finds nothing either because url_for
    renders a path.
    """
    index = body.find(action_url)
    assert index != -1, f'{action_url} not found on the page'
    start = body.rfind('<div class="modal', 0, index)
    dialog = body[start:index + 800].lower()
    return any(phrase in dialog for phrase in FINALITY)


@pytest.fixture()
def order_with_documents(app, seed):
    """One order carrying a quotation, a handover and a payment, all pending."""
    from app.config import db
    from app.models import Order, Quotation
    from app.models.models import (
        Contract, HandoverRecord, LifecycleStatus, PaymentReport,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DLG',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, quotation_created=True, contract_created=True,
            contract_signed=True, advance_paid=True))

        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-DLG', quotation_date=dt.date(2026, 1, 1),
            total_amount=10_000_000)
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-DLG', contract_date=dt.date(2026, 1, 1),
            contract_value=10_000_000, is_signed=True)
        handover = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-DLG', report_date=dt.date(2026, 2, 1),
            handover_date=dt.date(2026, 2, 1))
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-DLG', report_date=dt.date(2026, 2, 1),
            payment_date=dt.date(2026, 2, 1), payment_type='final',
            amount=5_000_000)
        db.session.add_all([quotation, contract, handover, payment])
        db.session.commit()

        return {'order_id': str(order.id), 'quotation_id': str(quotation.id),
                'handover_id': str(handover.id), 'payment_id': str(payment.id),
                **seed}


def test_confirming_a_payment_says_it_is_permanent(client, login,
                                                   order_with_documents):
    """The one that can never be corrected said the least."""
    login("admin")
    body = client.get(
        f"/payment/{order_with_documents['payment_id']}").get_data(as_text=True)

    # Anchored on the dialog's own question, not on the endpoint name:
    # `url_for` renders a URL, so 'confirm_payment' never appears in the HTML.
    assert _says_it_is_final(body, f"/payment/{order_with_documents['payment_id']}/confirm"), (
        "confirming a payment cannot be undone or edited afterwards"
    )


def test_confirming_a_payment_shows_which_amount(client, login,
                                                 order_with_documents):
    """Agreeing to a permanent record of money without seeing the money."""
    login("admin")
    body = client.get(
        f"/payment/{order_with_documents['payment_id']}").get_data(as_text=True)
    assert '5,000,000' in body


def test_confirming_a_handover_says_it_is_permanent(client, login,
                                                    order_with_documents):
    login("admin")
    body = client.get(
        f"/handover/{order_with_documents['handover_id']}").get_data(as_text=True)

    assert _says_it_is_final(body, f"/handover/{order_with_documents['handover_id']}/confirm")


def test_approving_a_quotation_says_it_cannot_then_be_cancelled(
        client, login, order_with_documents):
    login("admin")
    body = client.get(
        f"/quotations/{order_with_documents['quotation_id']}/view"
    ).get_data(as_text=True)

    assert _says_it_is_final(body, f"/quotations/{order_with_documents['quotation_id']}/approve")


def test_the_existing_warnings_are_still_there(client, login,
                                               order_with_documents):
    """Signing and cancelling already said so; they must keep saying it."""
    login("admin")
    body = client.get(
        f"/orders/{order_with_documents['order_id']}").get_data(as_text=True)
    assert any(phrase in body.lower() for phrase in FINALITY)
