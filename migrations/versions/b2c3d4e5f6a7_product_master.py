"""product master (F11 phase 1)

Adds the `products` table. PURELY ADDITIVE: nothing writes through it yet and
no existing column changes, so this revision is safe to apply and to roll back
on a live database.

Background: the app has never had a product entity. Document line items carry
free-text names and `material_norms.product_key` matches a lowercased version
of one, so renaming a product silently breaks its material norms. Phase 1
introduces the table plus a reconciliation report over the names already in
use; phase 2 points documents and norms at `product_id` once the owner has
reviewed that report.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'products',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('product_code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('match_key', sa.String(length=255), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('default_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True,
                  server_default='manual'),
        sa.Column('is_active', sa.Boolean(), nullable=True,
                  server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.UniqueConstraint('company_id', 'product_code',
                            name='uq_company_product_code'),
        sa.UniqueConstraint('company_id', 'match_key',
                            name='uq_company_product_match_key'),
    )
    op.create_index('ix_products_company_id', 'products', ['company_id'])
    op.create_index('ix_products_match_key', 'products', ['match_key'])
    op.create_index('ix_products_is_active', 'products', ['is_active'])


def downgrade() -> None:
    op.drop_index('ix_products_is_active', table_name='products')
    op.drop_index('ix_products_match_key', table_name='products')
    op.drop_index('ix_products_company_id', table_name='products')
    op.drop_table('products')
