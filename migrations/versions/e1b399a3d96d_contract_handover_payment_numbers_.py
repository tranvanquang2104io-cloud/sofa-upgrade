"""contract/handover/payment numbers unique per order (W6b)

Revision ID: e1b399a3d96d
Revises: acb618e15b19
Create Date: 2026-07-26 00:30:49.047907

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.types  # noqa: F401  (GUID and other custom column types)


# revision identifiers, used by Alembic.
revision: str = 'e1b399a3d96d'
down_revision: Union[str, Sequence[str], None] = 'acb618e15b19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, number column, old global constraint name, new composite constraint name)
_SWAPS = [
    ('contracts', 'contract_number', 'contracts_contract_number_key', 'uq_order_contract_number'),
    ('handover_records', 'report_number', 'handover_records_report_number_key', 'uq_order_handover_report_number'),
    ('payment_reports', 'report_number', 'payment_reports_report_number_key', 'uq_order_payment_report_number'),
]


def upgrade() -> None:
    """Swap GLOBAL unique on each document number for a per-order unique
    (order_id, number). The old global constraint blocked different tenants from
    reusing a number (AUDIT W6b/B3). No data is deleted."""
    bind = op.get_bind()
    for table, col, old_name, new_name in _SWAPS:
        if bind.dialect.name == 'postgresql':
            op.drop_constraint(old_name, table, type_='unique')
            op.create_unique_constraint(new_name, table, ['order_id', col])
        else:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.create_unique_constraint(new_name, ['order_id', col])


def downgrade() -> None:
    """Restore the global unique on each document number."""
    bind = op.get_bind()
    for table, col, old_name, new_name in _SWAPS:
        if bind.dialect.name == 'postgresql':
            op.drop_constraint(new_name, table, type_='unique')
            op.create_unique_constraint(old_name, table, [col])
        else:
            with op.batch_alter_table(table, schema=None) as batch_op:
                batch_op.drop_constraint(new_name, type_='unique')
