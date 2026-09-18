"""document lifecycle status

Every regeneration writes a NEW file (the generated name carries a timestamp),
so one contract can own several document rows with nothing to say which is the
one to send the customer. This adds an explicit status.

Existing rows are backfilled as `current`, which is what they were. It also
gives a signing step somewhere to live later: `signed` sits on this same axis,
and a signed document is never superseded by a regeneration.

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.add_column(sa.Column('status', sa.String(length=16),
                                   nullable=False, server_default='current'))
        batch.add_column(sa.Column('superseded_at', sa.DateTime(),
                                   nullable=True))
    op.create_index('ix_documents_status', 'documents', ['status'])

    # Backfill: for each source document, everything but the newest file is
    # historical. Doing this here means the screen is immediately useful on
    # existing data rather than only for documents generated from now on.
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE documents
        SET status = 'superseded'
        WHERE id NOT IN (
            SELECT newest.id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY order_id, document_type,
                                        COALESCE(CAST(quotation_id AS CHAR(36)), ''),
                                        COALESCE(CAST(contract_id AS CHAR(36)), ''),
                                        COALESCE(CAST(handover_record_id AS CHAR(36)), ''),
                                        COALESCE(CAST(payment_report_id AS CHAR(36)), '')
                           ORDER BY generated_at DESC, created_at DESC
                       ) AS rn
                FROM documents
            ) AS newest
            WHERE newest.rn = 1
        )
    """))


def downgrade() -> None:
    op.drop_index('ix_documents_status', table_name='documents')
    with op.batch_alter_table('documents') as batch:
        batch.drop_column('superseded_at')
        batch.drop_column('status')
