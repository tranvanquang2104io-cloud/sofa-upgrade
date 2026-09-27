"""Store scoping has to reach the CHILDREN of an order, not just the order.

`tests/test_store_isolation_on_detail_screens.py` closed the order itself:
`OrderService.get_order` now refuses an order belonging to a branch the user is
not in. That fix was written at the getter deliberately, so that a detail route
added tomorrow would be covered.

It does not cover these routes, and the reason is worth writing down, because
it is the same shape as several other findings in this repo: **the child
documents are not reached through the order.** `/contracts/<id>/sign` takes a
CONTRACT id. It never loads the order, so it never passes through the check
that was put on the order. The guard is real, and these thirteen doors are
simply not behind it.

Five services fetch their own rows with a bare `self.repo.get_by_id(...)` --
fourteen call sites across quotations, contracts, handovers, payments and
documents. Twelve of them are inside mutating methods, so even fixing the five
`get_*` methods would leave the mutators open; `mark_signed` does not call
`get_contract`, it calls the repository directly.

What that costs: a user at branch A can sign branch B's contract, confirm
branch B's customer payment, void one that was confirmed, and delete branch B's
printed documents. The money ones are the serious ones -- `mark_confirmed`
writes the lifecycle flags that say the customer has paid.

These are tested as HTTP requests by a real store user, not as service calls,
because the claim being made is about what a logged-in person can reach.
"""
import datetime as dt

import pytest


@pytest.fixture()
def staff_can_work(app, seed):
    """The permissions the job needs, so a 403 means scope and not a missing
    feature grant. Without this the whole file passes for the wrong reason."""
    from app.config import db
    from app.models.models import User

    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        user.allowed_features = ['orders', 'contracts', 'payments',
                                 'quotations', 'handovers', 'documents',
                                 'customers']
        db.session.commit()
    return seed


@pytest.fixture()
def other_branch_paperwork(app, seed, staff_can_work):
    """A full set of child documents on an order in a branch the user is not in."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, Document, HandoverRecord, LifecycleStatus, PaymentReport,
        Quotation, Store,
    )

    with app.app_context():
        branch = Store(company_id=seed['company_id'], store_code='CH-C',
                       name='Chi nhanh Binh Thanh', is_active=True)
        db.session.add(branch)
        db.session.flush()

        order = Order(company_id=seed['company_id'], store_id=branch.id,
                      customer_id=seed['customer_id'], order_code='DH-CHILD',
                      title='Sofa goc L', total_amount=30_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True))

        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-CHILD', quotation_date=dt.date(2026, 9, 1),
            total_amount=30_000_000)
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-CHILD', contract_date=dt.date(2026, 9, 1),
            contract_value=30_000_000, advance_percentage=50, is_signed=False)
        handover = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-GN-CHILD', report_date=dt.date(2026, 9, 2),
            handover_date=dt.date(2026, 9, 2), is_confirmed=False)
        payment = PaymentReport(
            company_id=seed['company_id'], order_id=order.id,
            report_number='TT-CHILD', report_date=dt.date(2026, 9, 3),
            payment_date=dt.date(2026, 9, 3), payment_type='advance',
            amount=15_000_000, is_confirmed=False)
        document = Document(
            company_id=seed['company_id'], order_id=order.id,
            document_name='Hop dong HD-CHILD.docx', document_type='contract',
            document_format='docx', file_path='uploads/hd-child.docx')
        for row in (quotation, contract, handover, payment, document):
            db.session.add(row)
        db.session.commit()

        return {**seed, 'branch_id': str(branch.id), 'order_id': str(order.id),
                'quotation_id': str(quotation.id),
                'contract_id': str(contract.id),
                'handover_id': str(handover.id),
                'payment_id': str(payment.id),
                'document_id': str(document.id)}


def _fetch(app, model_name, row_id):
    from app.models import models

    with app.app_context():
        return getattr(models, model_name).query.get(row_id)


def test_a_store_user_cannot_sign_another_branchs_contract(
        app, client, login, other_branch_paperwork):
    login('staff')
    client.post(f"/contracts/{other_branch_paperwork['contract_id']}/sign",
                follow_redirects=True)
    assert _fetch(app, 'Contract',
                  other_branch_paperwork['contract_id']).is_signed is False, (
        'a user at another branch signed this branch contract')


def test_a_store_user_cannot_confirm_another_branchs_payment(
        app, client, login, other_branch_paperwork):
    """The money one: this writes the flags that say the customer has paid.

    The first version of this test checked only `is_confirmed`, and it PASSED
    against the unfixed code -- for the wrong reason. A staff user is not a
    deciding role, so `request_or_do` never performs the confirmation; it files
    an approval request. The flag stayed False because of the approval queue,
    not because of scope, and the test could not tell the difference.

    So it now also asserts that no REQUEST was filed. Filing one against
    another branch's payment is itself the leak: the row lands in a queue, and
    a manager who has no business seeing that payment is asked to approve it.
    """
    from app.models.models import ApprovalRequest, LifecycleStatus

    login('staff')
    client.post(f"/payment/{other_branch_paperwork['payment_id']}/confirm",
                follow_redirects=True)

    assert _fetch(app, 'PaymentReport',
                  other_branch_paperwork['payment_id']).is_confirmed is False, (
        'a user at another branch confirmed this branch customer payment')
    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=other_branch_paperwork['order_id']).first()
        assert lifecycle.advance_paid is not True

        assert ApprovalRequest.query.count() == 0, (
            'a user at another branch filed an approval request against this '
            'branch payment; the confirmation was only deferred, not refused')


def test_a_store_user_cannot_void_another_branchs_payment(
        app, client, login, other_branch_paperwork):
    """Same shape as the confirm: the queue is not a substitute for scope."""
    from app.models.models import ApprovalRequest

    login('staff')
    client.post(f"/payment/{other_branch_paperwork['payment_id']}/cancel",
                data={'reason': 'nham don'}, follow_redirects=True)
    assert _fetch(app, 'PaymentReport',
                  other_branch_paperwork['payment_id']).is_canceled is not True
    with app.app_context():
        assert ApprovalRequest.query.count() == 0


def test_a_store_user_cannot_confirm_another_branchs_handover(
        app, client, login, other_branch_paperwork):
    login('staff')
    client.post(f"/handover/{other_branch_paperwork['handover_id']}/confirm",
                follow_redirects=True)
    assert _fetch(app, 'HandoverRecord',
                  other_branch_paperwork['handover_id']).is_confirmed is False


def test_a_store_user_cannot_approve_another_branchs_quotation(
        app, client, login, other_branch_paperwork):
    login('staff')
    client.post(f"/quotations/{other_branch_paperwork['quotation_id']}/approve",
                follow_redirects=True)
    assert _fetch(app, 'Quotation',
                  other_branch_paperwork['quotation_id']).is_approved is not True


def test_a_store_user_cannot_delete_another_branchs_document(
        app, client, login, other_branch_paperwork):
    login('staff')
    client.post(f"/documents/delete/{other_branch_paperwork['document_id']}",
                follow_redirects=True)
    assert _fetch(app, 'Document',
                  other_branch_paperwork['document_id']) is not None, (
        'a user at another branch deleted this branch printed document')


def test_a_store_user_cannot_open_another_branchs_contract_edit_form(
        client, login, other_branch_paperwork):
    """A GET that shows the form is a leak too: it prints the contract value."""
    login('staff')
    response = client.get(
        f"/contracts/{other_branch_paperwork['contract_id']}/edit")
    assert response.status_code in (403, 302, 404), (
        f'HTTP {response.status_code} -- the form rendered')


# --- the other half of the claim: nothing legitimate was closed -------------

def test_a_company_admin_may_still_sign_any_branchs_contract(
        app, client, login, other_branch_paperwork):
    """Scoping must not lock an administrator out of their own company."""
    login('admin')
    client.post(f"/contracts/{other_branch_paperwork['contract_id']}/sign",
                follow_redirects=True)
    assert _fetch(app, 'Contract',
                  other_branch_paperwork['contract_id']).is_signed is True, (
        'the company admin was refused their own contract')


def test_a_store_user_may_still_sign_their_own_branchs_contract(
        app, client, login, seed, staff_can_work):
    """The ordinary case, which is most of the traffic."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-OWN',
                      title='Sofa bang', total_amount=10_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True))
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-OWN', contract_date=dt.date(2026, 9, 1),
            contract_value=10_000_000, advance_percentage=50, is_signed=False)
        db.session.add(contract)
        db.session.commit()
        contract_id = str(contract.id)

    login('staff')
    client.post(f'/contracts/{contract_id}/sign', follow_redirects=True)
    assert _fetch(app, 'Contract', contract_id).is_signed is True, (
        'a store user was refused a contract in their OWN branch')
