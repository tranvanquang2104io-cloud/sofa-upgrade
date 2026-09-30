"""A clerk raises the request; the branch manager decides.

The owner's rule: only the person at the top of a branch may approve confirming
or cancelling money; everybody else raises the request.

Deliberately not a permission. A permission refuses and stops the work — a
clerk holding cash and a manager who is out have nothing they can record, and
the way round that is borrowing the manager's password, at which point the
control is theatre and the audit trail is a lie. A request lets the work
continue in the clerk's own name and moves only the decision.

New table only; nothing existing is touched. A company that never has a staff
user raise anything will never have a row here, and every screen behaves as it
did.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'approval_requests',
        sa.Column('id', app.models.types.GUID(), primary_key=True),
        sa.Column('company_id', app.models.types.GUID(),
                  sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('action', sa.String(length=50), nullable=False, index=True),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', app.models.types.GUID(), nullable=False,
                  index=True),
        sa.Column('reason', sa.Text()),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='pending', index=True),
        sa.Column('requested_by_id', app.models.types.GUID(),
                  sa.ForeignKey('users.id')),
        sa.Column('requested_at', sa.DateTime(), index=True),
        sa.Column('decided_by_id', app.models.types.GUID(),
                  sa.ForeignKey('users.id')),
        sa.Column('decided_at', sa.DateTime()),
        sa.Column('decision_note', sa.Text()),
    )


def downgrade() -> None:
    """Dropping this loses the record of who asked for what.

    It changes no document: an approved request already performed its action,
    and a pending one never did.
    """
    op.drop_table('approval_requests')
