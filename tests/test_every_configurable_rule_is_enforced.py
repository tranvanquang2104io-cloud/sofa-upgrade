"""A rule the admin can configure but nothing checks is worse than no rule.

The workflow settings screen lists seven actions and lets a company admin set
prerequisites on each. Five of them are checked: `WorkflowService.require` is
called before signing a contract, creating a handover, and taking each kind of
payment.

Two are not. `quotation.approve` and `handover.confirm` appear on the grid,
accept rules, save them, and show them back — and no code path ever asks.

This is the hidden-button problem with the sign reversed, and it is worse.
A hidden button misleads whoever is looking at the screen. Here the person
misled is the OWNER of the company, who has deliberately set a control, been
shown that it is set, and believes their staff cannot approve a quotation
before whatever they required. Nobody will discover it, because the absence of
a refusal looks exactly like a rule that was satisfied.

The fix is one line per action in the service, but the test is the point: it
asserts that EVERY action offered on that grid is enforced somewhere, so the
eighth action added next year cannot repeat this quietly.
"""
import datetime as dt

import pytest


def test_every_configurable_action_is_enforced_somewhere():
    """The grid and the enforcement must not be allowed to drift apart.

    Checked by reading the source rather than by exercising each action,
    deliberately: the failure being guarded against is an action that exists
    in `ALL_ACTIONS` and is never passed to `require`, and no behavioural test
    can see an action nobody wrote a path for.
    """
    import pathlib

    from app.services.workflow_service import ALL_ACTIONS

    root = pathlib.Path(__file__).resolve().parent.parent / 'app'
    sources = '\n'.join(
        path.read_text(encoding='utf-8')
        for path in root.rglob('*.py')
        if 'workflow_service.py' not in str(path))

    unenforced = [action for action in ALL_ACTIONS
                  if f"'{action}'" not in sources
                  and _constant_name(action) not in sources]

    assert not unenforced, (
        f'these actions can be configured by an admin but nothing enforces '
        f'them: {unenforced}. A rule that is set, shown as set, and never '
        f'checked tells the owner they have a control they do not have.')


def _constant_name(action):
    return 'ACTION_' + action.replace('.', '_').upper()


@pytest.fixture()
def order_needing_approval(app, seed):
    """An order with a quotation, and a rule requiring a contract first.

    The rule is deliberately one the order does NOT satisfy, so that an
    enforced rule refuses and an unenforced one lets the action through.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus, Quotation, WorkflowRule

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-WF',
                      title='Sofa goc L', total_amount=10_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=False))
        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-WF', quotation_date=dt.date(2026, 9, 1),
            total_amount=10_000_000)
        db.session.add(quotation)
        db.session.add(WorkflowRule(
            company_id=seed['company_id'], action='quotation.approve',
            prerequisite='contract_created', is_active=True,
            mode=WorkflowRule.MODE_REQUIRED,
            message='Phải có hợp đồng trước khi duyệt báo giá'))
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'quotation_id': str(quotation.id)}


def test_a_rule_on_approving_a_quotation_actually_refuses(
        app, order_needing_approval):
    """Set the rule, break it, and the approval must not go through."""
    from app.models.models import Quotation
    from app.services.services import QuotationService

    with app.app_context():
        with pytest.raises(Exception) as refused:
            QuotationService().approve_quotation(
                order_needing_approval['quotation_id'],
                order_needing_approval['order_id'])
        assert 'hợp đồng' in str(refused.value).lower(), (
            f'refused for some other reason: {refused.value}')

        assert Quotation.query.get(
            order_needing_approval['quotation_id']).is_approved is not True
