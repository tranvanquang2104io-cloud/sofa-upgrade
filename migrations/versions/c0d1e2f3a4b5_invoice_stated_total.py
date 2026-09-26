"""What the supplier's paper says the total is.

`SupplierInvoice` recomputes its totals from its lines, and a real invoice often
disagrees: a freight line the model has no room for, a volume discount as one
negative line at the bottom, or the seller rounding VAT on the total while this
system rounds per line.

The dangerous part was never the difference. It was what a clerk does with a
paper invoice that will not match and a screen insisting it must — they adjust
a unit price until the total agrees, which silently corrupts the price history
the three-way match checks variance against. The check stops comparing what was
ordered with what was billed, and nothing reports that it has stopped.

Nullable and left empty everywhere. An invoice nobody typed a stated total on
matches exactly as it did before, so nothing changes for anybody until somebody
chooses to use it.

This does NOT model freight or discounts. Which of those to build has to be
decided against real invoices from this company's suppliers — recorded in
§8.10 — and guessing would be modelling a shape nobody has seen.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-09-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, Sequence[str], None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('supplier_invoices') as batch:
        batch.add_column(sa.Column('stated_total', sa.Numeric(15, 2),
                                   nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('supplier_invoices') as batch:
        batch.drop_column('stated_total')
