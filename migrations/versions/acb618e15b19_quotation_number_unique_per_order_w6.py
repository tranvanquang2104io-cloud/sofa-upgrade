"""quotation number unique per order (W6)

Revision ID: acb618e15b19
Revises: 2ede8fb2868b
Create Date: 2026-07-26 00:19:29.319008

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.types  # noqa: F401  (GUID and other custom column types)


# revision identifiers, used by Alembic.
revision: str = 'acb618e15b19'
down_revision: Union[str, Sequence[str], None] = '2ede8fb2868b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Swap the GLOBAL unique on quotation_number for a per-order unique
    (order_id, quotation_number). The old global constraint blocked different
    tenants from reusing a number (AUDIT W6/B3). No data is deleted.

    On PostgreSQL the old constraint is auto-named quotations_quotation_number_key.
    On SQLite it is an unnamed column-unique; the batch recreate below adds the new
    composite unique (fresh installs build from models and never carry the old one).
    """
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('quotations_quotation_number_key', 'quotations', type_='unique')
        op.create_unique_constraint(
            'uq_order_quotation_number', 'quotations',
            ['order_id', 'quotation_number'])
    else:
        with op.batch_alter_table('quotations', schema=None) as batch_op:
            batch_op.create_unique_constraint(
                'uq_order_quotation_number', ['order_id', 'quotation_number'])


def downgrade() -> None:
    """Restore the global unique on quotation_number."""
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('uq_order_quotation_number', 'quotations', type_='unique')
        op.create_unique_constraint(
            'quotations_quotation_number_key', 'quotations', ['quotation_number'])
    else:
        with op.batch_alter_table('quotations', schema=None) as batch_op:
            batch_op.drop_constraint('uq_order_quotation_number', type_='unique')
