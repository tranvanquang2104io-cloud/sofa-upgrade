"""One working day, as a member of staff rather than an administrator.

Measured: the suite logs in as `admin` 319 times and as `staff` 25. Almost
everything this product does has only ever been proved for someone who can do
everything. The maker-checker work added this session is precisely the part
that BEHAVES DIFFERENTLY for the two, so the tests were blindest exactly where
the new behaviour lives.

This is one journey, not a set of endpoint checks, because the bugs being
looked for live between the steps: a clerk who can create but not edit, an
approval that leaves the document readable but frozen, a screen that offers a
button the service will refuse. Testing each POST alone cannot see any of it.

The story:

  1. a clerk writes a quotation for a customer
  2. the customer haggles, so the clerk edits it
  3. the customer agrees, so a contract is drawn up and signed
  4. the clerk records the advance the customer paid
  5. confirming money is not the clerk's to do — it goes to the manager
  6. the manager approves, and THAT is when the money counts
  7. the clerk tries to change the confirmed payment and is refused

Step 3 was missing from the first version, and the product was right to refuse
what followed: `payment.advance` requires `contract_signed`. A journey that
skips the contract is not a shorter journey, it is one that does not happen in
this business.

Steps 2 and 6 cover routes that, per the audit, had never received a POST in
any test.

(First run: I guessed `/orders/<id>/quotations/create`, a RESTful nesting this
app does not use — the real routes are `/quotations/<order_id>/create` and
`/payment/<order_id>/create`. Guessing a URL tests my expectation of the app
rather than the app, and it is the same mistake as guessing a field name.)

PROVEN TO CATCH SOMETHING. Adding the clerk's role to `DECIDING_ROLES` — the
exact careless change that would turn maker-checker into decoration — makes
this file fail at "a clerk confirmed money on their own".

Worth recording how that check nearly fooled me: my first attempt added
`'staff'` to that tuple and the tests stayed green, which looked like the
journey being blind. The seeded user called `staff` has role **`user`**. The
sabotage had done nothing. A test that does not fail when you break the code
is either a bad test or a bad break, and assuming the first without checking
the second would have had me rewriting a test that was already right.
"""
import datetime as dt

import pytest


@pytest.fixture()
def clerk_can_work(app, seed):
    """The permissions the job needs.

    Without this every request is 403 for a missing feature grant, and the
    whole journey passes for the wrong reason — which is what happened the
    first time this file was run.
    """
    from app.config import db
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['orders', 'quotations', 'payments',
                                 'contracts', 'customers']
        db.session.commit()
    return seed


@pytest.fixture()
def an_order(app, seed, clerk_can_work):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-DAY',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_a_clerk_writes_edits_and_banks_a_quotation_then_hands_the_money_up(
        app, client, login, an_order):
    """The whole day, in order, with the state checked after every step."""
    from app.config import db
    from app.models.models import (
        ApprovalRequest, Contract, LifecycleStatus, PaymentReport, Quotation,
    )

    order_id = an_order['order_id']

    # --- 1. the clerk writes a quotation ---------------------------------
    login('staff')
    client.post(f'/quotations/{order_id}/create', data={
        'quotation_number': 'BG-DAY', 'quotation_date': '2026-09-01',
        'item_name[]': ['Sofa goc L'], 'item_unit[]': ['Bo'],
        'item_quantity[]': ['1'], 'item_price[]': ['20000000'],
        'vat_rate': '8',
    }, follow_redirects=True)

    with app.app_context():
        quotation = Quotation.query.filter_by(order_id=order_id).first()
        assert quotation is not None, 'a clerk could not write a quotation'
        quotation_id = str(quotation.id)
        assert float(quotation.total_amount) > 0, (
            'the quotation saved with no money on it')

    # --- 2. the customer haggles, so the clerk edits it -------------------
    # Per the audit this route had never received a POST in any test.
    client.post(f'/quotations/{quotation_id}/edit', data={
        'quotation_number': 'BG-DAY', 'quotation_date': '2026-09-01',
        'item_name[]': ['Sofa goc L'], 'item_unit[]': ['Bo'],
        'item_quantity[]': ['1'], 'item_price[]': ['18000000'],
        'vat_rate': '8',
    }, follow_redirects=True)

    with app.app_context():
        after = Quotation.query.get(quotation_id)
        assert float(after.subtotal) == 18_000_000, (
            f'the edit did not take: subtotal is {after.subtotal}')

    # --- 3. the customer agrees, so a contract is drawn up and signed -----
    # This step was missing from my first version of this story, and the
    # product was right to refuse: `payment.advance` requires
    # `contract_signed`. A journey that skips the contract is not a shorter
    # journey, it is a different one that does not happen in this business.
    client.post(f'/contracts/{order_id}/create', data={
        'contract_number': 'HD-DAY', 'contract_date': '2026-09-01',
        'advance_percentage': '50',
    }, follow_redirects=True)

    with app.app_context():
        contract = Contract.query.filter_by(order_id=order_id).first()
        assert contract is not None, 'a clerk could not draw up a contract'
        contract_id = str(contract.id)

    client.post(f'/contracts/{contract_id}/sign', follow_redirects=True)

    with app.app_context():
        assert Contract.query.get(contract_id).is_signed is True, (
            'the contract was not signed, so the advance cannot be taken')

    # --- 4. the clerk records the advance the customer paid ---------------
    client.post(f'/payment/{order_id}/create', data={
        'report_number': 'TT-DAY', 'report_date': '2026-09-02',
        'payment_date': '2026-09-02', 'payment_type': 'advance',
        'amount': '9000000', 'payment_method': 'bank_transfer',
    }, follow_redirects=True)

    with app.app_context():
        payment = PaymentReport.query.filter_by(order_id=order_id).first()
        assert payment is not None, 'a clerk could not record a payment'
        payment_id = str(payment.id)
        assert payment.is_confirmed is False

    # --- 5. confirming money is not the clerk's to do ---------------------
    client.post(f'/payment/{payment_id}/confirm', follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(payment_id).is_confirmed is False, (
            'a clerk confirmed money on their own')
        request_row = ApprovalRequest.query.filter_by(
            target_id=payment_id).first()
        assert request_row is not None, (
            'the clerk was refused instead of being able to ASK — that is the '
            'design the owner rejected, because it is what makes people '
            'borrow the manager password')
        assert request_row.status == ApprovalRequest.STATUS_PENDING
        assert str(request_row.store_id) == str(an_order['store_id']), (
            'the request does not carry the branch it came from')
        request_id = str(request_row.id)

        lifecycle = LifecycleStatus.query.filter_by(order_id=order_id).first()
        assert lifecycle.advance_paid is not True, (
            'the order says the advance is paid while it is still pending')

    # --- 6. the manager approves, and THAT is when the money counts -------
    login('admin')
    client.post(f'/approvals/{request_id}/approve', follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(payment_id).is_confirmed is True, (
            'approving did not perform the action, so approval is a ceremony')
        assert ApprovalRequest.query.get(request_id).status == \
            ApprovalRequest.STATUS_APPROVED
        assert ApprovalRequest.query.get(request_id).decided_by_id is not None, (
            'nobody is recorded as having approved it')

    # --- 7. the clerk tries to change the confirmed payment --------------
    login('staff')
    client.post(f'/payment/{payment_id}/edit', data={
        'amount': '1', 'report_date': '2026-09-02',
        'payment_date': '2026-09-02', 'payment_type': 'advance',
    }, follow_redirects=True)

    with app.app_context():
        assert float(PaymentReport.query.get(payment_id).amount) == 9_000_000, (
            'a confirmed payment was edited after approval — the amount can '
            'change after the decision that approved it')


@pytest.fixture()
def order_ready_for_payment(app, an_order):
    """An order with a signed contract, built directly.

    Built in the database rather than through the screens, because this test
    is about who may APPROVE — the journey to get here is the other test's
    subject, and repeating it would mean two tests failing whenever one
    earlier step changes.
    """
    from app.config import db
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        db.session.add(Contract(
            company_id=an_order['company_id'], order_id=an_order['order_id'],
            contract_number='HD-SELF', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=50,
            is_signed=True, is_active=True))
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=an_order['order_id']).first()
        lifecycle.contract_created = True
        lifecycle.contract_signed = True
        db.session.commit()
    return an_order


def test_the_clerk_cannot_approve_their_own_request(app, client, login,
                                                    order_ready_for_payment):
    """The other half of step 6: asking and deciding are different people."""
    from app.models.models import ApprovalRequest, PaymentReport

    an_order = order_ready_for_payment
    order_id = an_order['order_id']
    login('staff')
    client.post(f'/payment/{order_id}/create', data={
        'report_number': 'TT-SELF', 'report_date': '2026-09-02',
        'payment_date': '2026-09-02', 'payment_type': 'advance',
        'amount': '5000000', 'payment_method': 'cash',
    }, follow_redirects=True)

    with app.app_context():
        payment_id = str(PaymentReport.query.filter_by(
            order_id=order_id).first().id)

    client.post(f'/payment/{payment_id}/confirm', follow_redirects=True)

    with app.app_context():
        request_id = str(ApprovalRequest.query.filter_by(
            target_id=payment_id).first().id)

    # Still the clerk. The queue screen is store_admin-only, so this is the
    # URL being posted directly — which is the only way this is reachable and
    # therefore the only way worth testing.
    client.post(f'/approvals/{request_id}/approve', follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.get(payment_id).is_confirmed is False, (
            'the person who asked also approved it, so the second pair of '
            'eyes was their own')
