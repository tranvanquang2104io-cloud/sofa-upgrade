"""Four endpoints that change money, stock or permissions, never once posted to.

Measured against Flask's own route map rather than by grepping: of 77 POST
endpoints, 22 had never received a POST in any test. These four were picked
because of what they do, not to make a number go down —

  * skipping the advance means the company agrees to build before being paid;
  * setting stock by hand overrides what the shelves say;
  * deactivating a user is how somebody is locked out;
  * editing a user is how what they may do is decided.

Each asserts the CONSEQUENCE rather than the status code. A route that returns
302 and changes nothing passes a smoke test and fails the business.

(The first measurement said 26. It was wrong: the URL extractor broke on
f-strings containing quoted dict keys — `{d['contract_id']}` — so routes
tested earlier in this very session looked untested. Fixed to read braces
properly, which found four already covered. A measurement is a claim too.)
"""
import datetime as dt

import pytest


@pytest.fixture()
def signed_order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-POST',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-POST', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=0,
            is_signed=True, is_active=True))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_skipping_the_advance_records_who_and_why(app, client, login,
                                                  signed_order):
    """Agreeing to build before being paid is a decision, not a checkbox.

    The route says it records "an audited waiver first: who skipped the step,
    when, and why". Nothing had ever posted to it, so that claim had never
    been checked.
    """
    from app.models.models import LifecycleStatus, WorkflowWaiver

    login('admin')
    client.post(f"/order/{signed_order['order_id']}/skip-advance",
                data={'reason': 'Khach la moi quen, cho tra sau'},
                follow_redirects=True)

    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(
            order_id=signed_order['order_id']).first()
        assert lifecycle.advance_skipped is True, (
            'the advance was not skipped, so the order is stuck before '
            'handover with no way past it')

        waiver = WorkflowWaiver.query.filter_by(
            order_id=signed_order['order_id']).first()
        assert waiver is not None, (
            'the step was skipped and nothing recorded who decided to skip '
            'it — which is the whole point of the waiver')


def test_the_advance_cannot_be_skipped_before_the_contract_is_signed(
        app, client, login, seed):
    """Otherwise the order jumps to handover with nothing agreed at all."""
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-NOSIGN',
                      title='Sofa bang', total_amount=5_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()
        order_id = str(order.id)

    login('admin')
    client.post(f'/order/{order_id}/skip-advance',
                data={'reason': 'bo qua'}, follow_redirects=True)

    with app.app_context():
        lifecycle = LifecycleStatus.query.filter_by(order_id=order_id).first()
        assert lifecycle.advance_skipped is not True, (
            'the advance was skipped on an order with no signed contract')


def test_setting_stock_by_hand_through_the_screen_works_and_is_scoped(
        app, client, login, seed):
    """T-05 guarded the SERVICE. Nothing had ever posted to the route.

    A guard in a service that no test reaches through its own screen is a
    guard whose wiring is unproven.
    """
    from app.config import db
    from app.models.models import Material, MaterialStock

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-HAND', name='Vai dem tay',
                            is_active=True)
        db.session.add(material)
        db.session.commit()
        material_id = str(material.id)

    login('admin')
    client.post(f'/materials/{material_id}/stock',
                data={'store_id': seed['store_id'], 'quantity': '37'},
                follow_redirects=True)

    with app.app_context():
        row = MaterialStock.query.filter_by(material_id=material_id,
                                            store_id=seed['store_id']).first()
        assert row is not None and float(row.current_quantity) == 37, (
            'counting the shelves by hand did not reach the stock record')


def test_deactivating_a_user_actually_locks_them_out(app, client, login,
                                                     seed):
    """The consequence, not the redirect: they must not be able to log in."""
    from app.config import db
    from app.models.models import User

    with app.app_context():
        leaver = User(company_id=seed['company_id'], store_id=seed['store_id'],
                      username='nghiviec', email='nghiviec@acme.test',
                      full_name='Nguoi nghi viec', role='user',
                      is_active=True, allowed_features=['orders'])
        leaver.set_password('secret123')
        db.session.add(leaver)
        db.session.commit()
        leaver_id = str(leaver.id)

    login('admin')
    client.post(f'/users/{leaver_id}/deactivate', follow_redirects=True)

    with app.app_context():
        assert User.query.get(leaver_id).is_active is False

    # The part that matters: the door is actually shut.
    client.get('/auth/logout', follow_redirects=True)
    client.post('/auth/login', data={'email': 'nghiviec@acme.test',
                                     'password': 'secret123'},
                follow_redirects=True)
    with client.session_transaction() as session_data:
        assert 'user_id' not in session_data, (
            'a deactivated user could still log in, so deactivating somebody '
            'is a label rather than a lock')


def test_editing_a_users_features_changes_what_they_can_reach(app, client,
                                                              login, seed):
    """Permissions are only permissions if changing them changes access."""
    from app.models.models import User

    with app.app_context():
        staff_id = str(User.query.filter_by(username='staff').first().id)

    login('admin')
    client.post(f'/users/{staff_id}/edit', data={
        'full_name': 'Store Staff', 'role': 'user',
        'store_id': seed['store_id'], 'features': ['orders', 'inventory'],
    }, follow_redirects=True)

    with app.app_context():
        granted = set(User.query.get(staff_id).allowed_features or [])
        assert 'inventory' in granted, (
            'granting a feature through the edit screen did not grant it')

    client.get('/auth/logout', follow_redirects=True)
    login('staff')
    assert client.get('/materials/').status_code == 200, (
        'the feature was granted in the database but the user still cannot '
        'reach the screen it unlocks')
