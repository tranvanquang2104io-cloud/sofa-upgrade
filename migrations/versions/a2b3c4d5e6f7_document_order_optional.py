"""A printed document need not belong to an order.

`documents.order_id` was NOT NULL, which encoded the assumption that every
document the system prints is about one order. The framework agreement (HĐNT)
broke that: it is an agreement with a CUSTOMER, covering orders that do not
exist yet. Recording a printed HĐNT was therefore impossible — the insert failed
on the constraint — which is why the feature had a variable collector, a
template type and no way to produce anything.

Every document that does belong to an order still carries it; nothing about the
per-order file list changes. Only the requirement is lifted.

Revision ID: a2b3c4d5e6f7
Revises: d4e5f6a7b8c9
Create Date: 2026-09-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.alter_column('order_id', existing_type=sa.String(length=36),
                           nullable=True)


def downgrade() -> None:
    """Refuses if any document has no order, rather than destroying it.

    Going back means every row must have an order again. A HĐNT document has
    none and never can, so the honest failure is to stop and say so — deleting
    the customer's printed agreements to satisfy a constraint would be a far
    worse outcome than a failed downgrade.
    """
    connection = op.get_bind()
    orphans = connection.execute(
        sa.text('SELECT COUNT(*) FROM documents WHERE order_id IS NULL')
    ).scalar()
    if orphans:
        raise RuntimeError(
            f'{orphans} document(s) belong to no order (framework agreements). '
            'Reassign or remove them deliberately before downgrading.')

    with op.batch_alter_table('documents') as batch:
        batch.alter_column('order_id', existing_type=sa.String(length=36),
                           nullable=False)
