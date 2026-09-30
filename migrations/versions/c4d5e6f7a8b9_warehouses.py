"""Separate the warehouse from the branch, without anybody re-keying stock.

A `Store` has been playing three parts at once — the shop, the workshop and the
warehouse — and `material_stock` hung off it, with a NULL `store_id` row
standing for "the company's main warehouse". That describes a company with one
address. It stops describing anything with two: a production plan issued
material from the store on the CUSTOMER'S order, and where no row existed for
that store the code fell through to the company-level row. Stock moving between
locations with no document is what makes an inventory stop being trustworthy.

This migration creates one warehouse per existing location, moves every stock
row onto it, and leaves the QUANTITIES UNTOUCHED. Nobody re-keys anything: a
company that opens the app afterwards sees the same numbers under a warehouse
named after the branch they already had.

Two decisions worth stating:

* **`warehouses.store_id` is NOT NULL.** The nullable company-level row is
  precisely what the silent fallback reached for; removing the null removes the
  class of bug with it. Companies that had such rows get a warehouse named
  "Kho công ty" attached to their first location — which is what those rows
  always meant in practice.
* **The totals are asserted, not assumed.** Before and after, per material, the
  sum of `current_quantity` must be identical, and the migration raises if it
  is not. A data migration that moves inventory and checks nothing is the
  riskiest thing in this plan; `tests/test_migrations_run.py` exists because
  until now no migration in this repository was executed by the suite at all.

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-09-25
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _totals_by_material(connection):
    return dict(connection.execute(sa.text(
        'SELECT material_id, SUM(current_quantity) FROM material_stock '
        'GROUP BY material_id')).all())


def upgrade() -> None:
    op.create_table(
        'warehouses',
        sa.Column('id', app.models.types.GUID(), primary_key=True),
        sa.Column('company_id', app.models.types.GUID(),
                  sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('store_id', app.models.types.GUID(), sa.ForeignKey('stores.id'),
                  nullable=False, index=True),
        sa.Column('warehouse_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=True,
                  server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('company_id', 'warehouse_code',
                            name='uq_company_warehouse_code'),
    )

    with op.batch_alter_table('stores') as batch:
        batch.add_column(sa.Column('is_sales_site', sa.Boolean(),
                                   nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('is_production_site', sa.Boolean(),
                                   nullable=False, server_default=sa.true()))

    connection = op.get_bind()
    before = _totals_by_material(connection)

    with op.batch_alter_table('material_stock') as batch:
        batch.add_column(sa.Column('warehouse_id', app.models.types.GUID(),
                                   nullable=True))

    # TRUE/FALSE, not 1/0: PostgreSQL refuses an integer for a boolean column
    # (SQLite accepts both, which is why only a real QAS-like upgrade found it).
    # One warehouse per existing location, named after it.
    stores = connection.execute(sa.text(
        'SELECT id, company_id, store_code, name FROM stores')).all()
    for store_id, company_id, store_code, name in stores:
        warehouse_id = str(uuid.uuid4())
        connection.execute(sa.text(
            'INSERT INTO warehouses (id, company_id, store_id, '
            'warehouse_code, name, is_default, is_active) VALUES '
            '(:id, :company, :store, :code, :name, TRUE, TRUE)'),
            {'id': warehouse_id, 'company': company_id, 'store': store_id,
             'code': f'{store_code}-KHO', 'name': f'Kho {name}'})
        connection.execute(sa.text(
            'UPDATE material_stock SET warehouse_id = :warehouse '
            'WHERE store_id = :store'),
            {'warehouse': warehouse_id, 'store': store_id})

    # Rows that meant "the company's main warehouse" become a warehouse of
    # their own, attached to the company's first location. Created only where
    # such rows exist, so a company that never used them gains nothing to
    # explain.
    companies = connection.execute(sa.text(
        'SELECT DISTINCT company_id FROM material_stock '
        'WHERE store_id IS NULL')).all()
    for (company_id,) in companies:
        anchor = connection.execute(sa.text(
            'SELECT id FROM stores WHERE company_id = :company '
            'ORDER BY created_at LIMIT 1'), {'company': company_id}).first()
        if anchor is None:
            # A company with company-level stock and no location at all. Give
            # it one rather than dropping the stock on the floor.
            anchor_id = str(uuid.uuid4())
            connection.execute(sa.text(
                'INSERT INTO stores (id, company_id, store_code, name, '
                'is_active, is_sales_site, is_production_site) VALUES '
                '(:id, :company, :code, :name, TRUE, TRUE, TRUE)'),
                {'id': anchor_id, 'company': company_id, 'code': 'MAIN',
                 'name': 'Cơ sở chính'})
        else:
            anchor_id = anchor[0]

        warehouse_id = str(uuid.uuid4())
        connection.execute(sa.text(
            'INSERT INTO warehouses (id, company_id, store_id, '
            'warehouse_code, name, is_default, is_active) VALUES '
            '(:id, :company, :store, :code, :name, FALSE, TRUE)'),
            {'id': warehouse_id, 'company': company_id, 'store': anchor_id,
             'code': 'KHO-CT', 'name': 'Kho công ty'})
        connection.execute(sa.text(
            'UPDATE material_stock SET warehouse_id = :warehouse '
            'WHERE company_id = :company AND store_id IS NULL'),
            {'warehouse': warehouse_id, 'company': company_id})

    orphans = connection.execute(sa.text(
        'SELECT COUNT(*) FROM material_stock WHERE warehouse_id IS NULL')
    ).scalar()
    if orphans:
        raise RuntimeError(
            f'{orphans} stock rows could not be placed in a warehouse; '
            'refusing rather than leaving them unreachable')

    after = _totals_by_material(connection)
    if before != after:
        raise RuntimeError(
            'stock totals changed during the warehouse migration: '
            f'{before} -> {after}')


def downgrade() -> None:
    """Back to stock hanging off the location.

    Safe because the move preserved `store_id` on every row: going back only
    drops the column that pointed at the warehouse. Quantities are untouched in
    both directions.
    """
    with op.batch_alter_table('material_stock') as batch:
        batch.drop_column('warehouse_id')
    with op.batch_alter_table('stores') as batch:
        batch.drop_column('is_production_site')
        batch.drop_column('is_sales_site')
    op.drop_table('warehouses')
