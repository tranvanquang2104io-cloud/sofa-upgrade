"""Two clerks press save in the same second; the second one must not see an error.

Opened deliberately by T-03 and recorded as its own task rather than papered
over with a comment claiming it was handled.

`next_document_number` reads the highest number in use and adds one. Two
people reading at the same instant read the same number. The numbered tables
carry unique constraints, so THE DATA STAYS CORRECT — this was never a
silent-duplicate bug. What happens instead is that the second INSERT raises
IntegrityError and the second clerk gets an unexplained error page for an
action that worked a second ago, while the movement of stock they just made
physically is not recorded.

The fix is a retry, not a lock. Each company and document type has its own
sequence, real contention is rare, and a table lock would cost more than the
error it prevents.

Tested by making the collision happen deterministically rather than with
threads: take the number the next save is about to allocate, insert a row
holding it, then save. That is exactly the state the loser of a race finds,
and it does not depend on timing to reproduce.

What is NOT claimed: gapless numbering. A transaction that rolls back for any
other reason still consumes a number, exactly as a cancelled paper invoice
consumes one.
"""
import datetime as dt

import pytest


@pytest.fixture()
def warehouses(app, seed):
    from app.config import db
    from app.models.models import Material, MaterialStock, Warehouse

    with app.app_context():
        source = Warehouse(company_id=seed['company_id'],
                           store_id=seed['store_id'], warehouse_code='KHO-R1',
                           name='Kho 1', is_active=True)
        target = Warehouse(company_id=seed['company_id'],
                           store_id=seed['store_id'], warehouse_code='KHO-R2',
                           name='Kho 2', is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-RC', name='Vai',
                            is_active=True)
        db.session.add_all([source, target, material])
        db.session.flush()
        db.session.add(MaterialStock(material_id=material.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=1000))
        db.session.commit()
        return {**seed, 'source_id': str(source.id),
                'target_id': str(target.id),
                'material_id': str(material.id)}


def _transfer(warehouses, number=None):
    from app.services.transfers import transfer_stock

    return transfer_stock(
        company_id=warehouses['company_id'],
        from_warehouse_id=warehouses['source_id'],
        to_warehouse_id=warehouses['target_id'],
        lines=[{'material_id': warehouses['material_id'], 'quantity': 1}],
        transfer_date=dt.date(2026, 9, 1),
        transfer_number=number)


def test_the_second_save_gets_the_next_number_not_an_error(app, warehouses,
                                                          monkeypatch):
    """The exact state the loser of a race finds.

    My first version of this inserted the taken number and then saved — which
    is NOT the race. The second save recomputed the number, correctly got the
    next one, and the test passed with no retry implemented at all: green for
    the wrong reason, again.

    The real race is both parties computing the SAME number before either
    inserts. That is reproduced here by making the allocator hand back a
    stale number once, which is precisely what a concurrent read does.
    """
    import app.services.transfers as transfers
    from app.models.models import StockTransfer

    with app.app_context():
        _transfer(warehouses)          # somebody takes DC-0001

        stale = ['DC-0001']            # our read happened before they saved

        real_next_number = transfers._next_number

        def hands_back_a_stale_number(company_id):
            return stale.pop() if stale else real_next_number(company_id)

        monkeypatch.setattr(transfers, '_next_number',
                            hands_back_a_stale_number)

        mine = _transfer(warehouses)

        assert mine.transfer_number == 'DC-0002', (
            f'the loser of the race got {mine.transfer_number!r} instead of '
            f'the next free number')
        numbers = sorted(row.transfer_number for row in
                         StockTransfer.query.filter_by(
                             company_id=warehouses['company_id']).all())
        assert len(numbers) == len(set(numbers)), (
            f'two transfers share a number: {numbers}')


def test_an_explicitly_chosen_number_that_collides_still_refuses(app,
                                                                 warehouses):
    """A retry must not silently renumber what somebody typed.

    If a person entered DC-0007 by hand and it is taken, quietly saving it as
    DC-0008 puts a different number on the record from the one on the paper
    in their hand. The automatic number may move; a chosen one may not.
    """
    with app.app_context():
        _transfer(warehouses, number='DC-0007')

        with pytest.raises(Exception):
            _transfer(warehouses, number='DC-0007')


def test_the_ordinary_case_is_unaffected(app, warehouses):
    """A retry that changes the no-contention path is a retry that costs."""
    from app.models.models import StockTransfer

    with app.app_context():
        for _ in range(3):
            _transfer(warehouses)

        numbers = sorted(row.transfer_number for row in
                         StockTransfer.query.filter_by(
                             company_id=warehouses['company_id']).all())
        assert numbers == ['DC-0001', 'DC-0002', 'DC-0003'], numbers
