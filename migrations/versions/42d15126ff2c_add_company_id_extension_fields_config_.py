"""add company_id + extension fields + config table (NR3/D9)

Revision ID: 42d15126ff2c
Revises: 68c0ef8699e4
Create Date: 2026-07-26 08:57:59.546997

Adds, to each document table (quotations, contracts, handover_records,
payment_reports):
  * a NOT NULL ``company_id`` (backfilled from the row's order) and swaps the
    per-order unique document-number constraint for a per-company one (NR3/D8);
  * ten nullable ``extend01``..``extend10`` TEXT columns (D9).
Also creates ``extension_field_configs``.

No data is deleted. Reversible. PostgreSQL uses in-place ALTERs; SQLite uses
batch (table-rebuild). company_id is added nullable first and backfilled before
being made NOT NULL, so existing rows are preserved.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.types  # noqa: F401  (GUID and other custom column types)


revision: str = '42d15126ff2c'
down_revision: Union[str, Sequence[str], None] = '68c0ef8699e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, number column, old per-order unique, new per-company unique)
SPECS = [
    ('quotations', 'quotation_number', 'uq_order_quotation_number', 'uq_company_quotation_number'),
    ('contracts', 'contract_number', 'uq_order_contract_number', 'uq_company_contract_number'),
    ('handover_records', 'report_number', 'uq_order_handover_report_number', 'uq_company_handover_report_number'),
    ('payment_reports', 'report_number', 'uq_order_payment_report_number', 'uq_company_payment_report_number'),
]
EXTEND_KEYS = [f'extend{i:02d}' for i in range(1, 11)]


def upgrade() -> None:
    op.create_table(
        'extension_field_configs',
        sa.Column('id', app.models.types.GUID(), nullable=False),
        sa.Column('company_id', app.models.types.GUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=30), nullable=False),
        sa.Column('field_key', sa.String(length=20), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('data_type', sa.String(length=20), nullable=False),
        sa.Column('is_required', sa.Boolean(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'entity_type', 'field_key', name='uq_extfield_company_entity_key'),
    )
    op.create_index('ix_extension_field_configs_company_id', 'extension_field_configs', ['company_id'])

    is_pg = op.get_bind().dialect.name == 'postgresql'
    for table, num_col, old_uq, new_uq in SPECS:
        # 1. add extension columns + a NULLABLE company_id (plain ADD COLUMN works on both).
        for k in EXTEND_KEYS:
            op.add_column(table, sa.Column(k, sa.Text(), nullable=True))
        op.add_column(table, sa.Column('company_id', app.models.types.GUID(), nullable=True))
        # 2. backfill company_id from the row's order.
        op.execute(f"UPDATE {table} SET company_id = "
                   f"(SELECT o.company_id FROM orders o WHERE o.id = {table}.order_id)")
        # 3. make NOT NULL, swap the unique constraint, add index + FK.
        fk = f'fk_{table}_company_id'
        idx = f'ix_{table}_company_id'
        if is_pg:
            op.alter_column(table, 'company_id', nullable=False)
            op.drop_constraint(old_uq, table, type_='unique')
            op.create_unique_constraint(new_uq, table, ['company_id', num_col])
            op.create_index(idx, table, ['company_id'])
            op.create_foreign_key(fk, table, 'companies', ['company_id'], ['id'])
        else:
            with op.batch_alter_table(table, schema=None) as b:
                b.alter_column('company_id', existing_type=app.models.types.GUID(), nullable=False)
                b.drop_constraint(old_uq, type_='unique')
                b.create_unique_constraint(new_uq, ['company_id', num_col])
                b.create_index(idx, ['company_id'])
                b.create_foreign_key(fk, 'companies', ['company_id'], ['id'])


def downgrade() -> None:
    is_pg = op.get_bind().dialect.name == 'postgresql'
    for table, num_col, old_uq, new_uq in reversed(SPECS):
        fk = f'fk_{table}_company_id'
        idx = f'ix_{table}_company_id'
        if is_pg:
            op.drop_constraint(fk, table, type_='foreignkey')
            op.drop_constraint(new_uq, table, type_='unique')
            op.drop_index(idx, table_name=table)
            op.create_unique_constraint(old_uq, table, ['order_id', num_col])
            op.drop_column(table, 'company_id')
            for k in reversed(EXTEND_KEYS):
                op.drop_column(table, k)
        else:
            with op.batch_alter_table(table, schema=None) as b:
                b.drop_constraint(fk, type_='foreignkey')
                b.drop_constraint(new_uq, type_='unique')
                b.drop_index(idx)
                b.create_unique_constraint(old_uq, ['order_id', num_col])
                b.drop_column('company_id')
                for k in reversed(EXTEND_KEYS):
                    b.drop_column(k)

    op.drop_index('ix_extension_field_configs_company_id', table_name='extension_field_configs')
    op.drop_table('extension_field_configs')
