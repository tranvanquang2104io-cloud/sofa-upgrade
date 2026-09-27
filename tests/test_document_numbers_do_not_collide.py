"""A document number counted from the number of rows repeats itself.

`transfers.py:_next_number` was `COUNT(*) + 1`. I wrote it, in this refactor,
and it is wrong in a way that only shows up after the product has been used
for a while -- which is the worst kind, because the test that would have
caught it on day one is the one nobody writes.

Delete transfer DC-0002 out of three, and the next one is numbered DC-0003,
which already exists.

My first version of this docstring said the duplicate row simply saves. It
does not, and the test corrected me on the first run: `stock_transfers` has a
unique constraint on (company_id, transfer_number), so the insert raises
IntegrityError. The consequence is not a silent duplicate but a clerk who
cannot record a real movement of stock at all, with a 500 and no explanation
of why the same action worked yesterday. Worth knowing which of the two it is,
because they need different fixes.

The repo already had the right algorithm in the `next_code` API endpoint --
read the highest suffix actually in use and add one, scoped to the company,
parsed in Python so it works on SQLite as well as PostgreSQL. It had itself
been fixed twice for exactly the kind of defect this file is about. So this is
not new work; it is one implementation instead of two, with the wrong one
deleted.

What this deliberately does NOT do: make concurrent saves safe. Two clerks
pressing save in the same instant read the same highest number, and the second
insert hits the unique constraint. The constraint means the data stays correct
-- it is the retry that is missing, so one of them sees an error instead of
getting the next number. That is recorded as its own task rather than smuggled
in here, and not papered over with a comment claiming it is handled.
"""
import datetime as dt

import pytest


@pytest.fixture()
def warehouses(app, seed):
    from app.config import db
    from app.models.models import Material, MaterialStock, Warehouse

    with app.app_context():
        source = Warehouse(company_id=seed['company_id'],
                           store_id=seed['store_id'], warehouse_code='KHO-A',
                           name='Kho A', is_active=True)
        target = Warehouse(company_id=seed['company_id'],
                           store_id=seed['store_id'], warehouse_code='KHO-B',
                           name='Kho B', is_active=True)
        db.session.add_all([source, target])
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-T', name='Vai nhung',
                            is_active=True)
        db.session.add(material)
        db.session.flush()
        db.session.add(MaterialStock(material_id=material.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=1000))
        db.session.commit()
        return {**seed, 'source_id': str(source.id),
                'target_id': str(target.id),
                'material_id': str(material.id)}


def _numbers(app, company_id):
    from app.models.models import StockTransfer

    with app.app_context():
        return sorted(row.transfer_number for row in
                      StockTransfer.query.filter_by(
                          company_id=company_id).all())


def test_a_deleted_transfer_does_not_make_the_next_one_collide(app,
                                                               warehouses):
    """The failure `COUNT(*) + 1` produces, written as the sequence that hits it."""
    from app.config import db
    from app.models.models import StockTransfer
    from app.services.transfers import transfer_stock

    with app.app_context():
        for _ in range(3):
            transfer_stock(
                company_id=warehouses['company_id'],
                from_warehouse_id=warehouses['source_id'],
                to_warehouse_id=warehouses['target_id'],
                lines=[{'material_id': warehouses['material_id'],
                        'quantity': 1}],
                transfer_date=dt.date(2026, 9, 1))

        # Somebody voids the middle one. Nothing unusual: a transfer entered
        # against the wrong warehouse is exactly the thing that gets deleted.
        middle = StockTransfer.query.filter_by(
            transfer_number='DC-0002').first()
        assert middle is not None, 'numbering changed shape; update this test'
        db.session.delete(middle)
        db.session.commit()

        transfer_stock(
            company_id=warehouses['company_id'],
            from_warehouse_id=warehouses['source_id'],
            to_warehouse_id=warehouses['target_id'],
            lines=[{'material_id': warehouses['material_id'],
                    'quantity': 1}],
            transfer_date=dt.date(2026, 9, 1))

    numbers = _numbers(app, warehouses['company_id'])
    assert len(numbers) == len(set(numbers)), (
        f'two transfers share a number: {numbers}. A deleted row lowered the '
        f'count, so the next number was one already in use.')
    assert numbers == ['DC-0001', 'DC-0003', 'DC-0004'], numbers


def test_numbering_is_per_company(app, warehouses):
    """Another tenant's transfers must not push this tenant's numbers along."""
    from app.config import db
    from app.models.models import (
        Company, Material, MaterialStock, StockTransfer, Store, Warehouse,
    )
    from app.services.transfers import transfer_stock

    with app.app_context():
        other = Company(company_code='OTHER', name='Cong ty khac',
                        email='other@test', is_active=True)
        db.session.add(other)
        db.session.flush()
        store = Store(company_id=other.id, store_code='CH-X', name='CH X',
                      is_active=True)
        db.session.add(store)
        db.session.flush()
        for code in ('KHO-X', 'KHO-Y'):
            db.session.add(Warehouse(company_id=other.id, store_id=store.id,
                                     warehouse_code=code, name=code,
                                     is_active=True))
        material = Material(company_id=other.id, material_code='VAI-X',
                            name='Vai khac', is_active=True)
        db.session.add(material)
        db.session.flush()
        db.session.add(MaterialStock(material_id=material.id,
                                     company_id=other.id, store_id=store.id,
                                     current_quantity=100))
        db.session.commit()

        far = Warehouse.query.filter_by(company_id=other.id).all()
        for _ in range(4):
            transfer_stock(company_id=str(other.id),
                           from_warehouse_id=str(far[0].id),
                           to_warehouse_id=str(far[1].id),
                           lines=[{'material_id': str(material.id),
                                   'quantity': 1}],
                           transfer_date=dt.date(2026, 9, 1))

        transfer_stock(
            company_id=warehouses['company_id'],
            from_warehouse_id=warehouses['source_id'],
            to_warehouse_id=warehouses['target_id'],
            lines=[{'material_id': warehouses['material_id'],
                    'quantity': 1}],
            transfer_date=dt.date(2026, 9, 1))

        mine = StockTransfer.query.filter_by(
            company_id=warehouses['company_id']).all()
        assert [row.transfer_number for row in mine] == ['DC-0001'], (
            "another tenant's four transfers moved this tenant's first one "
            'along; the numbering is not company-scoped')


def test_a_number_that_is_not_a_plain_integer_is_skipped_not_crashed(
        app, warehouses):
    """Real data has hand-typed numbers in it.

    The shared helper reads the suffix and ignores anything that is not
    digits, rather than raising. A migration from a spreadsheet is the normal
    way these tables get their first few hundred rows.
    """
    from app.config import db
    from app.models.models import StockTransfer
    from app.services.numbering import next_document_number

    with app.app_context():
        db.session.add(StockTransfer(
            company_id=warehouses['company_id'],
            from_warehouse_id=warehouses['source_id'],
            to_warehouse_id=warehouses['target_id'],
            transfer_date=dt.date(2026, 9, 1),
            transfer_number='DC-CU/2024'))
        db.session.commit()

        assert next_document_number(
            StockTransfer, 'transfer_number', 'DC-',
            warehouses['company_id'], width=4) == 'DC-0001'
