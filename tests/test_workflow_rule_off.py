"""Turning a workflow rule off turned it back on.

`rules_for()` falls back to DEFAULT_RULES when a company has no ACTIVE rows for
an action. That fallback exists for a good reason — an un-seeded tenant must
still behave as before rather than losing all its guards — but it could not
tell "never configured" from "deliberately switched off".

So the On checkbox on the workflow settings screen did not turn a step off. It
reverted it to the shipped default. The case that matters is the business's own
example, the one the plan cites: an admin unticks `payment.advance` so a
deposit can be taken before the contract is formally signed, and the default
REQUIRED rule comes straight back and blocks it.

Rows that exist and are all inactive now mean off. No rows at all still means
defaults.
"""
import datetime as dt

import pytest

from app.services.workflow_service import WorkflowService


@pytest.fixture()
def order_ready_for_advance(app, seed):
    """An order with a contract drafted but NOT signed."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-OFF',
                  title='Sofa')
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id, quotation_created=True,
                                       contract_created=True))
        db.session.add(Contract(company_id=seed['company_id'], order_id=o.id,
                                contract_number='CT-OFF',
                                contract_date=dt.date(2026, 1, 1),
                                contract_value=5_000_000))
        db.session.commit()
        return {'order_id': str(o.id), **seed}


def _order(order_id):
    from app.models import Order
    return Order.query.get(order_id)


def _seed_rules(app, company_id):
    from app.config import db

    with app.app_context():
        WorkflowService.seed_defaults(company_id)
        db.session.commit()


def test_an_unseeded_company_still_gets_the_default_guards(
        app, order_ready_for_advance):
    """The fallback must survive: this is why it exists."""
    with app.app_context():
        order = _order(order_ready_for_advance['order_id'])
        assert WorkflowService.can(order, 'payment.advance') is False


def test_switching_a_rule_off_actually_switches_it_off(
        app, order_ready_for_advance):
    """The admin's stated scenario: take a deposit before signing."""
    from app.config import db
    from app.models.models import WorkflowRule

    company_id = order_ready_for_advance['company_id']
    _seed_rules(app, company_id)

    with app.app_context():
        for rule in WorkflowRule.query.filter_by(company_id=company_id,
                                                 action='payment.advance').all():
            rule.is_active = False
        db.session.commit()

        order = _order(order_ready_for_advance['order_id'])
        assert WorkflowService.can(order, 'payment.advance') is True, (
            "unticking the rule must let the deposit through, not restore the "
            "shipped default"
        )


def test_switching_one_rule_off_leaves_the_others_alone(
        app, order_ready_for_advance):
    from app.config import db
    from app.models.models import WorkflowRule

    company_id = order_ready_for_advance['company_id']
    _seed_rules(app, company_id)

    with app.app_context():
        for rule in WorkflowRule.query.filter_by(company_id=company_id,
                                                 action='payment.advance').all():
            rule.is_active = False
        db.session.commit()

        order = _order(order_ready_for_advance['order_id'])
        assert WorkflowService.can(order, 'payment.final') is False, (
            "final payment still requires the handover"
        )


def test_switching_it_back_on_restores_the_guard(app, order_ready_for_advance):
    from app.config import db
    from app.models.models import WorkflowRule

    company_id = order_ready_for_advance['company_id']
    _seed_rules(app, company_id)

    with app.app_context():
        rules = WorkflowRule.query.filter_by(company_id=company_id,
                                             action='payment.advance').all()
        for rule in rules:
            rule.is_active = False
        db.session.commit()
        for rule in rules:
            rule.is_active = True
        db.session.commit()

        assert WorkflowService.can(
            _order(order_ready_for_advance['order_id']), 'payment.advance') is False
