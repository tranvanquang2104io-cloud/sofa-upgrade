"""document_transitions — who did what to which document

The whole schema carried three `*_by_id` columns, two of them on
ApprovalRequest. Nothing recorded who signed a contract, who confirmed that
money had arrived, or who cancelled any of it. The owner asked for
maker-checker; this is the foundation it was missing.

One table rather than a pair of columns per document: five document types and
at least eight actions between them is sixteen migrations and sixteen places
to forget, and a document has MANY events rather than one — `signed_by` holds
the last signature and loses the fact that it was cancelled and re-signed.

No backfill. Nothing in the existing data says who did anything, so there is
nothing to move here, and inventing rows would put names against actions those
people may not have taken. The history starts empty and starts now; that is
honest and a backfill would not be.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.models import GUID

revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, Sequence[str], None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_transitions',
        sa.Column('id', GUID(), primary_key=True),
        sa.Column('company_id', GUID(), sa.ForeignKey('companies.id'),
                  nullable=False),
        sa.Column('document_type', sa.String(50), nullable=False),
        sa.Column('document_id', GUID(), nullable=False),
        sa.Column('action', sa.String(64), nullable=False),
        sa.Column('from_state', sa.String(64)),
        sa.Column('to_state', sa.String(64)),
        sa.Column('user_id', GUID(), sa.ForeignKey('users.id')),
        sa.Column('user_name', sa.String(255)),
        sa.Column('occurred_at', sa.DateTime()),
        sa.Column('reason', sa.Text()),
    )
    op.create_index('ix_document_transitions_company_id',
                    'document_transitions', ['company_id'])
    op.create_index('ix_document_transitions_document_type',
                    'document_transitions', ['document_type'])
    op.create_index('ix_document_transitions_document_id',
                    'document_transitions', ['document_id'])
    op.create_index('ix_document_transitions_action',
                    'document_transitions', ['action'])
    op.create_index('ix_document_transitions_user_id',
                    'document_transitions', ['user_id'])
    op.create_index('ix_document_transitions_occurred_at',
                    'document_transitions', ['occurred_at'])
    # The query this table exists to answer: one document's story.
    op.create_index('ix_document_transitions_document',
                    'document_transitions', ['document_type', 'document_id'])


def downgrade() -> None:
    op.drop_table('document_transitions')
