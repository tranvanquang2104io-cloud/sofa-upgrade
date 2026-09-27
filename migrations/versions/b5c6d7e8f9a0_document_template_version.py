"""document_templates.version — replacing a template is an event, not an edit

Uploading a replacement deactivated the old row and inserted a new one. The
layout that printed the contract posted in March survived only as an inactive
row with nothing marking it as the one that did it.

A `Document` records `template_id`, so it always pointed at the right ROW — the
row simply had no identity a person could refer to, and nothing stopped its
file being swapped.

Backfill: existing rows are numbered per (company_id, document_type) in
`created_at` order, oldest = 1. That is the order they were uploaded in, which
is the only version history the data contains. Rows with no `created_at` sort
last and still get a number, because an unnumbered row would be invisible to
every screen that lists versions.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, Sequence[str], None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('document_templates') as batch:
        batch.add_column(sa.Column('version', sa.Integer(), nullable=False,
                                   server_default='1'))

    connection = op.get_bind()
    before = connection.execute(
        sa.text('SELECT COUNT(*) FROM document_templates')).scalar()

    rows = connection.execute(sa.text(
        'SELECT id, company_id, document_type, created_at '
        'FROM document_templates '
        'ORDER BY company_id, document_type, '
        '         created_at IS NULL, created_at, id'
    )).fetchall()

    counters = {}
    for row in rows:
        key = (str(row[1]), row[2])
        counters[key] = counters.get(key, 0) + 1
        connection.execute(
            sa.text('UPDATE document_templates SET version = :v '
                    'WHERE id = :id'),
            {'v': counters[key], 'id': row[0]})

    after = connection.execute(
        sa.text('SELECT COUNT(*) FROM document_templates')).scalar()
    assert before == after, (
        f'numbering changed the number of templates ({before} -> {after}); '
        f'it must only fill a column')

    unnumbered = connection.execute(sa.text(
        'SELECT COUNT(*) FROM document_templates WHERE version IS NULL '
        'OR version < 1')).scalar()
    assert not unnumbered, f'{unnumbered} template(s) ended up without a version'


def downgrade() -> None:
    with op.batch_alter_table('document_templates') as batch:
        batch.drop_column('version')
