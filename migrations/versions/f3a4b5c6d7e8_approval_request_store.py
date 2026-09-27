"""approval_requests.store_id — which branch asked

A branch manager decides their own branch's work. The queue therefore has to
be filterable by branch, and `approval_requests` carried only `company_id`.

The column is stamped when a request is raised. Existing rows are backfilled
from their target document's order, which is the only place the information
exists for them.

Backfill limits, stated rather than hidden:

- Only `payment.*` actions can be backfilled, because those are the only
  actions `PERFORMERS` has ever contained, so they are the only rows that can
  exist. If an unknown action turns up the migration leaves its store_id NULL
  rather than guessing.
- A row whose payment or order has since been deleted keeps NULL. An old row
  that cannot be filtered is better than a migration that fails on a tenant
  with tidied-up data.

NULL therefore means "unknown branch", and the queue shows those to company
admins only — the person above the branches, who is the right fallback reader.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.models import GUID

revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('approval_requests') as batch:
        batch.add_column(sa.Column('store_id', GUID(), nullable=True))
        batch.create_index('ix_approval_requests_store_id', ['store_id'])

    connection = op.get_bind()

    before = connection.execute(
        sa.text('SELECT COUNT(*) FROM approval_requests')).scalar()

    connection.execute(sa.text("""
        UPDATE approval_requests
           SET store_id = (
               SELECT o.store_id
                 FROM payment_reports p
                 JOIN orders o ON o.id = p.order_id
                WHERE p.id = approval_requests.target_id)
         WHERE action LIKE 'payment.%'
    """))

    after = connection.execute(
        sa.text('SELECT COUNT(*) FROM approval_requests')).scalar()
    assert before == after, (
        f'the backfill changed the number of approval requests '
        f'({before} -> {after}); it must only fill a column')

    unfilled = connection.execute(sa.text(
        'SELECT COUNT(*) FROM approval_requests WHERE store_id IS NULL'
    )).scalar()
    if unfilled:
        print(f'  {unfilled} approval request(s) could not be traced to a '
              f'branch; they stay visible to company admins')


def downgrade() -> None:
    with op.batch_alter_table('approval_requests') as batch:
        batch.drop_index('ix_approval_requests_store_id')
        batch.drop_column('store_id')
