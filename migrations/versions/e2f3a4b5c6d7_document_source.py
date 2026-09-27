"""A printed document points at its source generically.

`documents` links back with one foreign key per document kind —
`quotation_id`, `contract_id`, `handover_record_id`, `payment_report_id`. Four
kinds, four columns. The framework agreement, the order confirmation, the
purchase order and the production plan have none, which is why printing them
records nothing and their screens show no history.

A column per kind does not survive the owner's plan: "sau này mở rộng thì sẽ
rất nhiều form in của rất nhiều loại chứng từ". Every new printable document
would be a migration, a model change, a relationship, and another branch
everywhere that asks what a file was printed from.

`source_type` + `source_id` makes a new kind a line of data instead — the
shape `approval_requests` and `stock_movements` already use here.

The four old columns are KEPT and back-filled from, not dropped. They are what
today's rows carry and what today's relationships read; replacing them in the
same migration that introduces their successor would be one change doing two
jobs, and the rollback would take the data with it. Dropping them is a later
migration, once nothing reads them.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BACKFILL = [
    ('quotation_id', 'quotation'),
    ('contract_id', 'contract'),
    ('handover_record_id', 'handover_record'),
    ('payment_report_id', 'payment_report'),
]


def upgrade() -> None:
    with op.batch_alter_table('documents') as batch:
        batch.add_column(sa.Column('source_type', sa.String(length=50),
                                   nullable=True))
        batch.add_column(sa.Column('source_id', sa.String(length=36),
                                   nullable=True))

    connection = op.get_bind()
    total = connection.execute(
        sa.text('SELECT COUNT(*) FROM documents')).scalar()

    for column, kind in BACKFILL:
        connection.execute(sa.text(
            f'UPDATE documents SET source_type = :kind, source_id = {column} '
            f'WHERE {column} IS NOT NULL AND source_type IS NULL'),
            {'kind': kind})

    # Every row is still here. This migration adds an address, it never
    # removes a document — and a document quietly lost is a file somebody
    # sent a customer that the system can no longer account for.
    after = connection.execute(
        sa.text('SELECT COUNT(*) FROM documents')).scalar()
    if total != after:
        raise RuntimeError(
            f'documents went from {total} to {after} during the source '
            'backfill')

    # A row that had a per-kind link must now have the generic pair too, or
    # the new lookup would show an empty history where the old one showed
    # files.
    orphans = connection.execute(sa.text(
        'SELECT COUNT(*) FROM documents WHERE source_type IS NULL AND ('
        'quotation_id IS NOT NULL OR contract_id IS NOT NULL OR '
        'handover_record_id IS NOT NULL OR payment_report_id IS NOT NULL)')
    ).scalar()
    if orphans:
        raise RuntimeError(
            f'{orphans} documents have a per-kind link and no source_type')


def downgrade() -> None:
    """Safe: the per-kind columns were never touched, only read."""
    with op.batch_alter_table('documents') as batch:
        batch.drop_column('source_id')
        batch.drop_column('source_type')
