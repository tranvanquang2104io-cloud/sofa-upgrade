"""The advance is required only when the contract asks for one.

The business rule, in the owner's words: if the contract carries an advance
percentage other than zero, the advance payment must be made; if the contract
says 0%, the advance is optional and the handover and the payment can both be
created without one.

Before this, `handover.create` was gated on `advance_paid` regardless of what
the contract said. A contract agreed at 0% — which happens on small repeat
orders and for long-standing customers — still had to have its advance step
waived with a recorded reason, as if skipping something the contract never
asked for.

Implemented as a fourth rule MODE, not as a hardcoded branch, because the
request was for the logic to be able to follow several rules. An administrator
picks, per step, between:

    required   always blocks until the prerequisite is met
    waivable   blocks, but can be skipped with a recorded reason
    optional   advice only
    contract   applies only when the contract calls for it (this one)

`contract` mode still honours a recorded waiver, so the existing escape hatch
for an order that genuinely needs one is untouched.
"""
import datetime as dt

import pytest

from app.models.models import WorkflowRule
from app.services.workflow_service import ACTION_HANDOVER_CREATE, WorkflowService


def _order_with_contract(app, seed, advance_percentage, code):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code=code,
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number=f'HD-{code}', contract_date=dt.date(2026, 1, 1),
            contract_value=10_000_000,
            advance_percentage=advance_percentage,
            advance_amount=10_000_000 * advance_percentage / 100,
            is_signed=True))
        db.session.commit()
        return str(order.id)


def _set_contract_mode(app, company_id):
    """Put handover.create on the new mode, as the shipped default now does."""
    from app.config import db

    with app.app_context():
        rule = WorkflowRule.query.filter_by(
            company_id=company_id, action=ACTION_HANDOVER_CREATE).first()
        if rule is None:
            rule = WorkflowRule(company_id=company_id,
                                action=ACTION_HANDOVER_CREATE,
                                prerequisite='advance_paid')
            db.session.add(rule)
        rule.mode = WorkflowRule.MODE_CONTRACT
        db.session.commit()


def _order(order_id):
    from app.models import Order
    return Order.query.get(order_id)


# --- the rule itself ------------------------------------------------------

def test_a_contract_with_an_advance_still_requires_it(app, seed):
    order_id = _order_with_contract(app, seed, 30, 'DH-ADV-30')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is False


def test_a_zero_percent_contract_does_not_require_an_advance(app, seed):
    """The whole point: nothing to skip, so nothing to block."""
    order_id = _order_with_contract(app, seed, 0, 'DH-ADV-0')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is True


def test_a_zero_percent_contract_produces_no_warning_either(app, seed):
    """Not applicable is not the same as unmet: it must be silent."""
    order_id = _order_with_contract(app, seed, 0, 'DH-ADV-0W')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        blocked, warnings = WorkflowService.check(_order(order_id),
                                                  ACTION_HANDOVER_CREATE)
        assert blocked == []
        assert warnings == []


def test_an_advance_that_has_been_paid_unblocks_it(app, seed):
    from app.config import db
    from app.models.models import LifecycleStatus

    order_id = _order_with_contract(app, seed, 30, 'DH-ADV-PAID')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(order_id=order_id).first()
        lifecycle.advance_paid = True
        db.session.commit()

        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is True


def test_contract_mode_still_honours_a_recorded_waiver(app, seed):
    """The escape hatch for an order that genuinely needs one stays."""
    order_id = _order_with_contract(app, seed, 30, 'DH-ADV-WAIVE')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        WorkflowService.waive(_order(order_id), ACTION_HANDOVER_CREATE,
                              'advance_paid', reason='Khách quen, giao trước')

        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is True


def test_an_order_with_no_contract_is_not_blocked_by_this_mode(app, seed):
    """An order agreed through a framework agreement has no Contract row."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-NO-CT',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()
        order_id = str(order.id)

    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is True


def test_a_cancelled_contract_is_not_consulted(app, seed):
    from app.config import db
    from app.models.models import Contract

    order_id = _order_with_contract(app, seed, 30, 'DH-ADV-CANCEL')
    _set_contract_mode(app, seed['company_id'])

    with app.app_context():
        contract = Contract.query.filter_by(order_id=order_id).first()
        contract.is_canceled = True
        db.session.commit()

        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is True


# --- the other modes are untouched ---------------------------------------

def test_required_mode_ignores_the_contract_percentage(app, seed):
    """Picking `required` must keep meaning always."""
    order_id = _order_with_contract(app, seed, 0, 'DH-REQ-0')

    from app.config import db
    with app.app_context():
        rule = WorkflowRule.query.filter_by(
            company_id=seed['company_id'],
            action=ACTION_HANDOVER_CREATE).first()
        if rule is None:
            rule = WorkflowRule(company_id=seed['company_id'],
                                action=ACTION_HANDOVER_CREATE,
                                prerequisite='advance_paid')
            db.session.add(rule)
        rule.mode = WorkflowRule.MODE_REQUIRED
        db.session.commit()

        assert WorkflowService.can(_order(order_id),
                                   ACTION_HANDOVER_CREATE) is False


def test_the_new_mode_is_offered_on_the_settings_screen(client, login):
    """As a selectable option, not merely as a word on the page.

    Asserting `'contract' in body` would have passed on the action name
    `contract.sign` alone and proved nothing.
    """
    login("admin")
    body = client.get('/settings/workflow').get_data(as_text=True)

    assert 'value="contract"' in body
    for mode in ('required', 'waivable', 'optional'):
        assert f'value="{mode}"' in body, (
            f'the existing {mode} option must survive'
        )


def test_the_mode_names_are_shown_in_vietnamese(client, login):
    """`contract` on its own tells a shop owner nothing."""
    login("admin")
    body = client.get('/settings/workflow').get_data(as_text=True)
    assert 'Theo hợp đồng' in body
