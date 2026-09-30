"""A goods receipt records which warehouse the delivery went into.

`goods_receipts.store_id` says which branch took delivery. That was the whole
answer while a branch and a warehouse were the same thing. They are not any
more: a branch may hold a fabric store and a timber store, and a workshop may
draw from a warehouse at another address entirely. Without the column, a
receipt cannot say where the goods physically went, and the stock row it
increments becomes the only record of it — a fact with no document behind it.

Backfilled from the branch's own default warehouse, which is exactly what every
existing receipt meant. Nullable, because a receipt raised before any warehouse
existed has no honest answer and inventing one would be worse than admitting
it: the reading code falls back to the branch, as it does today.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('goods_receipts') as batch:
        batch.add_column(sa.Column('warehouse_id', app.models.types.GUID(),
                                   nullable=True))
    with op.batch_alter_table('purchase_orders') as batch:
        batch.add_column(sa.Column('warehouse_id', app.models.types.GUID(),
                                   nullable=True))

    connection = op.get_bind()
    # Every existing receipt went into the default warehouse of the branch that
    # took it — that is what "store_id" meant before warehouses existed.
    connection.execute(sa.text(
        'UPDATE goods_receipts SET warehouse_id = ('
        '  SELECT w.id FROM warehouses w'
        '  WHERE w.store_id = goods_receipts.store_id'
        '  ORDER BY w.is_default DESC, w.warehouse_code LIMIT 1'
        ') WHERE store_id IS NOT NULL'))
    connection.execute(sa.text(
        'UPDATE purchase_orders SET warehouse_id = ('
        '  SELECT w.id FROM warehouses w'
        '  WHERE w.store_id = purchase_orders.store_id'
        '  ORDER BY w.is_default DESC, w.warehouse_code LIMIT 1'
        ') WHERE store_id IS NOT NULL'))


def downgrade() -> None:
    with op.batch_alter_table('purchase_orders') as batch:
        batch.drop_column('warehouse_id')
    with op.batch_alter_table('goods_receipts') as batch:
        batch.drop_column('warehouse_id')
