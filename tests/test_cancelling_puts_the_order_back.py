"""Cancelling a contract through the UI left the order thinking it still had one.

`ContractService.cancel_contract` exists, and it rolls `lifecycle.contract_created`
back when no other active contract remains. The ROUTE does not call it. It sets
the four flags on the model itself and commits.

So the service path was reachable only from tests. It was green, it was
correct, and in production nothing ever ran it -- the sixth instance in this
repo of finished work that nothing reaches, and the first where the unreachable
version is the CORRECT one and the live version is the broken one.

What the user sees: cancel the only contract on an order, and the order still
says a contract has been created. The next screen offers no "create contract"
button, because that button asks the lifecycle. The order is stuck in a state
the person has already undone, and the only way out is another contract they
did not want.

`cancel_order` has the same shape, and `OrderService` has no cancel method at
all -- so that one could not be routed to a service without writing one.

The lifecycle is RECOMPUTED from the contracts that actually exist, not
unpicked flag by flag. Unpicking assumes you know everything the flag was
turned on by; recomputing asks the data. That is the same choice
`_resync_payment_lifecycle` made, for the same reason.
"""
import datetime as dt

import pytest


@pytest.fixture()
def order_with_contract(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-CANC',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, contract_created=True,
            contract_created_at=dt.datetime(2026, 9, 1)))
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-CANC', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=50,
            is_signed=False, is_active=True)
        db.session.add(contract)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'contract_id': str(contract.id)}


def _lifecycle(app, order_id):
    from app.models.models import LifecycleStatus

    with app.app_context():
        return LifecycleStatus.query.filter_by(order_id=order_id).first()


def test_cancelling_the_only_contract_lets_the_order_have_one_again(
        app, client, login, order_with_contract):
    """Through the ROUTE, because that is the path that was broken."""
    from app.models.models import Contract

    login('admin')
    client.post(f"/contracts/{order_with_contract['contract_id']}/cancel",
                data={'canceled_reason': 'Khach doi mau vai'},
                follow_redirects=True)

    with app.app_context():
        contract = Contract.query.get(order_with_contract['contract_id'])
        assert contract.is_canceled is True, 'the cancellation did not happen'

    lifecycle = _lifecycle(app, order_with_contract['order_id'])
    assert lifecycle.contract_created is False, (
        'the order still believes it has a contract, so the screen will not '
        'offer to create one and the order is stuck in a state the user has '
        'already undone')
    assert lifecycle.contract_created_at is None


def test_a_second_active_contract_keeps_the_flag_on(app, client, login,
                                                    order_with_contract):
    """Recomputed from the data, not blindly cleared.

    Two contracts on one order is not exotic: a superseded draft that was
    never cancelled sits beside the real one. Cancelling one of them must not
    tell the order it has none.
    """
    from app.config import db
    from app.models.models import Contract

    with app.app_context():
        db.session.add(Contract(
            company_id=order_with_contract['company_id'],
            order_id=order_with_contract['order_id'],
            contract_number='HD-CANC-2', contract_date=dt.date(2026, 9, 2),
            contract_value=21_000_000, advance_percentage=50,
            is_signed=False, is_active=True))
        db.session.commit()

    login('admin')
    client.post(f"/contracts/{order_with_contract['contract_id']}/cancel",
                data={'canceled_reason': 'Ban nhap cu'}, follow_redirects=True)

    lifecycle = _lifecycle(app, order_with_contract['order_id'])
    assert lifecycle.contract_created is True, (
        'the order was told it has no contract while an active one remains')


def test_a_cancellation_still_needs_a_reason(app, client, login,
                                             order_with_contract):
    """The rule was in the route. Moving the work must not drop it."""
    from app.models.models import Contract

    login('admin')
    client.post(f"/contracts/{order_with_contract['contract_id']}/cancel",
                data={'canceled_reason': '   '}, follow_redirects=True)

    with app.app_context():
        assert Contract.query.get(
            order_with_contract['contract_id']).is_canceled is not True, (
            'a contract was cancelled with no reason given')


def test_a_signed_contract_still_cannot_be_cancelled(app, client, login,
                                                     order_with_contract):
    """`can_cancel()` refuses a signed contract; that must survive the move."""
    from app.config import db
    from app.models.models import Contract

    with app.app_context():
        contract = Contract.query.get(order_with_contract['contract_id'])
        contract.is_signed = True
        db.session.commit()

    login('admin')
    client.post(f"/contracts/{order_with_contract['contract_id']}/cancel",
                data={'canceled_reason': 'Doi y'}, follow_redirects=True)

    with app.app_context():
        assert Contract.query.get(
            order_with_contract['contract_id']).is_canceled is not True


def test_cancelling_an_order_goes_through_a_service(app, client, login,
                                                    order_with_contract):
    """`OrderService` had no cancel method at all; the route did the work.

    The reason matters more than the tidiness: an order carries paperwork, and
    whatever is decided about that paperwork on cancellation has to be decided
    in ONE place. A route cannot be that place, because the next way to cancel
    an order — an API, a bulk action, the approval queue — will not go through
    it.
    """
    from app.models import Order
    from app.services.services import OrderService

    assert hasattr(OrderService, 'cancel_order'), (
        'the route is still the only thing that knows how to cancel an order')

    login('admin')
    client.post(f"/orders/{order_with_contract['order_id']}/cancel",
                data={'canceled_reason': 'Khach huy don'},
                follow_redirects=True)

    with app.app_context():
        order = Order.query.get(order_with_contract['order_id'])
        assert order.is_canceled is True
        assert order.canceled_reason == 'Khach huy don'


# --- the same defect, found in the sibling route nobody had posted to -------

@pytest.fixture()
def order_with_quotation(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus, Quotation

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-QCAN',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(
            order_id=order.id, quotation_created=True,
            quotation_created_at=dt.datetime(2026, 9, 1),
            quotation_approved=False))
        quotation = Quotation(
            company_id=seed['company_id'], order_id=order.id,
            quotation_number='BG-QCAN', quotation_date=dt.date(2026, 9, 1),
            total_amount=20_000_000, is_approved=False, is_active=True)
        db.session.add(quotation)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'quotation_id': str(quotation.id)}


def test_cancelling_the_only_quotation_lets_the_order_have_one_again(
        app, client, login, order_with_quotation):
    """`cancel_quotation` had the identical defect `cancel_contract` had.

    Found by covering a route nobody had ever posted to — which is the whole
    argument for T-19. The service cancelled the quotation and never touched
    the lifecycle, so the order went on saying it had a quotation, and an
    approved one at that, with nothing to show for it.
    """
    from app.models.models import Quotation

    login('admin')
    client.post(f"/quotations/{order_with_quotation['quotation_id']}/cancel",
                data={'reason': 'Khach doi yeu cau'}, follow_redirects=True)

    with app.app_context():
        assert Quotation.query.get(
            order_with_quotation['quotation_id']).is_canceled is True

    lifecycle = _lifecycle(app, order_with_quotation['order_id'])
    assert lifecycle.quotation_created is False, (
        'the order still believes it has a quotation')
    # Not asserting `quotation_approved` here: an APPROVED quotation cannot be
    # cancelled at all (`can_cancel()` refuses it, exactly as a signed
    # contract is refused), so there is no reachable path where that flag
    # needs rolling back. My first version of this test set the quotation
    # approved AND expected the cancel to work — two rules that cannot both
    # hold, which is how I noticed.


def test_a_second_active_quotation_keeps_the_flags(app, client, login,
                                                   order_with_quotation):
    """Recomputed from the data, not blindly cleared — as with contracts."""
    from app.config import db
    from app.models.models import Quotation

    with app.app_context():
        db.session.add(Quotation(
            company_id=order_with_quotation['company_id'],
            order_id=order_with_quotation['order_id'],
            quotation_number='BG-QCAN-2', quotation_date=dt.date(2026, 9, 3),
            total_amount=21_000_000, is_approved=False, is_active=True))
        db.session.commit()

    login('admin')
    client.post(f"/quotations/{order_with_quotation['quotation_id']}/cancel",
                data={'reason': 'Ban cu'}, follow_redirects=True)

    lifecycle = _lifecycle(app, order_with_quotation['order_id'])
    assert lifecycle.quotation_created is True, (
        'the order was told it has no quotation while an active one remains')
