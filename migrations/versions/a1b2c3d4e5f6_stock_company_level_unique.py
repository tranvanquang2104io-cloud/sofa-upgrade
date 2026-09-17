"""unique company-level stock row per material

`material_stock` already had UniqueConstraint(material_id, store_id), but
store_id is NULLable and SQL treats two NULLs as DISTINCT — so the constraint
never applied to company-level (main warehouse) rows and a material could hold
several of them. ProcurementService.receive() locates the row with .first(),
so duplicates make a goods receipt increment one row while a reader may see
another, with no error raised anywhere.

This adds a PARTIAL unique index covering store_id IS NULL (supported by both
PostgreSQL and SQLite).

DATA MERGE: any pre-existing duplicates must be consolidated first, or the
index cannot be created. Quantities are SUMMED into the earliest row — the
sum is the only defensible reading, since each duplicate was receiving real
stock movements. The merged rows' notes record what happened so the operation
is auditable rather than silent.

Revision ID: a1b2c3d4e5f6
Revises: f0a1b2c3d4e5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _merge_duplicate_company_level_rows(conn):
    """Consolidate duplicate store_id IS NULL rows, summing their quantities."""
    duplicates = conn.execute(sa.text(
        """
        SELECT material_id, COUNT(*) AS n
        FROM material_stock
        WHERE store_id IS NULL
        GROUP BY material_id
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    for material_id, _count in duplicates:
        rows = conn.execute(sa.text(
            """
            SELECT id, current_quantity
            FROM material_stock
            WHERE store_id IS NULL AND material_id = :mid
            ORDER BY created_at
            """
        ), {"mid": material_id}).fetchall()

        keep_id = rows[0][0]
        total = sum(float(r[1] or 0) for r in rows)
        drop_ids = [r[0] for r in rows[1:]]

        conn.execute(sa.text(
            """
            UPDATE material_stock
            SET current_quantity = :total,
                notes = COALESCE(notes, '') ||
                        ' [merged ' || :n || ' duplicate company-level rows]'
            WHERE id = :kid
            """
        ), {"total": total, "n": len(drop_ids), "kid": keep_id})

        for drop_id in drop_ids:
            conn.execute(sa.text("DELETE FROM material_stock WHERE id = :did"),
                         {"did": drop_id})


def upgrade() -> None:
    conn = op.get_bind()
    _merge_duplicate_company_level_rows(conn)

    op.create_index(
        'uq_material_stock_company_level',
        'material_stock',
        ['material_id'],
        unique=True,
        postgresql_where=sa.text('store_id IS NULL'),
        sqlite_where=sa.text('store_id IS NULL'),
    )


def downgrade() -> None:
    # Only the index is removed; the merged rows are NOT split back apart —
    # the original split was meaningless (the same material in the same
    # location) and the summed quantity is the correct total.
    op.drop_index('uq_material_stock_company_level', table_name='material_stock')
