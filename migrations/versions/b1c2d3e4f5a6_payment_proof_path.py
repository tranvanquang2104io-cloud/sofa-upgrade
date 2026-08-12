"""payment report proof_path (received-payment proof upload)

Revision ID: b1c2d3e4f5a6
Revises: 9337d2190ede
Create Date: 2026-08-12 22:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.types  # noqa: F401  (GUID and other custom column types)


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = '9337d2190ede'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('payment_reports', schema=None) as batch_op:
        batch_op.add_column(sa.Column('proof_path', sa.String(length=300), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('payment_reports', schema=None) as batch_op:
        batch_op.drop_column('proof_path')
