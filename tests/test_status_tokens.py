"""Contract for the shared status vocabulary (app/utils/status_tokens.py).

Pins two things:
  * the semantic-token mapping, so colour cannot come to mean different things
    on different screens again;
  * the lifecycle ORDERING bug — orders/list.html tested `advance_paid` before
    `handover_confirmed`, and since every delivered order also has
    `advance_paid` set, the "Delivered" badge was unreachable.
"""
import pytest

from app.utils.status_tokens import (
    TOKEN_CLASSES,
    order_process_steps,
    order_status_meta,
    status_meta,
    token_class,
)


class _Lifecycle:
    """Stand-in for LifecycleStatus; all flags default False."""

    _FLAGS = ('quotation_created', 'quotation_approved', 'contract_created',
              'contract_signed', 'advance_paid', 'advance_skipped',
              'handover_confirmed', 'fully_paid', 'completed')

    def __init__(self, **flags):
        for name in self._FLAGS:
            setattr(self, name, flags.get(name, False))


class _Order:
    def __init__(self, lifecycle=None, is_canceled=False):
        self.lifecycle = lifecycle
        self.is_canceled = is_canceled


# --- the ordering bug -----------------------------------------------------

def test_delivered_order_shows_delivered_not_advance_paid():
    """THE BUG: a delivered order also has advance_paid set.

    The old if/elif chain checked advance_paid first, so "Delivered" could
    never render and the order looked stuck on "Advance Paid" from delivery
    until it was fully paid.
    """
    order = _Order(_Lifecycle(quotation_approved=True, contract_signed=True,
                              advance_paid=True, handover_confirmed=True))
    token, label = order_status_meta(order)
    assert label == 'Delivered', (
        f"expected the most advanced stage, got {label!r} — the earlier stage "
        f"is shadowing the later one"
    )
    assert token == 'progress'


def test_signed_contract_shows_contract_signed():
    """Same class of bug one step earlier."""
    order = _Order(_Lifecycle(quotation_approved=True, contract_signed=True))
    _, label = order_status_meta(order)
    assert label == 'Contract Signed'


@pytest.mark.parametrize("flags,expected", [
    ({}, 'New'),
    ({'quotation_created': True}, 'Quotation Created'),
    ({'quotation_approved': True}, 'Quotation Approved'),
    ({'contract_created': True}, 'Contract Drafted'),
    ({'contract_signed': True}, 'Contract Signed'),
    ({'contract_signed': True, 'advance_paid': True}, 'Advance Paid'),
    ({'advance_paid': True, 'handover_confirmed': True}, 'Delivered'),
    ({'handover_confirmed': True, 'fully_paid': True}, 'Fully Paid'),
    ({'fully_paid': True, 'completed': True}, 'Completed'),
])
def test_every_stage_is_reachable(flags, expected):
    """No stage may be shadowed by an earlier one."""
    assert order_status_meta(_Order(_Lifecycle(**flags)))[1] == expected


def test_cancelled_order_overrides_every_stage():
    order = _Order(_Lifecycle(fully_paid=True, completed=True), is_canceled=True)
    token, label = order_status_meta(order)
    assert (token, label) == ('critical', 'Cancelled')


# --- skipped vs paid advance (F23 display) --------------------------------

def test_skipped_advance_is_not_shown_as_paid():
    """An advance that was waived must not look like money received."""
    order = _Order(_Lifecycle(contract_signed=True, advance_paid=True,
                              advance_skipped=True))
    token, label = order_status_meta(order)
    assert label == 'Advance Skipped'
    assert token == 'attention', "a skipped step is not a success state"


def test_skipped_advance_shows_as_skipped_in_the_stepper():
    order = _Order(_Lifecycle(contract_signed=True, advance_paid=True,
                              advance_skipped=True))
    steps = {s['key']: s['state'] for s in order_process_steps(order)}
    assert steps['advance_paid'] == 'skipped'
    assert steps['contract_signed'] == 'done'


# --- the stepper ----------------------------------------------------------

def test_stepper_marks_exactly_one_current_step():
    order = _Order(_Lifecycle(quotation_approved=True, contract_signed=True))
    steps = order_process_steps(order)
    assert [s['state'] for s in steps].count('current') == 1


def test_stepper_is_all_done_when_fully_paid():
    order = _Order(_Lifecycle(quotation_approved=True, contract_signed=True,
                              advance_paid=True, handover_confirmed=True,
                              fully_paid=True))
    assert all(s['state'] == 'done' for s in order_process_steps(order))


def test_stepper_handles_a_missing_lifecycle():
    steps = order_process_steps(_Order(lifecycle=None))
    assert steps[0]['state'] == 'current'
    assert all(s['state'] == 'todo' for s in steps[1:])


# --- the token vocabulary -------------------------------------------------

@pytest.mark.parametrize("status,entity,token", [
    ('draft', 'document', 'neutral'),
    ('approved', 'document', 'success'),
    ('canceled', 'document', 'critical'),
    ('cancelled', 'document', 'critical'),
    ('partial', 'procurement', 'attention'),
    ('ordered', 'procurement', 'progress'),
    ('received', 'procurement', 'success'),
])
def test_status_maps_to_the_expected_token(status, entity, token):
    assert status_meta(status, entity)[0] == token


def test_unknown_status_degrades_to_neutral_and_keeps_its_text():
    token, label = status_meta('some_new_state')
    assert token == 'neutral'
    assert label == 'some_new_state', "never hide a status we don't recognise"


def test_status_lookup_is_case_and_space_insensitive():
    assert status_meta('  Approved ')[0] == 'success'


def test_none_status_is_safe():
    assert status_meta(None)[0] == 'neutral'


def test_every_token_has_a_bootstrap_class():
    for token in ('neutral', 'progress', 'attention', 'success', 'critical'):
        assert token in TOKEN_CLASSES
    assert token_class('nonsense') == TOKEN_CLASSES['neutral']


# --- rendered output ------------------------------------------------------

def test_orders_list_shows_delivered_for_a_delivered_order(app, client, login, seed):
    """End-to-end proof that the badge fix reaches the actual page.

    Before the shared resolver, this page rendered "Advance Paid" for a
    delivered order because the if/elif chain tested the earlier flag first.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-BADGE",
                      title="Delivered order")
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, quotation_created=True, quotation_approved=True,
            contract_created=True, contract_signed=True, advance_paid=True,
            handover_confirmed=True))
        db.session.commit()

    login("admin")
    body = client.get('/orders').get_data(as_text=True)

    assert 'ORD-BADGE' in body, "the order should be listed"
    assert 'Delivered' in body or 'Đã giao' in body, (
        "a delivered order must show the Delivered stage, not the earlier one"
    )
