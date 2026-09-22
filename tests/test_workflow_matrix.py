"""Workflow rules as a grid: every step against every prerequisite.

Same gap as the standardization screen, in a different place. The workflow
settings page rendered only the rules already seeded, so `quotation.approve`
and `handover.confirm` - both declared in ALL_ACTIONS - could never be given a
rule at all. ALL_ACTIONS was even passed to the template and never used by it,
which is how a list of seven actions became a screen showing five.

The grid answers it the way the standardization matrix does: every action is a
ROW, every lifecycle prerequisite is a COLUMN, and the cell holds how strictly
that pairing applies:

    (blank)    no rule - this step does not care about that prerequisite
    required   always blocks until met
    waivable   blocks, but can be skipped with a recorded reason
    optional   advice only
    contract   applies only when the contract calls for it

Setting a cell creates the rule; blanking it deletes the rule. There is no
create form and no delete button, because a cell already exists for every
pairing the engine can express.
"""
import pytest

from app.models.models import WorkflowRule
from app.services.workflow_service import ALL_ACTIONS, PREREQUISITE_LABELS


def _rules(company_id, action=None):
    query = WorkflowRule.query.filter_by(company_id=company_id)
    if action:
        query = query.filter_by(action=action)
    return query.all()


# --- what the screen can express -----------------------------------------

def test_every_declared_action_is_a_row(client, login):
    """Five of seven were unreachable before."""
    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)

    for action in ALL_ACTIONS:
        assert action in body, f'{action} has no row'


def test_every_prerequisite_is_a_column(client, login):
    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)

    for prerequisite in PREREQUISITE_LABELS:
        assert prerequisite in body, f'{prerequisite} has no column'


def test_a_cell_exists_for_a_pairing_with_no_rule(client, login):
    """quotation.approve had no seeded rule, so it needs an empty cell."""
    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)
    assert 'cell_quotation.approve_contract_signed' in body


# --- setting a cell creates the rule -------------------------------------

def test_setting_a_cell_creates_a_rule(app, client, login, seed):
    login('admin')
    client.post('/settings/workflow', data={
        'action': 'save_matrix',
        'cell_quotation.approve_quotation_created': 'required',
    }, follow_redirects=True)

    with app.app_context():
        rules = _rules(seed['company_id'], 'quotation.approve')
        assert len(rules) == 1
        assert rules[0].prerequisite == 'quotation_created'
        assert rules[0].mode == 'required'


def test_blanking_a_cell_deletes_the_rule(app, client, login, seed):
    from app.config import db

    with app.app_context():
        db.session.add(WorkflowRule(
            company_id=seed['company_id'], action='quotation.approve',
            prerequisite='quotation_created', mode='required', is_active=True))
        db.session.commit()

    login('admin')
    client.post('/settings/workflow', data={'action': 'save_matrix'},
                follow_redirects=True)

    with app.app_context():
        assert _rules(seed['company_id'], 'quotation.approve') == []


def test_a_cell_can_hold_any_of_the_four_modes(app, client, login, seed):
    login('admin')
    for mode in ('required', 'waivable', 'optional', 'contract'):
        client.post('/settings/workflow', data={
            'action': 'save_matrix',
            'cell_handover.confirm_handover_confirmed': mode,
        }, follow_redirects=True)

        with app.app_context():
            rules = _rules(seed['company_id'], 'handover.confirm')
            assert len(rules) == 1
            assert rules[0].mode == mode


def test_an_unknown_mode_is_refused(app, client, login, seed):
    login('admin')
    client.post('/settings/workflow', data={
        'action': 'save_matrix',
        'cell_quotation.approve_quotation_created': 'whatever',
    }, follow_redirects=True)

    with app.app_context():
        assert _rules(seed['company_id'], 'quotation.approve') == []


def test_an_unknown_action_or_prerequisite_is_ignored(app, client, login, seed):
    """The form names every legitimate pairing; anything else is hand-made."""
    login('admin')
    client.post('/settings/workflow', data={
        'action': 'save_matrix',
        'cell_made.up_nonsense': 'required',
    }, follow_redirects=True)

    with app.app_context():
        assert _rules(seed['company_id'], 'made.up') == []


def test_one_action_can_carry_several_prerequisites(app, client, login, seed):
    login('admin')
    client.post('/settings/workflow', data={
        'action': 'save_matrix',
        'cell_payment.final_handover_confirmed': 'required',
        'cell_payment.final_contract_signed': 'optional',
    }, follow_redirects=True)

    with app.app_context():
        rules = {rule.prerequisite: rule.mode
                 for rule in _rules(seed['company_id'], 'payment.final')}
        assert rules == {'handover_confirmed': 'required',
                         'contract_signed': 'optional'}


def test_saving_does_not_touch_another_company(app, client, login, seed):
    from app.config import db
    from app.models import Company

    with app.app_context():
        rival = Company(company_code='WFM', name='Rival', email='r@wfm.test')
        db.session.add(rival)
        db.session.flush()
        db.session.add(WorkflowRule(
            company_id=rival.id, action='quotation.approve',
            prerequisite='quotation_created', mode='required', is_active=True))
        rival_id = rival.id
        db.session.commit()

    login('admin')
    client.post('/settings/workflow', data={'action': 'save_matrix'},
                follow_redirects=True)

    with app.app_context():
        assert len(_rules(rival_id, 'quotation.approve')) == 1


# --- the engine actually reads what the grid wrote ------------------------

def test_a_rule_set_in_the_grid_is_enforced(app, client, login, seed):
    """The whole point: configuration that reaches the behaviour."""
    import datetime as dt

    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus
    from app.services.workflow_service import (
        ACTION_HANDOVER_CREATE, WorkflowService,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-WFM',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id, contract_created=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-WFM', contract_date=dt.date(2026, 1, 1),
            contract_value=1_000_000, advance_percentage=0, is_signed=True))
        order_id = str(order.id)
        db.session.commit()

    login('admin')
    client.post('/settings/workflow', data={
        'action': 'save_matrix',
        'cell_handover.create_contract_signed': 'required',
    }, follow_redirects=True)

    with app.app_context():
        order = Order.query.get(order_id)
        assert WorkflowService.can(order, ACTION_HANDOVER_CREATE) is False, (
            'a rule set in the grid must reach the engine'
        )
