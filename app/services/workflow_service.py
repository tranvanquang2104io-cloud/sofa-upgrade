"""The order workflow engine — one place that knows the legal order of events.

WHY THIS EXISTS
---------------
Sequencing used to be expressed in three unrelated places:

1. ``LifecycleStatus`` boolean flags (the data),
2. per-document ``can_edit``/``can_approve``/``can_sign``/``can_confirm``
   guards on the models — which can only see their *own* document and so
   cannot express "a handover needs a signed contract",
3. hardcoded ``if ...: raise ValueError(...)`` blocks inside individual
   service methods (``services.py:745``, ``:875-880``), plus a second,
   parallel lifecycle-mutation path in the route layer
   (``skip_advance_payment``, ``dashboard_routes.py:1765``).

Nothing enumerated the graph, so the flow could not be reasoned about or
reconfigured — which is exactly the rigidity the business ran into.

WHAT THIS DOES
--------------
``WorkflowService.check(order, action)`` consults ``workflow_rules`` rows for
the order's company and returns which prerequisites are unmet, split by mode.
``require()`` raises on a hard block. A ``waivable`` rule can be bypassed via
``waive()``, which records who waived it and why — replacing the untracked
``advance_skipped`` boolean.

BEHAVIOUR IS UNCHANGED ON INSTALL. ``DEFAULT_RULES`` reproduces the previously
hardcoded rules exactly; seeding a company produces today's behaviour. Only an
administrator editing the rules changes anything.
"""
import logging

from app.config.database import db
from app.models.models import LifecycleStatus, WorkflowRule, WorkflowWaiver

logger = logging.getLogger(__name__)


# --- Actions -------------------------------------------------------------
# Stable identifiers for the points in the flow that can be gated.
ACTION_QUOTATION_APPROVE = 'quotation.approve'
ACTION_CONTRACT_CREATE = 'contract.create'
ACTION_CONTRACT_SIGN = 'contract.sign'
ACTION_HANDOVER_CREATE = 'handover.create'
ACTION_HANDOVER_CONFIRM = 'handover.confirm'
ACTION_PAYMENT_ADVANCE = 'payment.advance'
ACTION_PAYMENT_FINAL = 'payment.final'

ALL_ACTIONS = (
    ACTION_QUOTATION_APPROVE,
    ACTION_CONTRACT_CREATE,
    ACTION_CONTRACT_SIGN,
    ACTION_HANDOVER_CREATE,
    ACTION_HANDOVER_CONFIRM,
    ACTION_PAYMENT_ADVANCE,
    ACTION_PAYMENT_FINAL,
)

# Human-readable labels for lifecycle flags, used to build block messages.
PREREQUISITE_LABELS = {
    'quotation_created': 'a quotation has been created',
    'quotation_approved': 'the quotation has been approved',
    'contract_created': 'a contract has been created',
    'contract_signed': 'the contract has been signed',
    'handover_confirmed': 'the handover record has been confirmed',
    'advance_paid': 'the advance payment has been received',
    'fully_paid': 'the order has been fully paid',
}

# --- Default rules -------------------------------------------------------
# (action, prerequisite, mode). These MUST reproduce the behaviour that was
# previously hardcoded, so that installing the engine is a no-op:
#
#  * handover requires advance paid          <- services.py:745-747
#  * advance payment requires signed contract <- services.py:875-877
#  * final payment requires confirmed handover <- services.py:878-880
#  * contract does NOT require an approved quotation  <- AUDIT D6 decided this
#    is by design (quote-to-cash/CPQ practice), so it is seeded as `optional`:
#    surfaced to the user, never blocking.
#
# `advance_paid` is seeded as `waivable` because the product already had an
# escape hatch for it (the `advance_skipped` flag) — that hack now becomes a
# first-class, audited waiver instead of a parallel code path.
DEFAULT_RULES = (
    (ACTION_CONTRACT_CREATE, 'quotation_approved', WorkflowRule.MODE_OPTIONAL),
    (ACTION_CONTRACT_SIGN, 'contract_created', WorkflowRule.MODE_REQUIRED),
    (ACTION_HANDOVER_CREATE, 'advance_paid', WorkflowRule.MODE_WAIVABLE),
    (ACTION_PAYMENT_ADVANCE, 'contract_signed', WorkflowRule.MODE_REQUIRED),
    (ACTION_PAYMENT_FINAL, 'handover_confirmed', WorkflowRule.MODE_REQUIRED),
)


class WorkflowBlocked(ValueError):
    """Raised when a required prerequisite is unmet.

    Subclasses ValueError so existing callers that catch ValueError (the whole
    route layer) keep behaving exactly as they did.
    """

    def __init__(self, message, unmet=None):
        super().__init__(message)
        self.unmet = unmet or []


class WorkflowService:
    """Evaluates workflow rules for an order."""

    # ---- configuration ----------------------------------------------

    @staticmethod
    def seed_defaults(company_id, overwrite=False):
        """Install the default rule set for a company.

        Idempotent: existing rules are left alone unless ``overwrite`` is set,
        so re-running never clobbers an administrator's customisation.
        """
        created = 0
        for order_index, (action, prereq, mode) in enumerate(DEFAULT_RULES):
            existing = WorkflowRule.query.filter_by(
                company_id=company_id, action=action, prerequisite=prereq,
            ).first()
            if existing:
                if overwrite:
                    existing.mode = mode
                    existing.is_active = True
                continue
            db.session.add(WorkflowRule(
                company_id=company_id, action=action, prerequisite=prereq,
                mode=mode, sort_order=order_index,
            ))
            created += 1
        db.session.commit()
        logger.info("Seeded %s workflow rules for company %s", created, company_id)
        return created

    @staticmethod
    def rules_for(company_id, action):
        """Active rules for one action, in display order.

        Falls back to DEFAULT_RULES when a company has no rows yet, so an
        un-seeded tenant still behaves exactly as before rather than losing
        all its guards.
        """
        rules = WorkflowRule.query.filter_by(
            company_id=company_id, action=action, is_active=True,
        ).order_by(WorkflowRule.sort_order).all()
        if rules:
            return rules
        return [
            WorkflowRule(company_id=company_id, action=a, prerequisite=p, mode=m)
            for (a, p, m) in DEFAULT_RULES if a == action
        ]

    # ---- evaluation --------------------------------------------------

    @staticmethod
    def _message_for(rule):
        if rule.message:
            return rule.message
        label = PREREQUISITE_LABELS.get(rule.prerequisite, rule.prerequisite)
        return f"This step requires that {label}."

    @classmethod
    def check(cls, order, action):
        """Evaluate ``action`` against ``order``.

        Returns ``(blocked, warnings)``:
          * ``blocked``  — rules that refuse the action (required, or waivable
                           with no recorded waiver)
          * ``warnings`` — optional rules whose prerequisite is unmet
        Both are lists of ``(rule, message)``.
        """
        if order is None:
            raise WorkflowBlocked('Order not found')

        lifecycle = order.lifecycle
        blocked, warnings = [], []

        for rule in cls.rules_for(order.company_id, action):
            met = bool(getattr(lifecycle, rule.prerequisite, False)) if lifecycle else False
            if met:
                continue

            if rule.mode == WorkflowRule.MODE_OPTIONAL:
                warnings.append((rule, cls._message_for(rule)))
            elif rule.mode == WorkflowRule.MODE_WAIVABLE:
                if not cls.has_waiver(order.id, action, rule.prerequisite):
                    blocked.append((rule, cls._message_for(rule)))
            else:
                blocked.append((rule, cls._message_for(rule)))

        return blocked, warnings

    @classmethod
    def can(cls, order, action):
        """True when nothing blocks ``action``."""
        blocked, _ = cls.check(order, action)
        return not blocked

    @classmethod
    def require(cls, order, action):
        """Raise ``WorkflowBlocked`` if any rule refuses the action."""
        blocked, _ = cls.check(order, action)
        if blocked:
            raise WorkflowBlocked(
                ' '.join(message for _, message in blocked),
                unmet=[rule.prerequisite for rule, _ in blocked],
            )
        return True

    # ---- waivers -----------------------------------------------------

    @staticmethod
    def has_waiver(order_id, action, prerequisite):
        return WorkflowWaiver.query.filter_by(
            order_id=order_id, action=action, prerequisite=prerequisite,
        ).first() is not None

    @staticmethod
    def waive(order, action, prerequisite, reason, user_id=None):
        """Record an audited bypass of a waivable rule.

        Refuses to waive a rule that is not marked waivable — otherwise the
        waiver mechanism would become a way around every hard business control.
        """
        if not reason or not str(reason).strip():
            raise ValueError('A reason is required to waive a workflow step')

        rule = next(
            (r for r in WorkflowService.rules_for(order.company_id, action)
             if r.prerequisite == prerequisite),
            None,
        )
        if rule is None:
            raise ValueError(f'No workflow rule {action}/{prerequisite} to waive')
        if rule.mode != WorkflowRule.MODE_WAIVABLE:
            raise ValueError(
                f'Step {prerequisite} of {action} is {rule.mode} and cannot be waived'
            )

        waiver = WorkflowWaiver(
            company_id=order.company_id, order_id=order.id, action=action,
            prerequisite=prerequisite, reason=str(reason).strip(),
            waived_by_user_id=user_id,
        )
        db.session.add(waiver)
        db.session.commit()
        logger.info("Workflow waiver recorded: %s/%s on order %s",
                    action, prerequisite, order.id)
        return waiver
