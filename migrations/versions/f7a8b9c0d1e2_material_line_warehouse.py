"""A material line says which warehouse it is drawn from.

The owner: "từng thành phần nguyên vật liệu trong đơn đó thì phải được chỉ định
lấy từ kho nào ra để trừ tồn kho". A plan built at the workshop may take its
fabric from the fabric store and its frames from the timber yard.

Left NULL for every existing line, like `production_store_id` before it. NULL
means "the plan's production site", which is what every line did before the
column existed, so nothing moves for anybody and a workshop that keeps
everything in one place never has to fill it in. Backfilling a value would
write today's assumption into the data, where nobody could later tell a
considered choice from an inherited default.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('production_material_lines') as batch:
        batch.add_column(sa.Column('warehouse_id', app.models.types.GUID(),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('production_material_lines') as batch:
        batch.drop_column('warehouse_id')
