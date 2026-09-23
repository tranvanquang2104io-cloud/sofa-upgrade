"""The plan must show what is in stock before the manager presses Cấp phát.

The material table listed Required and Issued — what the job needs and what has
been handed over — but not what the store actually holds. So the only way to
learn that the fabric is short was to press Cấp phát and be refused. The system
knows the answer while the manager is still reading the screen.

Telling them afterwards is not a smaller version of telling them before: before,
they can raise a purchase requisition and carry on; after, they have already
promised the workshop a start date.
"""
import decimal

import pytest


@pytest.fixture()
def plan_with_stock(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Material, MaterialStock, ProductionPlan, ProductionPlanItem,
        ProductionMaterialLine,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-STOCK',
                      title='Sofa góc L')
        db.session.add(order)

        fabric = Material(company_id=seed['company_id'],
                          material_code='VAI-010', name='Vải nhung ghi',
                          is_active=True)
        foam = Material(company_id=seed['company_id'],
                        material_code='MUT-D40', name='Mút D40', is_active=True)
        db.session.add_all([fabric, foam])
        db.session.flush()

        db.session.add(MaterialStock(material_id=fabric.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=decimal.Decimal('3')))
        db.session.add(MaterialStock(material_id=foam.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=decimal.Decimal('80')))

        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-STOCK',
                              status=ProductionPlan.STATUS_APPROVED)
        db.session.add(plan)
        db.session.flush()
        item = ProductionPlanItem(plan_id=plan.id, source_name='Sofa góc L',
                                  quantity=1)
        db.session.add(item)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=item.id, material_id=fabric.id,
            quantity_required=decimal.Decimal('12'), unit='m'))
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=item.id, material_id=foam.id,
            quantity_required=decimal.Decimal('8'), unit='tấm'))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_the_plan_reports_stock_for_each_material(app, plan_with_stock):
    from app.models.models import ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        plan = ProductionPlan.query.filter_by(plan_number='KH-STOCK').first()
        levels = ProductionPlanService().stock_levels(plan)

    by_name = {value['name']: value for value in levels.values()}
    assert by_name['Vải nhung ghi']['available'] == 3
    assert by_name['Mút D40']['available'] == 80


def test_it_says_which_lines_are_short(app, plan_with_stock):
    from app.models.models import ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        plan = ProductionPlan.query.filter_by(plan_number='KH-STOCK').first()
        levels = ProductionPlanService().stock_levels(plan)

    by_name = {value['name']: value for value in levels.values()}
    assert by_name['Vải nhung ghi']['short'] is True
    assert by_name['Vải nhung ghi']['missing'] == 9
    assert by_name['Mút D40']['short'] is False


def test_a_material_never_stocked_reads_as_zero_not_as_an_error(app, seed):
    """A material with no stock row at all is the common case for a new one."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Material, ProductionPlan, ProductionMaterialLine,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-NEW',
                      title='Sofa mới')
        db.session.add(order)
        new_material = Material(company_id=seed['company_id'],
                                material_code='CHAN-01', name='Chân gỗ sồi',
                                is_active=True)
        db.session.add(new_material)
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-NEW')
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=new_material.id,
            quantity_required=decimal.Decimal('4')))
        db.session.commit()

        levels = ProductionPlanService().stock_levels(plan)

    only = list(levels.values())[0]
    assert only['available'] == 0
    assert only['short'] is True


def test_the_screen_shows_the_stock_column(client, login, plan_with_stock):
    """Scoped to the material table.

    Asserting on the whole page passed before the column existed — "Tồn kho"
    is also the label of the inventory menu. The same echo that made an orders
    filter look broken made this one look finished.
    """
    import re

    login('admin')
    body = client.get(
        f"/orders/{plan_with_stock['order_id']}/production-plan").get_data(
            as_text=True)

    tables = re.findall(r'<table.*?</table>', body, re.S)
    material_table = [t for t in tables if 'Vải nhung ghi' in t]
    assert material_table, 'the material table did not render'
    assert 'Tồn kho' in material_table[0], 'the plan screen has no stock column'


def test_the_screen_marks_the_line_that_is_short(client, login,
                                                 plan_with_stock):
    """Colour is never the only carrier: the shortfall is written out."""
    login('admin')
    body = client.get(
        f"/orders/{plan_with_stock['order_id']}/production-plan").get_data(
            as_text=True)
    assert 'thiếu 9' in body, (
        'the screen does not say how much the short line is missing')
