"""Phiếu điều chuyển kho — moving material between warehouses.

The moment a company has a second warehouse, material ends up in the wrong one.
Without a transfer document the only correction is editing two quantities by
hand — subtract here, add there — which is two chances to mistype, no record of
why, and nothing downstream that can notice the two do not agree.

New tables only; nothing existing is touched and no data moves, so there is
nothing to assert about totals here. The invariant that matters lives in
`app/services/transfers.py` and is pinned by
`tests/test_moving_stock_between_warehouses.py`: every line is checked before
any line is touched, so a transfer never leaves stock in neither warehouse.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.models.types  # noqa: F401  (GUID: UUID on PostgreSQL, CHAR(36) elsewhere)

revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stock_transfers',
        sa.Column('id', app.models.types.GUID(), primary_key=True),
        sa.Column('company_id', app.models.types.GUID(),
                  sa.ForeignKey('companies.id'), nullable=False, index=True),
        sa.Column('from_warehouse_id', app.models.types.GUID(),
                  sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('to_warehouse_id', app.models.types.GUID(),
                  sa.ForeignKey('warehouses.id'), nullable=False, index=True),
        sa.Column('transfer_number', sa.String(length=50), nullable=False),
        sa.Column('transfer_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime()),
        sa.UniqueConstraint('company_id', 'transfer_number',
                            name='uq_company_transfer_number'),
    )
    op.create_table(
        'stock_transfer_lines',
        sa.Column('id', app.models.types.GUID(), primary_key=True),
        sa.Column('transfer_id', app.models.types.GUID(),
                  sa.ForeignKey('stock_transfers.id'), nullable=False,
                  index=True),
        sa.Column('material_id', app.models.types.GUID(),
                  sa.ForeignKey('materials.id'), nullable=False, index=True),
        sa.Column('quantity', sa.Numeric(15, 2), nullable=False,
                  server_default='0'),
        sa.Column('unit', sa.String(length=50)),
    )


def downgrade() -> None:
    op.drop_table('stock_transfer_lines')
    op.drop_table('stock_transfers')
