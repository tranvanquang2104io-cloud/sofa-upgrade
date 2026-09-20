"""Configuration that did nothing, and errors that explained nothing.

Two findings that compound each other.

**The rule was listed but never consulted.** `contract.sign` and
`contract.create` are in `ALL_ACTIONS` and in `DEFAULT_RULES`, and the workflow
settings screen lists them and lets a company admin change their mode. But
nothing ever called `WorkflowService.require()` for either — only handover
creation and the two payment actions were gated. So an admin could set "signing
a contract requires an approved quotation", save it, see it on the screen, and
have it quietly do nothing.

**And when a rule did refuse, the reason was thrown away.** `WorkflowBlocked`
carries the specific sentence to show the user, but six POST handlers caught
broad `Exception` and flashed "Error signing contract". The user presses Sign,
gets a red bar that says "Error", and has no way to learn that the quotation
needs approving first.

Defaults are deliberately unchanged: `contract.sign` requires `contract_created`
out of the box, which is satisfied by the contract existing at all.
"""
import datetime as dt

import pytest


@pytest.fixture()
def order_with_contract(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-WF-1',
                  title='Sofa')
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id, contract_created=True))
        c = Contract(company_id=seed['company_id'], order_id=o.id,
                     contract_number='CT-WF-1', contract_date=dt.date(2026, 1, 1),
                     contract_value=5_000_000)
        db.session.add(c)
        db.session.commit()
        return {'order_id': str(o.id), 'contract_id': str(c.id), **seed}


def _set_rule(app, company_id, action, prerequisite, mode):
    from app.config import db
    from app.models.models import WorkflowRule

    with app.app_context():
        rule = WorkflowRule.query.filter_by(company_id=company_id,
                                            action=action).first()
        if rule is None:
            rule = WorkflowRule(company_id=company_id, action=action)
            db.session.add(rule)
        rule.prerequisite = prerequisite
        rule.mode = mode
        db.session.commit()


# --- the default install must behave exactly as before --------------------

def test_signing_still_works_on_the_default_rules(app, client, login,
                                                  order_with_contract):
    from app.models.models import Contract

    login("admin")
    client.post(f"/contracts/{order_with_contract['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        contract = Contract.query.get(order_with_contract['contract_id'])
        assert contract.is_signed is True


# --- a rule an admin set must actually be enforced ------------------------

def test_a_required_rule_blocks_signing(app, client, login, order_with_contract):
    """The admin says signing needs an approved quotation. It must be refused."""
    from app.models.models import Contract, WorkflowRule

    _set_rule(app, order_with_contract['company_id'], 'contract.sign',
              'quotation_approved', WorkflowRule.MODE_REQUIRED)

    login("admin")
    client.post(f"/contracts/{order_with_contract['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        contract = Contract.query.get(order_with_contract['contract_id'])
        assert contract.is_signed is False, (
            "a rule the admin configured must actually stop the action"
        )


def test_the_refusal_says_why(app, client, login, order_with_contract):
    """"Error signing contract" leaves the user with nothing to act on."""
    from app.models.models import WorkflowRule

    _set_rule(app, order_with_contract['company_id'], 'contract.sign',
              'quotation_approved', WorkflowRule.MODE_REQUIRED)

    login("admin")
    body = client.post(f"/contracts/{order_with_contract['contract_id']}/sign",
                       follow_redirects=True).get_data(as_text=True)

    assert 'requires' in body or 'yêu cầu' in body.lower(), (
        "the message must name the unmet prerequisite, not just say 'Error'"
    )


def test_an_optional_rule_does_not_block(app, client, login,
                                          order_with_contract):
    """Optional means advisory. It must not become a gate."""
    from app.models.models import Contract, WorkflowRule

    _set_rule(app, order_with_contract['company_id'], 'contract.sign',
              'quotation_approved', WorkflowRule.MODE_OPTIONAL)

    login("admin")
    client.post(f"/contracts/{order_with_contract['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        assert Contract.query.get(order_with_contract['contract_id']).is_signed


def test_a_met_prerequisite_allows_signing(app, client, login,
                                            order_with_contract):
    from app.config import db
    from app.models.models import Contract, LifecycleStatus, WorkflowRule

    _set_rule(app, order_with_contract['company_id'], 'contract.sign',
              'quotation_approved', WorkflowRule.MODE_REQUIRED)

    with app.app_context():
        lc = LifecycleStatus.query.filter_by(
            order_id=order_with_contract['order_id']).first()
        lc.quotation_approved = True
        db.session.commit()

    login("admin")
    client.post(f"/contracts/{order_with_contract['contract_id']}/sign",
                follow_redirects=True)

    with app.app_context():
        assert Contract.query.get(order_with_contract['contract_id']).is_signed


def test_a_required_rule_blocks_creating_a_contract(app, client, login, seed):
    """contract.create had the same gap: listed, editable, never consulted."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus, WorkflowRule

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-WF-2',
                  title='Sofa')
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id))
        order_id = str(o.id)
        db.session.commit()

    _set_rule(app, seed['company_id'], 'contract.create', 'quotation_approved',
              WorkflowRule.MODE_REQUIRED)

    login("admin")
    client.post(f"/orders/{order_id}/contracts/create", data={
        'contract_number': 'CT-WF-2',
        'contract_date': '2026-01-01',
        'contract_value': '1000000',
    }, follow_redirects=True)

    with app.app_context():
        assert Contract.query.filter_by(contract_number='CT-WF-2').first() is None


def test_every_seeded_rule_is_enforced_somewhere():
    """A rule an admin can edit must have something that consults it.

    This is the lint for the actual defect: `contract.sign` and
    `contract.create` are seeded into every company and listed on the workflow
    settings screen, so an admin could change them and save them, while no code
    path ever called require() for either. Configuration that cannot affect
    anything is worse than no configuration — it invites someone to rely on it.

    Scoped to DEFAULT_RULES rather than ALL_ACTIONS on purpose. `quotation.approve`
    and `handover.confirm` are declared constants with no seeded rule, and the
    settings screen only renders rules that exist, so they are not reachable by
    an admin today and enforcing them would be inventing a requirement.
    """
    import inspect

    from app.services import services
    from app.services import workflow_service as ws

    enforced = inspect.getsource(services)
    missing = []
    for action, _prereq, _mode in ws.DEFAULT_RULES:
        const = next((n for n in dir(ws)
                      if n.startswith('ACTION_') and getattr(ws, n) == action), None)
        if const is None or f'require(' not in enforced or const not in enforced:
            missing.append(action)

    assert missing == [], (
        f"these workflow rules are seeded and editable but nothing enforces "
        f"them: {missing}"
    )
