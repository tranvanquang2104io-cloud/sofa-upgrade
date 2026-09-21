"""The third workflow mode did nothing at all.

`WorkflowService.check()` returns `(blocked, warnings)`. Every caller in the
codebase discards the second half with `_`, so an OPTIONAL rule neither blocked
an action nor said anything about it — it was a setting on the workflow screen
with no observable effect whatsoever.

That matters because OPTIONAL is exactly the mode for the business's own
phrasing: "we usually approve the quotation first, but not always". Silently
doing nothing turns advice into absence.

Warnings are advice, so they are shown where the decision is made — the order
page — and never as a dialog or a blocker.
"""
import datetime as dt

import pytest

from app.services.workflow_service import WorkflowService


@pytest.fixture()
def an_order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-ADV',
                  title='Sofa góc')
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id, quotation_created=True))
        db.session.commit()
        return {'order_id': str(o.id), **seed}


def _rule(app, company_id, action, prerequisite, mode):
    from app.config import db
    from app.models.models import WorkflowRule

    with app.app_context():
        rule = WorkflowRule.query.filter_by(company_id=company_id,
                                            action=action).first()
        if rule is None:
            rule = WorkflowRule(company_id=company_id, action=action)
            db.session.add(rule)
        rule.prerequisite, rule.mode = prerequisite, mode
        db.session.commit()


def _order(order_id):
    from app.models import Order
    return Order.query.get(order_id)


# --- the service ---------------------------------------------------------

def test_an_unmet_optional_rule_produces_an_advisory(app, an_order):
    from app.models.models import WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_OPTIONAL)

    with app.app_context():
        advisories = WorkflowService.advisories(_order(an_order['order_id']))
        assert len(advisories) == 1
        assert advisories[0]['action'] == 'contract.create'


def test_a_met_optional_rule_says_nothing(app, an_order):
    from app.config import db
    from app.models.models import LifecycleStatus, WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_OPTIONAL)
    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=an_order['order_id']).first()
        lifecycle.quotation_approved = True
        db.session.commit()

        assert WorkflowService.advisories(_order(an_order['order_id'])) == []


def test_a_required_rule_is_not_an_advisory(app, an_order):
    """A block is not advice: it is refused at the action and says so there."""
    from app.models.models import WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_REQUIRED)

    with app.app_context():
        assert WorkflowService.advisories(_order(an_order['order_id'])) == []


def test_an_inactive_rule_says_nothing(app, an_order):
    """Off means off — see test_workflow_rule_off.py for why that needed fixing."""
    from app.config import db
    from app.models.models import WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_OPTIONAL)
    with app.app_context():
        WorkflowRule.query.filter_by(
            company_id=an_order['company_id'],
            action='contract.create').first().is_active = False
        db.session.commit()

        actions = {a['action'] for a in
                   WorkflowService.advisories(_order(an_order['order_id']))}
        assert 'contract.create' not in actions


def test_advisories_do_not_cross_tenants(app, an_order):
    """Another company's rule must not appear here.

    ACME is given its own rules first: without them it falls back to
    DEFAULT_RULES, and an advisory from that fallback would mask the question
    being asked.
    """
    from app.config import db
    from app.models import Company
    from app.models.models import WorkflowRule

    with app.app_context():
        WorkflowService.seed_defaults(an_order['company_id'])
        for rule in WorkflowRule.query.filter_by(
                company_id=an_order['company_id']).all():
            rule.is_active = False
        rival = Company(company_code="ADV", name="Rival", email="r@adv.test")
        db.session.add(rival)
        db.session.flush()
        db.session.add(WorkflowRule(company_id=rival.id,
                                    action='contract.create',
                                    prerequisite='quotation_approved',
                                    mode=WorkflowRule.MODE_OPTIONAL))
        db.session.commit()

        assert WorkflowService.advisories(_order(an_order['order_id'])) == []


# --- the screen ----------------------------------------------------------

def test_the_order_page_shows_the_advisory(app, client, login, an_order):
    from app.models.models import WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_OPTIONAL)

    login("admin")
    body = client.get(f"/orders/{an_order['order_id']}").get_data(as_text=True)
    assert ('thường' in body.lower() or 'usually' in body.lower()
            or 'khuyến nghị' in body.lower()), (
        "an optional rule must read as advice on the page where the user acts"
    )


def test_the_order_page_is_quiet_when_nothing_is_advised(app, client, login,
                                                          an_order):
    """Clutter is the failure mode this product cannot afford."""
    from app.config import db
    from app.models.models import LifecycleStatus, WorkflowRule

    _rule(app, an_order['company_id'], 'contract.create', 'quotation_approved',
          WorkflowRule.MODE_OPTIONAL)
    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=an_order['order_id']).first()
        lifecycle.quotation_approved = True
        db.session.commit()

    login("admin")
    body = client.get(f"/orders/{an_order['order_id']}").get_data(as_text=True)
    assert 'workflow-advisory' not in body
