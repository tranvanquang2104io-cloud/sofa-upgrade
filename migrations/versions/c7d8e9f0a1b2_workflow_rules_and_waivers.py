"""workflow rules + audited waivers

Introduces the configurable order-workflow engine: `workflow_rules` holds, per
company, the prerequisites of each workflow action; `workflow_waivers` records
audited bypasses of rules marked waivable (replacing the untracked
`lifecycle_statuses.advance_skipped` boolean, which is left in place for
backward compatibility).

No data is migrated and no existing column changes, so this revision is a
pure addition and fully reversible. Companies with no rows fall back to
`WorkflowService.DEFAULT_RULES`, which reproduces the previously hardcoded
behaviour — installing this migration changes nothing on its own.

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflow_rules',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('prerequisite', sa.String(length=64), nullable=False),
        sa.Column('mode', sa.String(length=16), nullable=False,
                  server_default='required'),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column('sort_order', sa.Integer(), nullable=True,
                  server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.UniqueConstraint('company_id', 'action', 'prerequisite',
                            name='uq_workflow_rule'),
    )
    op.create_index('ix_workflow_rules_company_id', 'workflow_rules',
                    ['company_id'])
    op.create_index('ix_workflow_rules_company_action', 'workflow_rules',
                    ['company_id', 'action'])

    op.create_table(
        'workflow_waivers',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('prerequisite', sa.String(length=64), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('waived_by_user_id', GUID(), nullable=True),
        sa.Column('waived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['waived_by_user_id'], ['users.id'], ),
    )
    op.create_index('ix_workflow_waivers_company_id', 'workflow_waivers',
                    ['company_id'])
    op.create_index('ix_workflow_waivers_order_id', 'workflow_waivers',
                    ['order_id'])
    op.create_index('ix_workflow_waivers_order_action', 'workflow_waivers',
                    ['order_id', 'action'])


def downgrade() -> None:
    op.drop_index('ix_workflow_waivers_order_action', table_name='workflow_waivers')
    op.drop_index('ix_workflow_waivers_order_id', table_name='workflow_waivers')
    op.drop_index('ix_workflow_waivers_company_id', table_name='workflow_waivers')
    op.drop_table('workflow_waivers')

    op.drop_index('ix_workflow_rules_company_action', table_name='workflow_rules')
    op.drop_index('ix_workflow_rules_company_id', table_name='workflow_rules')
    op.drop_table('workflow_rules')
