"""Creating and retiring master data, through the screens, for the first time.

More of the 22 POST endpoints that had never received a POST. These are the
ones that bring a material, a warehouse or a supplier into existence and take
it back out again.

"Deactivate" is the interesting word. It is not delete — the rows stay, because
past documents point at them — so the only way to know it worked is to check
that the thing STOPS BEING OFFERED for new work while remaining readable on
the old. A test that asserts `is_active is False` proves a column changed; it
does not prove anybody was stopped from picking it tomorrow.

Also pinned here: `cancel_handover` deliberately does NOT revert the
lifecycle, and that is correct. Its two siblings (`cancel_quotation`,
`cancel_contract`) both had a real bug of exactly that shape, so the obvious
move was to "fix" this one to match. Checked instead: the only handover
lifecycle flag is `handover_confirmed`, and `can_cancel()` refuses a confirmed
handover, so cancelling can only happen when there is nothing to revert. The
comment in the service is right, and pattern-matching would have broken
working code.
"""
import datetime as dt

import pytest


def test_a_material_can_be_created_through_the_screen(app, client, login,
                                                      seed):
    from app.models.models import Material

    login('admin')
    client.post('/materials/create', data={
        'material_code': 'VAI-NEW', 'name': 'Vai nhung moi',
        'unit_price': '150000', 'min_stock_level': '20',
    }, follow_redirects=True)

    with app.app_context():
        made = Material.query.filter_by(material_code='VAI-NEW').first()
        assert made is not None, 'the create screen did not create a material'
        assert made.is_active is True
        assert float(made.min_stock_level) == 20


def test_a_deactivated_material_stops_being_offered(app, client, login, seed):
    """The consequence: it disappears from where people pick materials.

    Asserting the flag alone would prove a column changed, not that anybody
    was stopped from choosing it for tomorrow's work.
    """
    from app.config import db
    from app.models.models import Material

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-OLD', name='Vai ngung dung',
                            is_active=True)
        db.session.add(material)
        db.session.commit()
        material_id = str(material.id)

    login('admin')
    listing_before = client.get('/materials/').get_data(as_text=True)
    assert 'VAI-OLD' in listing_before

    client.post(f'/materials/{material_id}/deactivate', follow_redirects=True)

    with app.app_context():
        assert Material.query.get(material_id) is not None, (
            'the material was deleted rather than retired, so every document '
            'that referred to it now points at nothing')
        assert Material.query.get(material_id).is_active is False

    listing_after = client.get('/materials/').get_data(as_text=True)
    assert 'VAI-OLD' not in listing_after, (
        'a retired material is still offered in the materials list')


def test_a_warehouse_can_be_created_and_retired(app, client, login, seed):
    from app.models.models import Warehouse

    login('admin')
    client.post('/warehouses/create', data={
        'warehouse_code': 'KHO-NEW', 'name': 'Kho moi',
        'store_id': seed['store_id'],
    }, follow_redirects=True)

    with app.app_context():
        made = Warehouse.query.filter_by(warehouse_code='KHO-NEW').first()
        assert made is not None, 'the warehouse was not created'
        warehouse_id = str(made.id)

    client.post(f'/warehouses/{warehouse_id}/deactivate',
                follow_redirects=True)

    with app.app_context():
        assert Warehouse.query.get(warehouse_id).is_active is False


def test_a_retired_warehouse_cannot_receive_new_stock(app, client, login,
                                                      seed):
    """The point of retiring it. Otherwise it is a label on a row.

    `warehouses_of()` is what every screen offers and what `resolve()` picks
    a default from, so this is the check that matters.
    """
    from app.config import db
    from app.models.models import Warehouse
    from app.services.warehouses import warehouses_of

    with app.app_context():
        warehouse = Warehouse(company_id=seed['company_id'],
                              store_id=seed['store_id'],
                              warehouse_code='KHO-RET', name='Kho dong cua',
                              is_active=True)
        db.session.add(warehouse)
        db.session.commit()
        warehouse_id = str(warehouse.id)

    login('admin')
    client.post(f'/warehouses/{warehouse_id}/deactivate',
                follow_redirects=True)

    with app.app_context():
        offered = {str(w.id) for w in warehouses_of(seed['company_id'])}
        assert warehouse_id not in offered, (
            'a closed warehouse is still offered as somewhere to put goods')


def test_cancelling_an_unconfirmed_handover_leaves_the_lifecycle_alone(
        app, client, login, seed):
    """Deliberate, and correct — unlike its two siblings.

    `cancel_quotation` and `cancel_contract` both failed to put the lifecycle
    back, and both were real bugs. This one does not put it back either, and
    that is RIGHT: `handover_confirmed` is the only flag, and `can_cancel()`
    refuses a confirmed handover, so there is never anything to revert.

    Pinned so that nobody later "fixes" it into consistency with its siblings.
    """
    from app.config import db
    from app.models import Order
    from app.models.models import HandoverRecord, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HCAN',
                      title='Sofa goc L', total_amount=10_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       handover_confirmed=False))
        record = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-HCAN', report_date=dt.date(2026, 9, 1),
            handover_date=dt.date(2026, 9, 1), is_confirmed=False)
        db.session.add(record)
        db.session.commit()
        order_id, record_id = str(order.id), str(record.id)

    login('admin')
    client.post(f'/handover/{record_id}/cancel',
                data={'reason': 'Khach hoan lich'}, follow_redirects=True)

    with app.app_context():
        assert HandoverRecord.query.get(record_id).is_canceled is True
        lifecycle = LifecycleStatus.query.filter_by(order_id=order_id).first()
        assert lifecycle.handover_confirmed is not True, (
            'cancelling a handover marked the order as delivered')


def test_a_confirmed_handover_cannot_be_cancelled(app, client, login, seed):
    """Which is why there is never a lifecycle flag to put back."""
    from app.config import db
    from app.models import Order
    from app.models.models import HandoverRecord, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HDONE',
                      title='Sofa bang', total_amount=10_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       handover_confirmed=True))
        record = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-HDONE', report_date=dt.date(2026, 9, 1),
            handover_date=dt.date(2026, 9, 1), is_confirmed=True)
        db.session.add(record)
        db.session.commit()
        record_id = str(record.id)

    login('admin')
    client.post(f'/handover/{record_id}/cancel',
                data={'reason': 'Doi y'}, follow_redirects=True)

    with app.app_context():
        assert HandoverRecord.query.get(record_id).is_canceled is not True, (
            'a handover the customer had already signed for was cancelled')
