"""Every change to stock leaves a line saying what happened and why.

`material_stock.current_quantity` is a bare number. When it is wrong — and with
more than one warehouse it will be — there is nothing to look at. Nobody can
say whether 3m is what a job left behind, what arrived short, or what somebody
typed by hand on a Tuesday.

A new table only; no existing data moves and nothing is backfilled. Movements
before today do not exist and inventing them would be worse than their absence:
a history that looks complete and is not would be trusted, and a reader could
not tell the invented lines from the recorded ones. The account starts now and
says so by being empty before now.

Nothing derives stock from this table. `current_quantity` stays authoritative —
summing movements to read a balance would turn a fast read into a scan, and
make a missing movement corrupt the stock figure rather than just the
explanation of it.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_movements',
        sa.Column('id', app.models.types.GUID(), primary_key=True),
        sa.Column('company_id', app.models.types.GUID(),
                  sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('material_id', app.models.types.GUID(),
                  sa.ForeignKey('materials.id'), nullable=False, index=True),
        sa.Column('store_id', app.models.types.GUID(), sa.ForeignKey('stores.id'),
                  index=True),
        sa.Column('warehouse_id', app.models.types.GUID(),
                  sa.ForeignKey('warehouses.id'), index=True),
        sa.Column('quantity', sa.Numeric(15, 2), nullable=False),
        sa.Column('movement_type', sa.String(length=20), nullable=False,
                  index=True),
        sa.Column('ref_type', sa.String(length=30)),
        sa.Column('ref_id', app.models.types.GUID(), index=True),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), index=True),
        sa.Column('created_by_id', app.models.types.GUID(),
                  sa.ForeignKey('users.id')),
    )


def downgrade() -> None:
    """Dropping this loses the history and no stock.

    Safe in a way the warehouse migration was not: nothing reads a balance from
    here, so removing it takes away the explanation and leaves every quantity
    exactly where it was.
    """
    op.drop_table('stock_movements')
