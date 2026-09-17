"""configurable data standardization rules

Adds `normalization_rules` (per company: entity, field, ordered primitive
list, auto/confirm mode) and `normalization_suggestions` (pending
confirm-mode changes awaiting a human decision).

Pure addition — no existing column or row is touched, and a company with no
rows is simply not normalized. Fully reversible.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'normalization_rules',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('field_name', sa.String(length=64), nullable=False),
        sa.Column('primitives', sa.JSON(), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False,
                  server_default='auto'),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.UniqueConstraint('company_id', 'entity_type', 'field_name',
                            name='uq_normalization_rule'),
    )
    op.create_index('ix_normalization_rules_company_id', 'normalization_rules',
                    ['company_id'])
    op.create_index('ix_normalization_rules_company_entity',
                    'normalization_rules', ['company_id', 'entity_type'])

    op.create_table(
        'normalization_suggestions',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('entity_id', GUID(), nullable=False),
        sa.Column('field_name', sa.String(length=64), nullable=False),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('suggested_value', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
    )
    op.create_index('ix_normalization_suggestions_company_id',
                    'normalization_suggestions', ['company_id'])
    op.create_index('ix_norm_suggestions_entity', 'normalization_suggestions',
                    ['entity_type', 'entity_id'])


def downgrade() -> None:
    op.drop_index('ix_norm_suggestions_entity',
                  table_name='normalization_suggestions')
    op.drop_index('ix_normalization_suggestions_company_id',
                  table_name='normalization_suggestions')
    op.drop_table('normalization_suggestions')

    op.drop_index('ix_normalization_rules_company_entity',
                  table_name='normalization_rules')
    op.drop_index('ix_normalization_rules_company_id',
                  table_name='normalization_rules')
    op.drop_table('normalization_rules')
