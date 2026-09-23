"""The two halves of the workflow screen must not undo each other.

The owner asked what the two sections are for and whether they overlap. They
do, and they fight:

* The **grid** sets how strict each (step, prerequisite) pairing is. Setting a
  cell creates the rule; blanking it deletes the rule.
* The **list** below does two things the grid cannot: switch a rule off without
  losing it, and word the message a user sees when they are blocked.

The grid's save wrote `is_active = True` on every cell it touched. So an
administrator who switched a rule off in the list, then went back and saved the
grid for an unrelated step, silently turned it back on — and nothing on screen
said so. The next person to hit that step is blocked by a rule its owner
believes is off.

Deleting is still deleting: blanking a cell removes the rule and its message
with it, which is what "no rule here" means. What the grid may not do is change
a decision the other section owns.
"""
import pytest

from app.models.models import WorkflowRule
from app.services.workflow_service import (
    ACTION_HANDOVER_CREATE, ACTION_PAYMENT_ADVANCE, WorkflowService,
)


@pytest.fixture()
def rules(app, seed):
    with app.app_context():
        WorkflowService.seed_defaults(seed['company_id'])
    return seed


def _rule(app, company_id, action):
    with app.app_context():
        return WorkflowRule.query.filter_by(
            company_id=company_id, action=action).first()


def _post_grid(client, company_id, app):
    """Save the grid exactly as the screen does, from its current state."""
    with app.app_context():
        current = WorkflowRule.query.filter_by(company_id=company_id).all()
        data = {'action': 'save_matrix'}
        for rule in current:
            data[f'cell_{rule.action}_{rule.prerequisite}'] = rule.mode
    return client.post('/settings/workflow', data=data, follow_redirects=True)


def test_saving_the_grid_does_not_switch_a_disabled_rule_back_on(
        app, client, login, rules):
    company_id = rules['company_id']

    # Switch one rule off, the way the list below the grid does.
    from app.config import db
    with app.app_context():
        rule = WorkflowRule.query.filter_by(
            company_id=company_id, action=ACTION_PAYMENT_ADVANCE).first()
        rule.is_active = False
        db.session.commit()

    login('admin')
    _post_grid(client, company_id, app)

    assert _rule(app, company_id, ACTION_PAYMENT_ADVANCE).is_active is False, (
        'saving the grid re-enabled a rule the administrator had switched off'
    )


def test_saving_the_grid_keeps_a_custom_message(app, client, login, rules):
    """The wording is the list's to own, not the grid's to lose."""
    from app.config import db

    company_id = rules['company_id']
    with app.app_context():
        rule = WorkflowRule.query.filter_by(
            company_id=company_id, action=ACTION_HANDOVER_CREATE).first()
        rule.message = 'Chưa nhận tạm ứng thì chưa giao hàng được.'
        db.session.commit()

    login('admin')
    _post_grid(client, company_id, app)

    assert _rule(app, company_id, ACTION_HANDOVER_CREATE).message == (
        'Chưa nhận tạm ứng thì chưa giao hàng được.')


def test_the_grid_still_sets_the_mode(app, client, login, rules):
    """What the grid IS for must keep working."""
    company_id = rules['company_id']

    login('admin')
    with app.app_context():
        current = WorkflowRule.query.filter_by(company_id=company_id).all()
        data = {'action': 'save_matrix'}
        for rule in current:
            data[f'cell_{rule.action}_{rule.prerequisite}'] = (
                WorkflowRule.MODE_OPTIONAL
                if rule.action == ACTION_HANDOVER_CREATE else rule.mode)
    client.post('/settings/workflow', data=data, follow_redirects=True)

    assert _rule(app, company_id, ACTION_HANDOVER_CREATE).mode == (
        WorkflowRule.MODE_OPTIONAL)


def test_blanking_a_cell_still_removes_the_rule(app, client, login, rules):
    """"No rule here" has to stay expressible."""
    company_id = rules['company_id']

    login('admin')
    with app.app_context():
        current = WorkflowRule.query.filter_by(company_id=company_id).all()
        data = {'action': 'save_matrix'}
        for rule in current:
            if rule.action != ACTION_HANDOVER_CREATE:
                data[f'cell_{rule.action}_{rule.prerequisite}'] = rule.mode
    client.post('/settings/workflow', data=data, follow_redirects=True)

    assert _rule(app, company_id, ACTION_HANDOVER_CREATE) is None
