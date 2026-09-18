"""material moving-average cost

Adds `materials.avg_cost`, updated on every goods receipt.

Without it the system could see what a bespoke job SOLD for but not what it
COST: material issues are already tracked per production plan
(`production_material_lines.quantity_issued`), they simply had no price
attached. In a bespoke business there is no catalogue price to compare
against, so this is the only way to tell whether a job made money.

Existing rows default to 0, which reads as "not yet known" rather than
"free" — the cost report counts and reports unpriced lines instead of
presenting a total that quietly omits them. Costs fill in naturally as goods
are received from now on.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('materials') as batch:
        batch.add_column(sa.Column('avg_cost', sa.Numeric(15, 2),
                                   nullable=True, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('materials') as batch:
        batch.drop_column('avg_cost')
