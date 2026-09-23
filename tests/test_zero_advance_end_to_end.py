"""The contract's advance percentage decides whether an advance is required.

The rule, as the owner stated it: if the contract records an advance other than
0%, an advance must be created; at 0% it is optional and the handover is not
held up waiting for one.

The service-level behaviour is covered in test_advance_follows_the_contract.py.
This walks the HTTP surface, because a rule that permits an action while the
screen that starts it refuses — or offers no button — is not permitted in any
sense the user can act on. The two halves have to agree.

Note what is deliberately NOT asserted: that a 0% contract makes the FINAL
payment available immediately. Final payment requires a confirmed handover, and
that has nothing to do with the advance — the work has to be delivered before
it is settled. Relaxing the advance must not quietly relax the rest of the
chain, so the chain is asserted too.
"""
import datetime as dt

import pytest


def _order_with_contract(app, seed, code, percentage, handover_confirmed=False):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code=code,
                      title='Sofa băng 3 chỗ', total_amount=40_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       quotation_approved=True,
                                       contract_created=True,
                                       contract_signed=True,
                                       handover_confirmed=handover_confirmed))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number=f'HD-{code}', contract_date=dt.date(2026, 9, 1),
            contract_value=40_000_000, advance_percentage=percentage,
            is_signed=True))
        db.session.commit()
        return str(order.id)


@pytest.fixture()
def zero_advance_order(app, seed):
    return {**seed, 'order_id': _order_with_contract(app, seed, 'ZERO', 0)}


@pytest.fixture()
def thirty_percent_order(app, seed):
    return {**seed, 'order_id': _order_with_contract(app, seed, 'THIRTY', 30)}


def test_a_zero_percent_contract_does_not_hold_up_the_handover(
        app, zero_advance_order):
    from app.models import Order
    from app.services.workflow_service import (
        ACTION_HANDOVER_CREATE, ACTION_PAYMENT_ADVANCE, WorkflowService,
    )

    with app.app_context():
        order = Order.query.get(zero_advance_order['order_id'])
        assert WorkflowService.can(order, ACTION_HANDOVER_CREATE), (
            'a contract that never asked for an advance is blocking on one')
        assert WorkflowService.can(order, ACTION_PAYMENT_ADVANCE), (
            'an advance must stay possible — optional, not forbidden')


def test_a_contract_that_names_a_percentage_does_hold_it_up(
        app, thirty_percent_order):
    """The other half of the rule, or the first half means nothing."""
    from app.models import Order
    from app.services.workflow_service import (
        ACTION_HANDOVER_CREATE, WorkflowService,
    )

    with app.app_context():
        order = Order.query.get(thirty_percent_order['order_id'])
        assert not WorkflowService.can(order, ACTION_HANDOVER_CREATE)


def test_the_delivery_chain_is_not_relaxed_along_with_the_advance(
        app, zero_advance_order):
    """Final payment still waits for the handover: the work must be delivered."""
    from app.models import Order
    from app.services.workflow_service import (
        ACTION_PAYMENT_FINAL, WorkflowService,
    )

    with app.app_context():
        order = Order.query.get(zero_advance_order['order_id'])
        assert not WorkflowService.can(order, ACTION_PAYMENT_FINAL)


def test_all_three_become_available_once_the_handover_is_confirmed(app, seed):
    from app.models import Order
    from app.services.workflow_service import (
        ACTION_HANDOVER_CREATE, ACTION_PAYMENT_ADVANCE, ACTION_PAYMENT_FINAL,
        WorkflowService,
    )

    order_id = _order_with_contract(app, seed, 'DONE', 0,
                                    handover_confirmed=True)
    with app.app_context():
        order = Order.query.get(order_id)
        for action in (ACTION_HANDOVER_CREATE, ACTION_PAYMENT_ADVANCE,
                       ACTION_PAYMENT_FINAL):
            assert WorkflowService.can(order, action), f'{action} is blocked'


@pytest.mark.parametrize('path', [
    '/handover/{order_id}/create',
    '/payment/{order_id}/create?type=advance',
])
def test_each_permitted_create_screen_opens(client, login, zero_advance_order,
                                            path):
    """A permitted action whose screen refuses is not permitted."""
    login('admin')
    response = client.get(path.format(**zero_advance_order))
    assert response.status_code == 200, (
        f'{path} did not open on a 0% contract (HTTP {response.status_code})')


def test_the_order_page_offers_the_handover_without_an_advance(
        client, login, zero_advance_order):
    """The button is how a non-technical user learns the action is available."""
    login('admin')
    body = client.get(
        f"/orders/{zero_advance_order['order_id']}").get_data(as_text=True)
    assert f"/handover/{zero_advance_order['order_id']}/create" in body, (
        'the order screen offers no way to start the handover')
