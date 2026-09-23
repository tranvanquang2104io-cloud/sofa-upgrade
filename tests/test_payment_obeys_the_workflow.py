"""Configuration the action ignores is worse than no configuration.

The owner's rule for this area: flexible to configure, strict to act. The
payment screen was strict to act and deaf to configuration — it re-implemented
its own sequencing inline:

    if payment_type == 'advance' and not order.lifecycle.contract_signed: ...
    if payment_type == 'final' and not order.lifecycle.handover_confirmed: ...

`PaymentReportService.create_payment_report` already asks
`WorkflowService.require()`, which is the configurable gate. So an administrator
who switched `payment.advance` off at /settings/workflow — to take a deposit
before signing, which is the case that screen exists for — was still refused, by
a rule no screen could reach.

That is the same defect the workflow engine was built to remove, left standing
on the busiest money screen. A setting that does nothing teaches people the
settings do not work.

Turning a rule off must not weaken anything else: the strictness has to come
from one place, not two, so the rules that remain on are still enforced.
"""
import datetime as dt

import pytest


@pytest.fixture()
def unsigned_order(app, seed):
    """A contract drafted but not signed — the state an advance is blocked by."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-EARLY',
                      title='Sofa góc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       quotation_approved=True,
                                       contract_created=True,
                                       contract_signed=False))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-EARLY', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=30,
            is_signed=False, is_active=True))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def _switch_off(app, company_id, action):
    """Turn a workflow rule off the way the settings screen does."""
    from app.config import db
    from app.models.models import WorkflowRule
    from app.services.workflow_service import WorkflowService

    with app.app_context():
        WorkflowService.seed_defaults(company_id)
        for rule in WorkflowRule.query.filter_by(company_id=company_id,
                                                 action=action).all():
            rule.is_active = False
        db.session.commit()


def test_by_default_an_advance_still_waits_for_the_signature(
        app, client, login, unsigned_order):
    """The shipped rule must keep working."""
    from app.models.models import PaymentReport

    login('admin')
    client.post(f"/payment/{unsigned_order['order_id']}/create",
                data={'payment_type': 'advance', 'report_number': 'TT-E1',
                      'report_date': '2026-09-10', 'payment_date': '2026-09-10',
                      'advance_amount': '6000000'},
                follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.filter_by(report_number='TT-E1').first() is None


def test_switching_the_rule_off_actually_lets_the_deposit_through(
        app, client, login, unsigned_order):
    """The point of the settings screen."""
    from app.models.models import PaymentReport
    from app.services.workflow_service import ACTION_PAYMENT_ADVANCE

    _switch_off(app, unsigned_order['company_id'], ACTION_PAYMENT_ADVANCE)

    login('admin')
    client.post(f"/payment/{unsigned_order['order_id']}/create",
                data={'payment_type': 'advance', 'report_number': 'TT-E2',
                      'report_date': '2026-09-10', 'payment_date': '2026-09-10',
                      'advance_amount': '6000000'},
                follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.filter_by(report_number='TT-E2').first() is not None, (
            'the rule was switched off and the screen refused anyway, because '
            'it enforces its own copy of the rule')


def test_turning_one_rule_off_does_not_loosen_another(
        app, client, login, unsigned_order):
    """Strictness must come from one place, not two."""
    from app.models.models import PaymentReport
    from app.services.workflow_service import ACTION_PAYMENT_ADVANCE

    _switch_off(app, unsigned_order['company_id'], ACTION_PAYMENT_ADVANCE)

    login('admin')
    client.post(f"/payment/{unsigned_order['order_id']}/create",
                data={'payment_type': 'final', 'report_number': 'TT-E3',
                      'report_date': '2026-09-10', 'payment_date': '2026-09-10',
                      'amount': '20000000'},
                follow_redirects=True)

    with app.app_context():
        assert PaymentReport.query.filter_by(report_number='TT-E3').first() is None, (
            'the final payment went through without a confirmed handover'
        )
