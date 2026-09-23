"""A locked screen must name a way out that actually exists.

Reported by the owner: a production plan they had not approved could not be
edited either. Walking it through:

* The plan was in `processing`, not `draft`, so `can_edit()` was False and the
  material list was locked. That part is intended.
* The lock message told them to use **"Từ chối (làm lại)"** to get back.
* There is no such button on the screen, and `reject` is only a legal
  transition from `validating`. From `processing` the only moves are
  `complete` and `cancel`.

So the message sent the user looking for a control that does not exist and
could not work if it did. That is worse than saying nothing: they spend their
time believing the fault is theirs.

What the message may say is limited to what the plan can actually do from where
it is, which is what this test enforces — for every status, not just the one
that was reported.
"""
import pytest

from app.models.models import ProductionPlan


def _transitions_from(status):
    return {action for action, (allowed, _target)
            in ProductionPlan.TRANSITIONS.items() if status in allowed}


def test_reject_is_not_reachable_from_production():
    """The premise of the bug, pinned so the message cannot drift back."""
    assert 'reject' not in _transitions_from(ProductionPlan.STATUS_PROCESSING)


def test_a_plan_in_production_can_only_be_completed_or_cancelled():
    assert _transitions_from(ProductionPlan.STATUS_PROCESSING) == {
        'complete', 'cancel'}


@pytest.mark.parametrize('status', [
    ProductionPlan.STATUS_APPROVED,
    ProductionPlan.STATUS_PROCESSING,
    ProductionPlan.STATUS_COMPLETED,
    ProductionPlan.STATUS_VALIDATING,
    ProductionPlan.STATUS_VALIDATED,
])
def test_the_lock_message_names_only_reachable_actions(status):
    """The message is composed per status and must stay honest for each."""
    from app.services.services import plan_lock_reason

    message, action = plan_lock_reason(status)
    assert message, f'no lock message for {status}'
    if action is not None:
        assert action in _transitions_from(status), (
            f'the message for {status!r} points at {action!r}, which is not a '
            'legal move from there')


def test_a_draft_plan_is_not_locked_at_all():
    from app.services.services import plan_lock_reason

    message, action = plan_lock_reason(ProductionPlan.STATUS_DRAFT)
    assert message is None and action is None, (
        'a draft plan is editable, so there is nothing to explain')


def test_the_screen_shows_the_honest_message(app, client, login, seed):
    """Through the page a user actually opens."""
    from app.config import db
    from app.models import Order
    from app.models.models import ProductionPlan as _Plan
    from app.services.services import plan_lock_reason

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-LOCK',
                      title='Sofa góc')
        db.session.add(order)
        db.session.flush()
        db.session.add(_Plan(company_id=seed['company_id'], order_id=order.id,
                             plan_number='KH-LOCK',
                             status=_Plan.STATUS_PROCESSING))
        db.session.commit()
        order_id = str(order.id)

    from app.utils.i18n import t
    message, _action = plan_lock_reason(_Plan.STATUS_PROCESSING)

    login('admin')
    body = client.get(f'/orders/{order_id}/production-plan').get_data(
        as_text=True)
    assert t(message) in body
    assert 'Từ chối (làm lại)' not in body, (
        'the screen still points at an action it does not offer')
