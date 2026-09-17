"""HĐNT master agreements + ĐƠN ĐẶT HÀNG release orders

Adds `master_agreements` (framework agreement with a customer),
`master_agreement_price_lines` (agreed prices with line-level validity) and
`order_confirmations` (the per-order document issued under an agreement,
occupying the same lifecycle slot as a Contract).

Pure addition. An order whose customer has no active agreement keeps
producing an ordinary Contract, so no historical data needs migrating.

Revision ID: e9f0a1b2c3d4
Revises: d8e9f0a1b2c3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = 'e9f0a1b2c3d4'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'master_agreements',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('customer_id', GUID(), nullable=False),
        sa.Column('agreement_number', sa.String(length=50), nullable=False),
        sa.Column('signed_date', sa.Date(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('auto_renew', sa.Boolean(), nullable=True,
                  server_default=sa.false()),
        sa.Column('renewal_notice_days', sa.Integer(), nullable=True,
                  server_default='30'),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='draft'),
        sa.Column('commitment_type', sa.String(length=16), nullable=True,
                  server_default='none'),
        sa.Column('target_value', sa.Numeric(15, 2), nullable=True),
        sa.Column('target_quantity', sa.Numeric(15, 2), nullable=True),
        sa.Column('scope_description', sa.Text(), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('quality_terms', sa.Text(), nullable=True),
        sa.Column('delivery_terms', sa.Text(), nullable=True),
        sa.Column('penalty_pct', sa.Numeric(5, 2), nullable=True,
                  server_default='8.00'),
        sa.Column('penalty_basis_note', sa.String(length=255), nullable=True),
        sa.Column('dispute_resolution', sa.Text(), nullable=True),
        sa.Column('seller_representative', sa.String(length=255), nullable=True),
        sa.Column('seller_representative_title', sa.String(length=100),
                  nullable=True),
        sa.Column('buyer_representative', sa.String(length=255), nullable=True),
        sa.Column('buyer_representative_title', sa.String(length=100),
                  nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True,
                  server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.UniqueConstraint('company_id', 'agreement_number',
                            name='uq_company_agreement_number'),
    )
    op.create_index('ix_master_agreements_company_id', 'master_agreements',
                    ['company_id'])
    op.create_index('ix_master_agreements_customer_id', 'master_agreements',
                    ['customer_id'])
    op.create_index('ix_master_agreements_status', 'master_agreements',
                    ['status'])
    op.create_index('ix_master_agreements_customer_status',
                    'master_agreements', ['customer_id', 'status'])

    op.create_table(
        'master_agreement_price_lines',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('agreement_id', GUID(), nullable=False),
        sa.Column('product_key', sa.String(length=255), nullable=False),
        sa.Column('product_name', sa.String(length=255), nullable=True),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('agreed_unit_price', sa.Numeric(15, 2), nullable=True),
        sa.Column('discount_pct', sa.Numeric(5, 2), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agreement_id'], ['master_agreements.id'], ),
    )
    op.create_index('ix_map_lines_agreement_id',
                    'master_agreement_price_lines', ['agreement_id'])

    op.create_table(
        'order_confirmations',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('master_agreement_id', GUID(), nullable=False),
        sa.Column('quotation_id', GUID(), nullable=True),
        sa.Column('confirmation_number', sa.String(length=50), nullable=False),
        sa.Column('confirmation_date', sa.Date(), nullable=False),
        sa.Column('cited_agreement_number', sa.String(length=50), nullable=True),
        sa.Column('cited_agreement_date', sa.Date(), nullable=True),
        sa.Column('items', sa.JSON(), nullable=True),
        sa.Column('subtotal', sa.Numeric(15, 2), nullable=True,
                  server_default='0'),
        sa.Column('vat_rate', sa.Numeric(5, 2), nullable=True,
                  server_default='8.00'),
        sa.Column('vat_amount', sa.Numeric(15, 2), nullable=True,
                  server_default='0'),
        sa.Column('shipping_fee', sa.Numeric(15, 2), nullable=True,
                  server_default='0'),
        sa.Column('another_fee', sa.Numeric(15, 2), nullable=True,
                  server_default='0'),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=True,
                  server_default='0'),
        sa.Column('amount_in_words', sa.String(length=500), nullable=True),
        sa.Column('delivery_date', sa.Date(), nullable=True),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='draft'),
        sa.Column('is_active', sa.Boolean(), nullable=True,
                  server_default=sa.true()),
        sa.Column('is_canceled', sa.Boolean(), nullable=True,
                  server_default=sa.false()),
        sa.Column('canceled_at', sa.DateTime(), nullable=True),
        sa.Column('canceled_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        *[sa.Column(f'extend{n:02d}', sa.Text(), nullable=True)
          for n in range(1, 11)],
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['master_agreement_id'],
                                ['master_agreements.id'], ),
        sa.ForeignKeyConstraint(['quotation_id'], ['quotations.id'], ),
        sa.UniqueConstraint('company_id', 'confirmation_number',
                            name='uq_company_confirmation_number'),
    )
    op.create_index('ix_order_confirmations_company_id', 'order_confirmations',
                    ['company_id'])
    op.create_index('ix_order_confirmations_order_id', 'order_confirmations',
                    ['order_id'])
    op.create_index('ix_order_confirmations_agreement_id',
                    'order_confirmations', ['master_agreement_id'])


def downgrade() -> None:
    op.drop_index('ix_order_confirmations_agreement_id',
                  table_name='order_confirmations')
    op.drop_index('ix_order_confirmations_order_id',
                  table_name='order_confirmations')
    op.drop_index('ix_order_confirmations_company_id',
                  table_name='order_confirmations')
    op.drop_table('order_confirmations')

    op.drop_index('ix_map_lines_agreement_id',
                  table_name='master_agreement_price_lines')
    op.drop_table('master_agreement_price_lines')

    op.drop_index('ix_master_agreements_customer_status',
                  table_name='master_agreements')
    op.drop_index('ix_master_agreements_status', table_name='master_agreements')
    op.drop_index('ix_master_agreements_customer_id',
                  table_name='master_agreements')
    op.drop_index('ix_master_agreements_company_id',
                  table_name='master_agreements')
    op.drop_table('master_agreements')
