"""A document in a period already declared to the tax office cannot be rewritten.

A SME like this workshop files its VAT return quarterly (NĐ 126/2020 Đ.8-9)
and its corporate tax return by 31 March (Luật QLT 38/2019 Đ.44). Once a return
is filed, the figures in it are a public statement. Editing or cancelling a
document dated inside that period makes the system permanently disagree with
what was declared, and at an inspection there is nothing to explain the gap
with.

That is not a style preference: Luật Kế toán 2015 Đ.27 forbids erasing what a
record said. The lawful corrections are all forward-looking — a correcting
entry, a negative entry, or an additional one.

So the product gets one date: **"Khoá sổ đến ngày"**, set by whoever files the
returns. It is empty until somebody sets it, which means nothing changes for a
company that has not asked for this.

What the date does:

* a **draft** is untouched. It is not in the books yet, so it stays editable
  and deletable whatever its date — the same reason `can_edit()` already
  distinguishes confirmed from draft;
* a **confirmed** document dated on or before the date can no longer be edited
  or cancelled in place;
* refusing is not enough on its own. A refusal with no way forward is how a
  user ends up editing the database, so the message has to name the date, say
  who can change it, and point at the correction that IS allowed.

The adjustment document itself — an opposite entry dated today, referencing the
original — is the next step and is not in this file yet. Refusing first is the
half that stops the damage; offering the lawful route is the half that makes
the refusal usable, and building the second badly would be worse than building
it late.
"""
import datetime as dt

import pytest


@pytest.fixture()
def confirmed_payment(app, seed):
    """A payment dated in Q1, confirmed — the shape a filed return contains."""
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-CLOSED',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-Q1', report_date=dt.date(2026, 2, 10),
            payment_date=dt.date(2026, 2, 10), payment_type='advance',
            amount=9_703_200, is_confirmed=True)
        db.session.add(payment)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'payment_id': str(payment.id)}


def _close_books(app, company_id, through):
    from app.config import db
    from app.models import Company

    with app.app_context():
        company = Company.query.get(company_id)
        company.books_closed_through = through
        db.session.commit()


# --------------------------------------------------------------------------
# Nothing changes until somebody sets the date.
# --------------------------------------------------------------------------

def test_a_company_that_has_not_set_the_date_is_unaffected(app,
                                                           confirmed_payment):
    from app.models import Company
    from app.services.books import is_in_a_closed_period

    with app.app_context():
        company = Company.query.get(confirmed_payment['company_id'])
        assert company.books_closed_through is None
        assert is_in_a_closed_period(dt.date(2020, 1, 1), company) is False, (
            'a company that never asked for this had a document locked')


def test_the_date_is_inclusive(app, confirmed_payment):
    """"Khoá sổ đến ngày 31/03" includes the 31st — that day was declared."""
    from app.models import Company
    from app.services.books import is_in_a_closed_period

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        company = Company.query.get(confirmed_payment['company_id'])
        assert is_in_a_closed_period(dt.date(2026, 3, 31), company) is True
        assert is_in_a_closed_period(dt.date(2026, 4, 1), company) is False


def test_a_document_with_no_date_is_not_treated_as_ancient(app,
                                                           confirmed_payment):
    """None must not compare as "before everything" and lock silently."""
    from app.models import Company
    from app.services.books import is_in_a_closed_period

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        company = Company.query.get(confirmed_payment['company_id'])
        assert is_in_a_closed_period(None, company) is False


# --------------------------------------------------------------------------
# A draft is not in the books.
# --------------------------------------------------------------------------

def test_a_draft_in_a_closed_period_is_still_editable(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import PaymentReport
    from app.services.books import may_change

    _close_books(app, seed['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DRAFT',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        draft = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-DRAFT', report_date=dt.date(2026, 2, 10),
            payment_date=dt.date(2026, 2, 10), payment_type='advance',
            amount=1_000_000, is_confirmed=False)
        db.session.add(draft)
        db.session.commit()

        allowed, reason = may_change(draft)
        assert allowed is True, (
            f'a draft was locked by the closing date: {reason}')


# --------------------------------------------------------------------------
# A confirmed document in a closed period is refused, with a usable reason.
# --------------------------------------------------------------------------

def test_a_confirmed_document_in_a_closed_period_is_refused(
        app, confirmed_payment):
    from app.models.models import PaymentReport
    from app.services.books import may_change

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        payment = PaymentReport.query.get(confirmed_payment['payment_id'])
        allowed, reason = may_change(payment)
        assert allowed is False
        assert reason, 'refused without saying why'


def test_the_refusal_names_the_date_it_is_refusing_against(
        app, confirmed_payment):
    """A refusal a person cannot act on is how the database gets edited."""
    from app.models.models import PaymentReport
    from app.services.books import may_change

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        payment = PaymentReport.query.get(confirmed_payment['payment_id'])
        _allowed, reason = may_change(payment)
        assert '31/03/2026' in reason, (
            f'the message does not say which date locked it: {reason!r}')


def test_a_document_after_the_date_is_untouched(app, confirmed_payment):
    from app.config import db
    from app.models.models import PaymentReport

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 1, 31))
    from app.services.books import may_change
    with app.app_context():
        payment = PaymentReport.query.get(confirmed_payment['payment_id'])
        allowed, _reason = may_change(payment)
        assert allowed is True, (
            'a February document was locked by a January closing date')


# --------------------------------------------------------------------------
# The wire. The unit tests above prove the rule; these prove it is enforced
# where a person would meet it — and enforced in the service too, because a
# control only the screen applies is one the next entry point skips.
# --------------------------------------------------------------------------

def test_the_closing_date_is_set_from_the_settings_screen(client, login, app,
                                                          seed):
    login('admin')
    response = client.post('/settings/company', data={
        'name': 'Nội Thất An Phát', 'email': 'a@b.test',
        'books_closed_through': '2026-03-31',
    }, follow_redirects=True)
    assert response.status_code == 200

    from app.models import Company
    with app.app_context():
        company = Company.query.get(seed['company_id'])
        assert company.books_closed_through == dt.date(2026, 3, 31), (
            'the date typed on the settings screen never reached the company')


def test_clearing_the_field_reopens_the_period(client, login, app, seed):
    """Otherwise the screen that closes a period cannot reopen it."""
    _close_books(app, seed['company_id'], dt.date(2026, 3, 31))
    login('admin')
    client.post('/settings/company', data={
        'name': 'Nội Thất An Phát', 'email': 'a@b.test',
        'books_closed_through': '',
    }, follow_redirects=True)

    from app.models import Company
    with app.app_context():
        assert Company.query.get(seed['company_id']).books_closed_through \
            is None


def test_cancelling_a_supplier_invoice_in_a_closed_period_is_refused(
        app, seed):
    """The path where the closing date actually bites today.

    A CONFIRMED supplier invoice can still be cancelled — only an allocation
    stops it — so one dated inside a filed period is rewritable. That is the
    case the rule exists for.
    """
    from app.config import db
    from app.models.models import PurchaseOrder, SupplierInvoice, Supplier
    from app.services.payables_service import PayablesService

    _close_books(app, seed['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-CLOSE', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add(supplier)
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           supplier_id=supplier.id, po_number='PO-CLOSE',
                           order_date=dt.date(2026, 2, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        invoice = SupplierInvoice(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_id=po.id, invoice_number='0001111', invoice_date=dt.date(2026, 2, 20),
            subtotal=10_000_000, vat_rate=8, total_amount=10_800_000,
            status=SupplierInvoice.STATUS_CONFIRMED)
        db.session.add(invoice)
        db.session.commit()

        with pytest.raises(ValueError) as refused:
            PayablesService.cancel_invoice(invoice, reason='ghi nhầm')
        assert '31/03/2026' in str(refused.value)


def test_the_same_invoice_can_be_cancelled_once_the_period_reopens(app, seed):
    """The lock must be a lock, not a one-way door.

    A closing date that cannot be moved back would make a genuine mistake in a
    filed period unfixable by anyone — which is how people end up editing the
    database, the outcome this control exists to avoid.
    """
    from app.config import db
    from app.models.models import PurchaseOrder, SupplierInvoice, Supplier
    from app.services.payables_service import PayablesService

    _close_books(app, seed['company_id'], dt.date(2026, 1, 31))
    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-OPEN', name='Gỗ Hoà Bình',
                            is_active=True)
        db.session.add(supplier)
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           supplier_id=supplier.id, po_number='PO-OPEN',
                           order_date=dt.date(2026, 2, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        invoice = SupplierInvoice(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_id=po.id, invoice_number='0002222', invoice_date=dt.date(2026, 2, 20),
            subtotal=5_000_000, vat_rate=8, total_amount=5_400_000,
            status=SupplierInvoice.STATUS_CONFIRMED)
        db.session.add(invoice)
        db.session.commit()

        PayablesService.cancel_invoice(invoice, reason='ghi nhầm')
        assert invoice.status == SupplierInvoice.STATUS_CANCELED


def test_the_customer_payment_path_is_now_reachable_and_guarded(
        app, confirmed_payment):
    """This predicted its own obsolescence, and the prediction came true.

    It used to record that the closing-date check in
    `PaymentReportService.cancel_payment` never ran: `can_cancel()` refused
    every confirmed payment first (§3.2), so on that path the closed period
    added nothing. It was wired anyway, and the test said so out loud rather
    than passing for the wrong reason — with the note that when
    void-with-a-reason landed, the closed period would already be standing
    behind it.

    §3.2 landed. The guard is now what refuses, and the message names the date.
    """
    from app.services.services import PaymentReportService

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 3, 31))
    with app.app_context():
        with pytest.raises(ValueError) as refused:
            PaymentReportService().cancel_payment(
                confirmed_payment['payment_id'],
                confirmed_payment['order_id'], reason='nhầm đơn')
        assert '31/03/2026' in str(refused.value), (
            'the closing date is no longer what refuses this; check whether '
            f'something else now refuses first: {refused.value}')


def test_reopening_the_period_lets_the_void_through(app, confirmed_payment):
    """The lock must be a lock, not a one-way door — on this path too."""
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    _close_books(app, confirmed_payment['company_id'], dt.date(2026, 1, 31))
    with app.app_context():
        PaymentReportService().cancel_payment(
            confirmed_payment['payment_id'],
            confirmed_payment['order_id'], reason='nhầm đơn')
        assert PaymentReport.query.get(
            confirmed_payment['payment_id']).is_canceled is True
