"""Every action that changes something must ask first.

The users of this product are not confident with computers. A button that
acts on a single click — especially one that commits money, sends something to
a supplier, or cannot be undone — is the main way they lose work or cause
damage they cannot repair.

This file has two halves:
  * a LINT test that scans every template, so a new destructive button cannot
    ship without a confirmation;
  * behaviour tests for the specific gaps found in the review.
"""
import datetime as dt
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

# Endpoints that change state. A form posting to one of these must be guarded
# either by a JS confirm() or by a Bootstrap modal.
DESTRUCTIVE = (
    'approve_quotation', 'cancel_quotation',
    'sign_contract', 'cancel_contract',
    'confirm_handover', 'cancel_handover',
    'confirm_payment', 'cancel_payment',
    'skip_advance_payment',
    'cancel_order',
    'issue_order_confirmation', 'cancel_order_confirmation',
    'issue_plan_materials', 'delete_plan_material',
    'receive_purchase_order',
    'confirm_supplier_invoice', 'pay_supplier_invoice',
    'deactivate_material', 'deactivate_user', 'deactivate_store',
    'deactivate_template', 'delete_document',
    'change_agreement_status',
)


def _guarded(text, endpoint):
    """Is every form posting to `endpoint` guarded by confirm() or a modal?

    A modal counts: the user still gets a deliberate second step.
    """
    for match in re.finditer(r'<form[^>]*>', text, re.S):
        tag = match.group(0)
        if endpoint not in tag:
            continue
        if 'confirm(' in tag:
            continue
        # look back for a modal wrapper containing this form
        head = text[max(0, match.start() - 1500):match.start()]
        if 'modal' in head:
            continue
        return False
    return True


def test_every_destructive_action_asks_before_acting():
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for endpoint in DESTRUCTIVE:
            if f'dashboard.{endpoint}' not in text:
                continue
            if not _guarded(text, endpoint):
                offenders.append(f'{path.relative_to(TEMPLATES)}:{endpoint}')

    assert offenders == [], (
        "these state-changing actions fire on a single click with no "
        f"confirmation, which non-technical users will trigger by accident: "
        f"{offenders}"
    )


# --- the specific gaps found in review -----------------------------------

def test_a_waived_advance_is_not_drawn_as_paid_on_the_timeline(app, client,
                                                               login, seed):
    """The order timeline showed the same green tick for waived and paid."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-WAIVE",
                  title="Waived advance")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=o.id, quotation_created=True, quotation_approved=True,
            contract_created=True, contract_signed=True,
            advance_paid=True, advance_skipped=True))
        db.session.commit()
        order_id = str(o.id)

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)

    assert 'advance_waived' not in body, "template variable leaked into output"
    assert ('Advance Skipped' in body or 'bỏ qua' in body.lower()), (
        "a waived advance must be labelled as waived, not shown as received"
    )


def test_a_genuinely_paid_advance_still_shows_as_paid(app, client, login, seed):
    """The fix must not hide a real payment."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-PAID",
                  title="Paid advance")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=o.id, quotation_created=True, quotation_approved=True,
            contract_created=True, contract_signed=True,
            advance_paid=True, advance_skipped=False))
        db.session.commit()
        order_id = str(o.id)

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert 'Advance Skipped' not in body


def test_zero_quantity_material_line_is_rejected(app, client, login, seed):
    """A zero line looks planned but issues nothing."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, Material, MaterialCategory, MaterialUnit,
        ProductionMaterialLine,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-ZERO",
                  title="Zero qty")
        db.session.add(o)
        db.session.flush()
        c = Contract(company_id=seed["company_id"], order_id=o.id,
                     contract_number="CT-ZERO", contract_date=dt.date(2026, 1, 1),
                     contract_value=0,
                     items=[{'name': 'Sofa', 'unit': 'bo', 'quantity': 1,
                             'unit_price': 1, 'total': 1}])
        db.session.add(c)
        unit = MaterialUnit(company_id=seed["company_id"], name="m")
        cat = MaterialCategory(company_id=seed["company_id"], name="v")
        db.session.add_all([unit, cat])
        db.session.flush()
        mat = Material(company_id=seed["company_id"], material_code="M-Z",
                       name="Vai", unit_id=unit.id, category_id=cat.id)
        db.session.add(mat)
        db.session.commit()

        plan = ProductionPlanService().create_from_contract(c)
        plan_id, mat_id = str(plan.id), str(mat.id)

    login("admin")
    client.post(f'/production-plan/{plan_id}/materials',
                data={'material_id': mat_id, 'quantity_required': '0'},
                follow_redirects=True)

    with app.app_context():
        assert ProductionMaterialLine.query.filter_by(
            plan_id=plan_id, material_id=mat_id).count() == 0, (
            "a zero-quantity material line must not be stored"
        )


# --- the order confirmation can now be undone ----------------------------

@pytest.fixture()
def issued_confirmation(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus, MasterAgreement, Quotation
    from app.services.agreement_service import AgreementService

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-CANCEL", signed_date=dt.date(2026, 1, 1),
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(ma)
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-CANCEL",
                  title="Cancellable")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id, quotation_created=True,
                                       quotation_approved=True))
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=o.id,
            quotation_number="QT-CANCEL", quotation_date=dt.date(2026, 1, 1),
            total_amount=0, is_approved=True,
            items=[{'name': 'Sofa', 'unit': 'bo', 'quantity': 1,
                    'unit_price': 1_000_000, 'total': 1_000_000}]))
        db.session.commit()

        conf = AgreementService.create_confirmation(
            order=o, agreement=ma,
            items=[{'name': 'Sofa', 'unit': 'bo', 'quantity': 1,
                    'unit_price': 1_000_000, 'total': 1_000_000}],
            confirmation_number="DDH-CANCEL",
            confirmation_date=dt.date(2026, 1, 2))
        AgreementService.confirm(conf)
        return {'order_id': str(o.id), 'confirmation_id': str(conf.id)}


def test_an_issued_order_confirmation_can_be_cancelled(app, client, login,
                                                       issued_confirmation):
    """It was previously permanent — the only document with no way back."""
    from app.models.models import OrderConfirmation

    login("admin")
    client.post(
        f"/order-confirmations/{issued_confirmation['confirmation_id']}/cancel",
        data={'reason': 'Khách đổi ý'}, follow_redirects=True)

    with app.app_context():
        conf = OrderConfirmation.query.get(issued_confirmation['confirmation_id'])
        assert conf.is_canceled is True
        assert 'Khách đổi ý' in (conf.canceled_reason or '')


def test_cancelling_requires_a_reason(app, client, login, issued_confirmation):
    from app.models.models import OrderConfirmation

    login("admin")
    client.post(
        f"/order-confirmations/{issued_confirmation['confirmation_id']}/cancel",
        data={'reason': '   '}, follow_redirects=True)

    with app.app_context():
        assert OrderConfirmation.query.get(
            issued_confirmation['confirmation_id']).is_canceled is False


def test_cancelling_rolls_the_order_back_to_the_agreement_step(
        app, client, login, issued_confirmation):
    from app.models import Order

    login("admin")
    client.post(
        f"/order-confirmations/{issued_confirmation['confirmation_id']}/cancel",
        data={'reason': 'Sai giá'}, follow_redirects=True)

    with app.app_context():
        lifecycle = Order.query.get(issued_confirmation['order_id']).lifecycle
        assert lifecycle.contract_signed is False, (
            "the order should be issuable again after the mistake is undone"
        )


def test_cancelling_does_not_rewrite_history_once_the_order_moved_on(
        app, client, login, issued_confirmation):
    """If money or goods already moved, un-signing would misstate the past."""
    from app.config import db
    from app.models import Order

    with app.app_context():
        lifecycle = Order.query.get(issued_confirmation['order_id']).lifecycle
        lifecycle.advance_paid = True
        db.session.commit()

    login("admin")
    client.post(
        f"/order-confirmations/{issued_confirmation['confirmation_id']}/cancel",
        data={'reason': 'Huỷ muộn'}, follow_redirects=True)

    with app.app_context():
        lifecycle = Order.query.get(issued_confirmation['order_id']).lifecycle
        assert lifecycle.contract_signed is True, (
            "lifecycle must be left alone once a later step has happened"
        )


def test_order_confirmation_is_tenant_scoped(app, client, login, seed,
                                             issued_confirmation):
    from app.config import db
    from app.models import Company, Customer, Order, Store
    from app.models.models import MasterAgreement, OrderConfirmation

    with app.app_context():
        c = Company(company_code="OCX", name="Rival", email="r@ocx.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="OCS", name="S")
        db.session.add(st)
        db.session.flush()
        cu = Customer(company_id=c.id, store_id=st.id, customer_code="OCC",
                      name="C")
        db.session.add(cu)
        db.session.flush()
        ma = MasterAgreement(company_id=c.id, customer_id=cu.id,
                             agreement_number="HDNT-X",
                             effective_from=dt.date(2026, 1, 1),
                             status=MasterAgreement.STATUS_ACTIVE)
        o = Order(company_id=c.id, store_id=st.id, customer_id=cu.id,
                  order_code="OCORD", title="T")
        db.session.add_all([ma, o])
        db.session.flush()
        conf = OrderConfirmation(
            company_id=c.id, order_id=o.id, master_agreement_id=ma.id,
            confirmation_number="DDH-X", confirmation_date=dt.date(2026, 1, 2),
            status='confirmed')
        db.session.add(conf)
        db.session.commit()
        theirs = str(conf.id)

    login("admin")
    client.post(f'/order-confirmations/{theirs}/cancel',
                data={'reason': 'x'}, follow_redirects=True)

    with app.app_context():
        assert OrderConfirmation.query.get(theirs).is_canceled is False


# --- "where is my order" at a glance -------------------------------------

def _order_with(app, seed, code, **flags):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code=code, title=code)
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id, **flags))
        db.session.commit()
        return str(o.id)


def test_order_page_shows_the_progress_stepper(app, client, login, seed):
    """The stepper was built and never used; it answers the first question a
    non-technical user asks — which step is my order on."""
    order_id = _order_with(app, seed, 'ORD-STEP',
                           quotation_created=True, quotation_approved=True,
                           contract_created=True, contract_signed=True)
    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)

    assert 'sf-stepper' in body, "the progress stepper should be on the page"
    assert 'sf-step--done' in body, "completed steps should be marked done"
    assert 'sf-step--current' in body, "the current step should be marked"


def test_stepper_marks_a_waived_advance_distinctly(app, client, login, seed):
    """Consistent with the timeline fix: waived is not done."""
    order_id = _order_with(app, seed, 'ORD-STEP-WAIVE',
                           quotation_created=True, quotation_approved=True,
                           contract_created=True, contract_signed=True,
                           advance_paid=True, advance_skipped=True)
    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert 'sf-step--skipped' in body


def test_stepper_on_a_brand_new_order_points_at_the_first_step(app, client,
                                                               login, seed):
    order_id = _order_with(app, seed, 'ORD-STEP-NEW')
    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert 'sf-stepper' in body
    assert 'sf-step--current' in body
