"""A company records how far its books are closed.

Once a VAT return is filed — quarterly for a workshop this size — the figures
in it are a statement to the tax office. Editing a document dated inside that
period makes the system permanently disagree with what was declared, and Luật
Kế toán 2015 Đ.27 forbids erasing what a record said in any case: a correction
goes forward, as a new entry.

The column is nullable and starts empty for every existing company. Empty means
nobody has closed anything, so nothing changes until the person who files the
returns sets a date. A NOT NULL column with a default would have had to invent
a closing date for companies that never asked for one, and inventing it in
either direction is wrong — too early locks nothing, too late locks records
people are still working on.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-09-25
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('companies') as batch:
        batch.add_column(sa.Column('books_closed_through', sa.Date(),
                                   nullable=True))


def downgrade() -> None:
    """Dropping this loses which periods were declared closed.

    Unlike the document migration next to this one, refusing is not right here:
    the column holds a setting, not anybody's records, and a company that rolls
    back simply returns to the state it was in before — nothing is locked, and
    no document is lost. The cost is that whoever files the returns has to
    enter the date again.
    """
    with op.batch_alter_table('companies') as batch:
        batch.drop_column('books_closed_through')
