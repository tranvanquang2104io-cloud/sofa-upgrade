"""Two lines of the same material on one receipt blend correctly.

Raised in review as a defect: `_update_average_cost` runs once per line and
derives `qty_before` as (total across locations) − (this line's quantity), so
on the SECOND line for the same material the first line's quantity sits inside
`qty_before` and — the claim went — is therefore valued at the old average
instead of the price just paid.

Working it through, that is not what happens. After line 1 the material's
average has already been rewritten to include line 1 at its own price, so
(S + q1) × avg₁ = S × old + q1 × p1 exactly. Substituting into line 2 gives

    (S × old + q1 × p1 + q2 × p2) / (S + q1 + q2)

which is the answer computed in one pass. Sequential blending is correct here,
and the finding is rejected.

These tests exist because that reasoning is easy to get wrong in either
direction, and because a split delivery at two prices is ordinary — a roll of
fabric short-shipped and topped up at a different rate. Arithmetic nobody has
pinned is arithmetic that drifts.
"""
import datetime as dt
import decimal

import pytest


@pytest.fixture()
def po_with_two_lines_of_one_material(app, seed):
    """One purchase order buying the same fabric twice, at different prices."""
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-AVG', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-AVG', name='Vải nhung',
                            is_active=True, avg_cost=0)
        db.session.add_all([supplier, material])
        db.session.flush()

        order = PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            po_number='PO-AVG', order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(order)
        db.session.flush()
        first = PurchaseOrderLine(po_id=order.id, material_id=material.id,
                                  quantity_ordered=10, unit_price=100_000)
        second = PurchaseOrderLine(po_id=order.id, material_id=material.id,
                                   quantity_ordered=10, unit_price=200_000)
        db.session.add_all([first, second])
        db.session.commit()
        return {**seed, 'po_id': str(order.id), 'material_id': str(material.id),
                'line_ids': [str(first.id), str(second.id)]}


def test_two_lines_at_different_prices_average_correctly(
        app, po_with_two_lines_of_one_material):
    """10 at 100,000 and 10 at 200,000 is 150,000, not 100,000 or 200,000."""
    from app.models.models import Material, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    data = po_with_two_lines_of_one_material
    with app.app_context():
        order = PurchaseOrder.query.get(data['po_id'])
        ProcurementService().receive(order, {
            data['line_ids'][0]: decimal.Decimal('10'),
            data['line_ids'][1]: decimal.Decimal('10'),
        })
        material = Material.query.get(data['material_id'])
        average = float(material.avg_cost)

    assert average == 150_000, (
        f'the two lines blended to {average:,.0f} instead of 150,000')


def test_existing_stock_is_carried_into_the_average(
        app, po_with_two_lines_of_one_material):
    """What the business already holds is part of what it paid on average."""
    from app.config import db
    from app.models.models import Material, MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    data = po_with_two_lines_of_one_material
    with app.app_context():
        material = Material.query.get(data['material_id'])
        material.avg_cost = 50_000
        db.session.add(MaterialStock(material_id=material.id,
                                     company_id=data['company_id'],
                                     store_id=None,
                                     current_quantity=decimal.Decimal('20')))
        db.session.commit()

        order = PurchaseOrder.query.get(data['po_id'])
        ProcurementService().receive(order, {
            data['line_ids'][0]: decimal.Decimal('10'),
            data['line_ids'][1]: decimal.Decimal('10'),
        })
        average = float(Material.query.get(data['material_id']).avg_cost)

    # (20 x 50,000 + 10 x 100,000 + 10 x 200,000) / 40 = 100,000
    assert average == 100_000, (
        f'existing stock was not carried into the average: got {average:,.0f}')


def test_a_line_with_no_price_does_not_drag_the_average_to_zero(
        app, po_with_two_lines_of_one_material):
    """An unpriced line is unknown, not free."""
    from app.config import db
    from app.models.models import Material, PurchaseOrder, PurchaseOrderLine
    from app.services.procurement_service import ProcurementService

    data = po_with_two_lines_of_one_material
    with app.app_context():
        line = PurchaseOrderLine.query.get(data['line_ids'][1])
        line.unit_price = 0
        db.session.commit()

        order = PurchaseOrder.query.get(data['po_id'])
        ProcurementService().receive(order, {
            data['line_ids'][0]: decimal.Decimal('10'),
            data['line_ids'][1]: decimal.Decimal('10'),
        })
        average = float(Material.query.get(data['material_id']).avg_cost)

    assert average == 100_000, (
        f'the unpriced line was averaged in as free: got {average:,.0f}')
