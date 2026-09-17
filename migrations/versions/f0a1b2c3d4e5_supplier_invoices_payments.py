"""supplier invoices + payments (close the P2P loop)

Adds `supplier_invoices`, `supplier_invoice_lines`, `supplier_payments` and
`supplier_payment_allocations`, plus `purchase_order_lines.quantity_invoiced`
— the third leg of the 3-way match (ordered / received / invoiced).

The new counter defaults to 0 for existing rows, which is correct: nothing
recorded before this revision had been invoiced through the system.

Revision ID: f0a1b2c3d4e5
Revises: e9f0a1b2c3d4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models.types import GUID

revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e9f0a1b2c3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('purchase_order_lines') as batch:
        batch.add_column(sa.Column('quantity_invoiced', sa.Numeric(15, 2),
                                   nullable=False, server_default='0'))

    op.create_table(
        'supplier_invoices',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('supplier_id', GUID(), nullable=False),
        sa.Column('po_id', GUID(), nullable=False),
        sa.Column('invoice_series', sa.String(length=20), nullable=True),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('invoice_date', sa.Date(), nullable=False),
        sa.Column('seller_tax_code', sa.String(length=50), nullable=True),
        sa.Column('subtotal', sa.Numeric(15, 2), nullable=True, server_default='0'),
        sa.Column('vat_rate', sa.Numeric(5, 2), nullable=True, server_default='0'),
        sa.Column('vat_amount', sa.Numeric(15, 2), nullable=True, server_default='0'),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=True, server_default='0'),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='draft'),
        sa.Column('match_status', sa.String(length=24), nullable=True,
                  server_default='ok'),
        sa.Column('match_notes', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.ForeignKeyConstraint(['po_id'], ['purchase_orders.id'], ),
        sa.UniqueConstraint('company_id', 'supplier_id', 'invoice_series',
                            'invoice_number', name='uq_supplier_invoice_number'),
    )
    op.create_index('ix_supplier_invoices_company_id', 'supplier_invoices',
                    ['company_id'])
    op.create_index('ix_supplier_invoices_supplier_id', 'supplier_invoices',
                    ['supplier_id'])
    op.create_index('ix_supplier_invoices_po_id', 'supplier_invoices', ['po_id'])
    op.create_index('ix_supplier_invoices_status', 'supplier_invoices', ['status'])

    op.create_table(
        'supplier_invoice_lines',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('invoice_id', GUID(), nullable=False),
        sa.Column('po_line_id', GUID(), nullable=False),
        sa.Column('material_id', GUID(), nullable=True),
        sa.Column('quantity', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('unit_price', sa.Numeric(15, 2), nullable=True, server_default='0'),
        sa.Column('line_total', sa.Numeric(15, 2), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['invoice_id'], ['supplier_invoices.id'], ),
        sa.ForeignKeyConstraint(['po_line_id'], ['purchase_order_lines.id'], ),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ),
    )
    op.create_index('ix_supplier_invoice_lines_invoice_id',
                    'supplier_invoice_lines', ['invoice_id'])
    op.create_index('ix_supplier_invoice_lines_po_line_id',
                    'supplier_invoice_lines', ['po_line_id'])
    op.create_index('ix_supplier_invoice_lines_material_id',
                    'supplier_invoice_lines', ['material_id'])

    op.create_table(
        'supplier_payments',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('company_id', GUID(), nullable=False),
        sa.Column('supplier_id', GUID(), nullable=False),
        sa.Column('payment_number', sa.String(length=50), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False, server_default='0'),
        sa.Column('method', sa.String(length=20), nullable=False,
                  server_default='bank_transfer'),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False,
                  server_default='draft'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id'], ),
        sa.UniqueConstraint('company_id', 'payment_number',
                            name='uq_company_supplier_payment_number'),
    )
    op.create_index('ix_supplier_payments_company_id', 'supplier_payments',
                    ['company_id'])
    op.create_index('ix_supplier_payments_supplier_id', 'supplier_payments',
                    ['supplier_id'])

    op.create_table(
        'supplier_payment_allocations',
        sa.Column('id', GUID(), primary_key=True, nullable=False),
        sa.Column('payment_id', GUID(), nullable=False),
        sa.Column('invoice_id', GUID(), nullable=False),
        sa.Column('allocated_amount', sa.Numeric(15, 2), nullable=False,
                  server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payment_id'], ['supplier_payments.id'], ),
        sa.ForeignKeyConstraint(['invoice_id'], ['supplier_invoices.id'], ),
        sa.UniqueConstraint('payment_id', 'invoice_id',
                            name='uq_payment_invoice_allocation'),
    )
    op.create_index('ix_spa_payment_id', 'supplier_payment_allocations',
                    ['payment_id'])
    op.create_index('ix_spa_invoice_id', 'supplier_payment_allocations',
                    ['invoice_id'])


def downgrade() -> None:
    op.drop_index('ix_spa_invoice_id', table_name='supplier_payment_allocations')
    op.drop_index('ix_spa_payment_id', table_name='supplier_payment_allocations')
    op.drop_table('supplier_payment_allocations')

    op.drop_index('ix_supplier_payments_supplier_id', table_name='supplier_payments')
    op.drop_index('ix_supplier_payments_company_id', table_name='supplier_payments')
    op.drop_table('supplier_payments')

    op.drop_index('ix_supplier_invoice_lines_material_id',
                  table_name='supplier_invoice_lines')
    op.drop_index('ix_supplier_invoice_lines_po_line_id',
                  table_name='supplier_invoice_lines')
    op.drop_index('ix_supplier_invoice_lines_invoice_id',
                  table_name='supplier_invoice_lines')
    op.drop_table('supplier_invoice_lines')

    op.drop_index('ix_supplier_invoices_status', table_name='supplier_invoices')
    op.drop_index('ix_supplier_invoices_po_id', table_name='supplier_invoices')
    op.drop_index('ix_supplier_invoices_supplier_id', table_name='supplier_invoices')
    op.drop_index('ix_supplier_invoices_company_id', table_name='supplier_invoices')
    op.drop_table('supplier_invoices')

    with op.batch_alter_table('purchase_order_lines') as batch:
        batch.drop_column('quantity_invoiced')
