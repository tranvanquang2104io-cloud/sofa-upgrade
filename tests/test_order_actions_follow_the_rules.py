"""The buttons on the order page must obey the workflow rules.

The order screen decided what a user may do next by reading
`lifecycle.advance_paid` directly. Two consequences:

* A contract agreed at 0% advance never gets an advance, so "Create Handover
  Record" and "Record Final Payment" never appeared at all — the order could
  not be finished from its own screen.
* The workflow settings screen could relax or switch off a rule and the buttons
  stayed hidden regardless, because nothing on the page ever asked the engine.
  Configuration that the interface ignores is configuration that does nothing.

The page now asks `WorkflowService.can()`, which is the same question the
service layer answers when the form is submitted — so what the screen offers
and what the system accepts cannot drift apart.
"""
import datetime as dt

import pytest

HANDOVER_BUTTON = '/handover/'
FINAL_PAYMENT_BUTTON = 'type=final'


def _order_with_contract(app, seed, advance_percentage, code,
                         contract_signed=True):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code=code,
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, quotation_created=True, quotation_approved=True,
            contract_created=True, contract_signed=contract_signed))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number=f'HD-{code}', contract_date=dt.date(2026, 1, 1),
            contract_value=10_000_000, advance_percentage=advance_percentage,
            advance_amount=10_000_000 * advance_percentage / 100,
            is_signed=contract_signed))
        db.session.commit()
        return str(order.id)


def test_a_zero_percent_contract_can_go_straight_to_handover(app, client,
                                                             login, seed):
    """The owner's rule: no advance asked for, so nothing to wait on."""
    order_id = _order_with_contract(app, seed, 0, 'DH-UI-0')

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert HANDOVER_BUTTON in body


def test_a_zero_percent_contract_reaches_the_final_payment(app, client, login,
                                                           seed):
    """The advance must stop blocking it; the handover still gates it.

    Those are two different rules and only the first one changed. You invoice
    the balance after delivering, which is why `payment.final` asks for the
    handover — so this asserts the order can get there, not that the button
    appears before the goods do.
    """
    from app.config import db
    from app.models.models import LifecycleStatus

    order_id = _order_with_contract(app, seed, 0, 'DH-UI-0P')

    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(order_id=order_id).first()
        lifecycle.handover_confirmed = True
        db.session.commit()

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert FINAL_PAYMENT_BUTTON in body, (
        "with nothing owed up front and the goods delivered, the balance must "
        "be recordable"
    )


def test_a_contract_with_an_advance_still_waits_for_it(app, client, login,
                                                        seed):
    order_id = _order_with_contract(app, seed, 30, 'DH-UI-30')

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert HANDOVER_BUTTON not in body, (
        "the contract asked for 30% up front; the handover must wait"
    )


def test_the_advance_can_always_be_recorded_when_it_is_optional(app, client,
                                                                 login, seed):
    """0% means optional, not forbidden — a customer may still pay early.

    Checks the labelled button, not just the word `/payment/`: that substring
    appears in other links on the page and would have proved nothing.

    The label used to be matched in ENGLISH, and that passed for a reason
    worth keeping: the timeline carried a hardcoded `Record Advance Payment`
    with no `t()` around it, so a Vietnamese user saw English there. When the
    duplicate button was removed the only remaining one goes through `t()` and
    renders as `Tạo Biên Bản Tạm Ứng` — so the English match broke while the
    capability was untouched. The button is asserted by its real label now.
    """
    order_id = _order_with_contract(app, seed, 0, 'DH-UI-0A')

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert 'Tạo Biên Bản Tạm Ứng' in body, (
        "a customer may still choose to pay something up front"
    )


def test_relaxing_the_rule_makes_the_button_appear(app, client, login, seed):
    """An admin who relaxes a step must see the screen follow."""
    from app.config import db
    from app.models.models import WorkflowRule
    from app.services.workflow_service import ACTION_HANDOVER_CREATE

    order_id = _order_with_contract(app, seed, 30, 'DH-UI-RELAX')

    with app.app_context():
        db.session.add(WorkflowRule(
            company_id=seed['company_id'], action=ACTION_HANDOVER_CREATE,
            prerequisite='advance_paid', mode=WorkflowRule.MODE_OPTIONAL))
        db.session.commit()

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert HANDOVER_BUTTON in body, (
        "the settings screen offered this and the order page ignored it"
    )


def test_an_unsigned_contract_offers_no_advance_yet(app, client, login, seed):
    """payment.advance requires the signature; that rule is unchanged."""
    order_id = _order_with_contract(app, seed, 30, 'DH-UI-UNSIGNED',
                                    contract_signed=False)

    login("admin")
    body = client.get(f'/orders/{order_id}').get_data(as_text=True)
    assert 'Record Advance Payment' not in body
    assert 'Ghi Nhận Tạm Ứng' not in body
