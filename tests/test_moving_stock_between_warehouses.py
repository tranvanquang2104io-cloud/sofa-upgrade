"""Moving material between warehouses needs a document, not two hand edits.

The moment a company has a second warehouse, material ends up in the wrong one:
a delivery goes to the showroom because that is where the van could park, and
the job is at the workshop. Without a transfer, the only way to put it right is
`update_stock` twice — subtract here, add there — and that is two separate
hand-typed numbers with nothing tying them together. Two chances to mistype,
no record of why, and `avg_cost` is company-wide so nothing downstream notices
a discrepancy. An inventory loses its credibility within weeks of that becoming
routine.

One step, not two. No in-transit state, no approval: a motorbike carrying
fabric across Hà Nội takes twenty minutes, and modelling it as goods in flight
would be an accounting apparatus for a motorbike ride. If a workshop ever needs
to know what is on the road, that is a different feature and a real one — it is
not this.

What the document must guarantee:

* both sides move or neither does. A transfer that debits the source and fails
  before crediting the destination destroys stock, which is worse than the
  problem it was solving;
* it refuses to move more than is there. A negative quantity in a warehouse is
  not a small error — every screen downstream reads it as fact;
* the total across the company is unchanged. That is the invariant that makes
  a transfer a transfer rather than an adjustment.
"""
import datetime as dt

import pytest


@pytest.fixture()
def two_warehouses_with_stock(app, seed):
    from app.config import db
    from app.models import Store
    from app.models.models import Material, MaterialStock, Warehouse

    with app.app_context():
        workshop = Store(company_id=seed['company_id'], store_code='XUONG-T',
                         name='Xưởng Hoài Đức', is_active=True)
        db.session.add(workshop)
        db.session.flush()
        here = Warehouse(company_id=seed['company_id'],
                         store_id=seed['store_id'], warehouse_code='W-SR',
                         name='Kho showroom', is_default=True, is_active=True)
        there = Warehouse(company_id=seed['company_id'],
                          store_id=workshop.id, warehouse_code='W-XU',
                          name='Kho xưởng', is_default=True, is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-T', name='Vải bố',
                            is_active=True)
        db.session.add_all([here, there, material])
        db.session.flush()
        db.session.add_all([
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id, store_id=seed['store_id'],
                          current_quantity=50),
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id, store_id=workshop.id,
                          current_quantity=5),
        ])
        db.session.commit()
        return {**seed, 'workshop_id': str(workshop.id),
                'material_id': str(material.id),
                'from_warehouse_id': str(here.id),
                'to_warehouse_id': str(there.id)}


def _move(fixture, quantity, **kwargs):
    from app.services.transfers import transfer_stock

    return transfer_stock(
        company_id=fixture['company_id'],
        from_warehouse_id=fixture['from_warehouse_id'],
        to_warehouse_id=fixture['to_warehouse_id'],
        lines=[{'material_id': fixture['material_id'],
                'quantity': quantity, 'unit': 'm'}],
        transfer_date=dt.date(2026, 9, 26),
        **kwargs)


def test_a_transfer_moves_the_quantity(app, two_warehouses_with_stock):
    from app.models.models import MaterialStock

    with app.app_context():
        _move(two_warehouses_with_stock, 20)

        source = MaterialStock.query.filter_by(
            material_id=two_warehouses_with_stock['material_id'],
            store_id=two_warehouses_with_stock['store_id']).one()
        destination = MaterialStock.query.filter_by(
            material_id=two_warehouses_with_stock['material_id'],
            store_id=two_warehouses_with_stock['workshop_id']).one()
        assert float(source.current_quantity) == 30
        assert float(destination.current_quantity) == 25


def test_the_company_total_does_not_change(app, two_warehouses_with_stock):
    """The invariant that makes it a transfer and not an adjustment."""
    from app.models.models import Material

    with app.app_context():
        before = float(Material.query.get(
            two_warehouses_with_stock['material_id']).total_stock)
        _move(two_warehouses_with_stock, 20)
        after = float(Material.query.get(
            two_warehouses_with_stock['material_id']).total_stock)
        assert before == after == 55


def test_moving_more_than_is_there_is_refused(app, two_warehouses_with_stock):
    """A negative quantity is read as fact by every screen downstream."""
    from app.models.models import MaterialStock

    with app.app_context():
        with pytest.raises(ValueError):
            _move(two_warehouses_with_stock, 80)

        source = MaterialStock.query.filter_by(
            material_id=two_warehouses_with_stock['material_id'],
            store_id=two_warehouses_with_stock['store_id']).one()
        assert float(source.current_quantity) == 50, (
            'the refusal took the fabric anyway')


def test_a_refused_transfer_leaves_both_sides_alone(app,
                                                    two_warehouses_with_stock):
    """Both sides move or neither does.

    A transfer that debits the source and then fails destroys stock, which is
    worse than the problem it exists to solve. Two lines, the second
    impossible.
    """
    from app.config import db
    from app.models.models import Material, MaterialStock
    from app.services.transfers import transfer_stock

    with app.app_context():
        second = Material(company_id=two_warehouses_with_stock['company_id'],
                          material_code='MUT-T', name='Mút D40',
                          is_active=True)
        db.session.add(second)
        db.session.flush()
        db.session.add(MaterialStock(
            company_id=two_warehouses_with_stock['company_id'],
            material_id=second.id,
            store_id=two_warehouses_with_stock['store_id'],
            current_quantity=2))
        db.session.commit()

        with pytest.raises(ValueError):
            transfer_stock(
                company_id=two_warehouses_with_stock['company_id'],
                from_warehouse_id=two_warehouses_with_stock[
                    'from_warehouse_id'],
                to_warehouse_id=two_warehouses_with_stock['to_warehouse_id'],
                lines=[
                    {'material_id': two_warehouses_with_stock['material_id'],
                     'quantity': 10, 'unit': 'm'},
                    {'material_id': str(second.id), 'quantity': 9,
                     'unit': 'tấm'},          # only 2 are there
                ],
                transfer_date=dt.date(2026, 9, 26))

        fabric = MaterialStock.query.filter_by(
            material_id=two_warehouses_with_stock['material_id'],
            store_id=two_warehouses_with_stock['store_id']).one()
        assert float(fabric.current_quantity) == 50, (
            'the first line moved and the second failed, so 10m of fabric is '
            'now in neither warehouse')


def test_moving_to_the_same_warehouse_is_refused(app,
                                                 two_warehouses_with_stock):
    """Not pedantry: it would look like work and change nothing."""
    from app.services.transfers import transfer_stock

    with app.app_context():
        with pytest.raises(ValueError):
            transfer_stock(
                company_id=two_warehouses_with_stock['company_id'],
                from_warehouse_id=two_warehouses_with_stock[
                    'from_warehouse_id'],
                to_warehouse_id=two_warehouses_with_stock[
                    'from_warehouse_id'],
                lines=[{'material_id':
                        two_warehouses_with_stock['material_id'],
                        'quantity': 5, 'unit': 'm'}],
                transfer_date=dt.date(2026, 9, 26))


def test_a_warehouse_from_another_company_is_refused(app,
                                                     two_warehouses_with_stock):
    from app.config import db
    from app.models import Company, Store
    from app.models.models import Warehouse
    from app.services.transfers import transfer_stock

    with app.app_context():
        other = Company(company_code='OTHER-T', name='Xưởng khác',
                        email='o@t.test')
        db.session.add(other)
        db.session.flush()
        their_store = Store(company_id=other.id, store_code='S', name='Cơ sở',
                            is_active=True)
        db.session.add(their_store)
        db.session.flush()
        theirs = Warehouse(company_id=other.id, store_id=their_store.id,
                           warehouse_code='W-X', name='Kho của họ',
                           is_default=True, is_active=True)
        db.session.add(theirs)
        db.session.commit()

        with pytest.raises(ValueError):
            transfer_stock(
                company_id=two_warehouses_with_stock['company_id'],
                from_warehouse_id=two_warehouses_with_stock[
                    'from_warehouse_id'],
                to_warehouse_id=str(theirs.id),
                lines=[{'material_id':
                        two_warehouses_with_stock['material_id'],
                        'quantity': 5, 'unit': 'm'}],
                transfer_date=dt.date(2026, 9, 26))


def test_the_transfer_is_recorded_with_a_reason(app, two_warehouses_with_stock):
    """Two hand edits leave no record of why. A document is the point."""
    from app.models.models import StockTransfer

    with app.app_context():
        transfer = _move(two_warehouses_with_stock, 20,
                         notes='Chuyển sang xưởng để cắt đơn DH-2609')
        assert transfer.transfer_number, 'the transfer has no number'
        assert transfer.notes == 'Chuyển sang xưởng để cắt đơn DH-2609'
        assert StockTransfer.query.count() == 1
        assert len(transfer.lines) == 1
        assert float(transfer.lines[0].quantity) == 20


def test_the_transfer_screen_moves_stock(app, client, login,
                                         two_warehouses_with_stock):
    """Through the screen, because the service being right is not enough.

    Five times in this programme finished work sat unreachable. This posts the
    form a person would fill in.
    """
    from app.models.models import MaterialStock, StockTransfer

    login('admin')
    response = client.post('/warehouses/transfers/create', data={
        'from_warehouse_id': two_warehouses_with_stock['from_warehouse_id'],
        'to_warehouse_id': two_warehouses_with_stock['to_warehouse_id'],
        'transfer_date': '2026-09-26',
        'notes': 'Chuyển sang xưởng để cắt',
        'material_id[]': [two_warehouses_with_stock['material_id']],
        'quantity[]': ['20'],
    }, follow_redirects=True)
    assert response.status_code == 200

    with app.app_context():
        assert StockTransfer.query.count() == 1, (
            'the form did not reach the service')
        source = MaterialStock.query.filter_by(
            material_id=two_warehouses_with_stock['material_id'],
            store_id=two_warehouses_with_stock['store_id']).one()
        assert float(source.current_quantity) == 30


def test_a_refused_transfer_says_why_on_the_screen(app, client, login,
                                                   two_warehouses_with_stock):
    """A refusal with no reason is how people go back to editing by hand."""
    from app.models.models import StockTransfer

    login('admin')
    body = client.post('/warehouses/transfers/create', data={
        'from_warehouse_id': two_warehouses_with_stock['from_warehouse_id'],
        'to_warehouse_id': two_warehouses_with_stock['to_warehouse_id'],
        'transfer_date': '2026-09-26',
        'material_id[]': [two_warehouses_with_stock['material_id']],
        'quantity[]': ['80'],          # only 50 are there
    }, follow_redirects=True).get_data(as_text=True)

    assert 'không đủ' in body, (
        'the transfer was refused and the screen does not say what was short')
    with app.app_context():
        assert StockTransfer.query.count() == 0
