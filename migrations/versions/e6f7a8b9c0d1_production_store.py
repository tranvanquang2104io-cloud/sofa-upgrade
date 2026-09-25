"""A production plan says where the work happens.

The service read `plan.order.store_id` — the branch the CUSTOMER bought at —
and used it as the place the sofa is built, in three spots: the stock column on
the plan screen, the availability check before issuing, and the deduction. With
one address the two are the same row and nothing is visible. With two it is
simply wrong: a customer ordering at the Nguyễn Trãi showroom does not mean the
work happens at Nguyễn Trãi, and material would be checked against a showroom
that holds none.

Left NULL for every existing plan, deliberately. NULL means "the same place it
was sold", which is exactly what the code assumed before the column existed, so
nothing moves for anybody: `production_site_of()` falls back to the order's
branch. Backfilling the value instead would have written the assumption into
the data, where the next person could not tell a considered choice from an
inherited default.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('production_plans') as batch:
        batch.add_column(sa.Column('production_store_id',
                                   sa.String(length=36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('production_plans') as batch:
        batch.drop_column('production_store_id')
