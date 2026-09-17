"""Contract for the configurable workflow engine.

The critical property is the FIRST test: installing the engine must not change
behaviour. The defaults reproduce the rules that were previously hardcoded in
services.py, so a company that has never touched the configuration behaves
exactly as it did before.
"""
import pytest

from app.models.models import WorkflowRule
from app.services.workflow_service import (
    ACTION_CONTRACT_CREATE,
    ACTION_HANDOVER_CREATE,
    ACTION_PAYMENT_ADVANCE,
    ACTION_PAYMENT_FINAL,
    DEFAULT_RULES,
    WorkflowBlocked,
    WorkflowService,
)


@pytest.fixture()
def order(app, seed):
    """An order with a fresh (all-false) lifecycle."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-WF1",
                  title="Workflow order")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id))
        db.session.commit()
        return str(o.id)


def _get(order_id):
    from app.models import Order
    return Order.query.get(order_id)


def _set_lifecycle(order_id, **flags):
    from app.config import db
    o = _get(order_id)
    for key, value in flags.items():
        setattr(o.lifecycle, key, value)
    db.session.commit()
    return o


# --- the no-op property ---------------------------------------------------

def test_defaults_reproduce_the_previously_hardcoded_rules(app, order):
    """Installing the engine must not change behaviour for an unseeded company.

    These four assertions mirror services.py:745-747 and :875-880 exactly.
    """
    with app.app_context():
        o = _get(order)

        # advance payment required a SIGNED CONTRACT (services.py:875-877)
        assert not WorkflowService.can(o, ACTION_PAYMENT_ADVANCE)
        _set_lifecycle(order, contract_signed=True)
        assert WorkflowService.can(_get(order), ACTION_PAYMENT_ADVANCE)

        # final payment required a CONFIRMED HANDOVER (services.py:878-880)
        assert not WorkflowService.can(_get(order), ACTION_PAYMENT_FINAL)
        _set_lifecycle(order, handover_confirmed=True)
        assert WorkflowService.can(_get(order), ACTION_PAYMENT_FINAL)


def test_handover_requires_advance_paid_by_default(app, order):
    """services.py:745-747 — handover blocked until the advance is paid."""
    with app.app_context():
        assert not WorkflowService.can(_get(order), ACTION_HANDOVER_CREATE)
        _set_lifecycle(order, advance_paid=True)
        assert WorkflowService.can(_get(order), ACTION_HANDOVER_CREATE)


def test_contract_does_not_require_an_approved_quotation(app, order):
    """AUDIT D6 decided this is by design; it must warn, never block."""
    with app.app_context():
        o = _get(order)
        blocked, warnings = WorkflowService.check(o, ACTION_CONTRACT_CREATE)
        assert blocked == [], "contract creation must not be hard-blocked"
        assert len(warnings) == 1, "but the unapproved quotation should surface"
        assert warnings[0][0].prerequisite == 'quotation_approved'


def test_require_raises_workflow_blocked_which_is_a_valueerror(app, order):
    """Existing routes catch ValueError; the new exception must stay compatible."""
    with app.app_context():
        with pytest.raises(WorkflowBlocked) as exc:
            WorkflowService.require(_get(order), ACTION_PAYMENT_ADVANCE)
        assert isinstance(exc.value, ValueError)
        assert 'contract_signed' in exc.value.unmet


# --- configurability ------------------------------------------------------

def test_seeding_is_idempotent(app, seed):
    with app.app_context():
        first = WorkflowService.seed_defaults(seed["company_id"])
        second = WorkflowService.seed_defaults(seed["company_id"])
        assert first == len(DEFAULT_RULES)
        assert second == 0, "re-seeding must not duplicate or clobber rules"


def test_admin_can_relax_a_required_rule(app, seed, order):
    """The whole point: a business can change the flow without a deploy."""
    from app.config import db

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])

        # Out of the box, an advance payment needs a signed contract.
        assert not WorkflowService.can(_get(order), ACTION_PAYMENT_ADVANCE)

        # The business wants to take a deposit right after quotation approval.
        rule = WorkflowRule.query.filter_by(
            company_id=seed["company_id"], action=ACTION_PAYMENT_ADVANCE,
            prerequisite='contract_signed').first()
        rule.mode = WorkflowRule.MODE_OPTIONAL
        db.session.commit()

        assert WorkflowService.can(_get(order), ACTION_PAYMENT_ADVANCE), (
            "relaxing the rule to optional should unblock the deposit"
        )


def test_rules_are_per_company(app, seed, order):
    """One tenant's configuration must not affect another's."""
    from app.config import db
    from app.models import Company

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        other = Company(company_code="WF2", name="Other Co", email="o@wf2.test")
        db.session.add(other)
        db.session.commit()

        rule = WorkflowRule.query.filter_by(
            company_id=seed["company_id"], action=ACTION_PAYMENT_ADVANCE).first()
        rule.is_active = False
        db.session.commit()

        # The other company has no rows, so it falls back to the defaults and
        # keeps the guard.
        assert WorkflowService.rules_for(other.id, ACTION_PAYMENT_ADVANCE), (
            "a company with no configuration must still get the default guards"
        )


# --- waivers --------------------------------------------------------------

def test_waivable_step_blocks_until_waived_then_allows(app, seed, order):
    """Generalises the old untracked `advance_skipped` flag."""
    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        o = _get(order)
        assert not WorkflowService.can(o, ACTION_HANDOVER_CREATE)

        WorkflowService.waive(o, ACTION_HANDOVER_CREATE, 'advance_paid',
                              reason='Khách thanh toán 100% khi giao hàng',
                              user_id=seed["admin_id"])

        assert WorkflowService.can(_get(order), ACTION_HANDOVER_CREATE)


def test_waiver_requires_a_reason(app, seed, order):
    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        with pytest.raises(ValueError):
            WorkflowService.waive(_get(order), ACTION_HANDOVER_CREATE,
                                  'advance_paid', reason='  ')


def test_a_required_rule_cannot_be_waived(app, seed, order):
    """Otherwise waivers would become a way around every hard control."""
    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        with pytest.raises(ValueError, match='cannot be waived'):
            WorkflowService.waive(_get(order), ACTION_PAYMENT_ADVANCE,
                                  'contract_signed', reason='just because')


def test_waiver_records_who_and_why(app, seed, order):
    from app.models.models import WorkflowWaiver

    with app.app_context():
        WorkflowService.seed_defaults(seed["company_id"])
        WorkflowService.waive(_get(order), ACTION_HANDOVER_CREATE, 'advance_paid',
                              reason='Giao hàng gấp theo yêu cầu khách',
                              user_id=seed["admin_id"])

        w = WorkflowWaiver.query.filter_by(order_id=order).first()
        assert w is not None
        assert w.reason == 'Giao hàng gấp theo yêu cầu khách'
        assert str(w.waived_by_user_id) == seed["admin_id"]
        assert w.waived_at is not None
