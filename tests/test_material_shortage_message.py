"""A shortage must say which material is short, and by how much.

"Không đủ tồn kho cho 3 vật tư — chưa trừ kho." is true and useless. The
workshop manager now has to open the plan and compare every line against stock
by hand to find the three — and the system already knows exactly which three,
because it just checked them one at a time to produce that number.

This is the product's audience test: someone who is not technically minded
should be able to act on a message without reconstructing how it was reached.
"""
import decimal

import pytest


@pytest.fixture()
def plan_short_of_stock(app, seed):
    """An approved plan needing more fabric than the store holds."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Material, MaterialStock, ProductionPlan, ProductionPlanItem,
        ProductionMaterialLine,
    )

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-SHORT',
                      title='Sofa góc L')
        db.session.add(order)

        fabric = Material(company_id=seed['company_id'],
                          material_code='VAI-001', name='Vải nhung xanh rêu',
                          is_active=True)
        foam = Material(company_id=seed['company_id'],
                        material_code='MUT-D40', name='Mút D40',
                        is_active=True)
        db.session.add_all([fabric, foam])
        db.session.flush()

        # Enough foam, not nearly enough fabric.
        db.session.add(MaterialStock(material_id=fabric.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=decimal.Decimal('4.5')))
        db.session.add(MaterialStock(material_id=foam.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=decimal.Decimal('50')))

        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-SHORT',
                              status=ProductionPlan.STATUS_APPROVED)
        db.session.add(plan)
        db.session.flush()
        item = ProductionPlanItem(plan_id=plan.id, source_name='Sofa góc L',
                                  quantity=1)
        db.session.add(item)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=item.id, material_id=fabric.id,
            quantity_required=decimal.Decimal('12')))
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=item.id, material_id=foam.id,
            quantity_required=decimal.Decimal('8')))
        db.session.commit()
        return {**seed, 'order_id': str(order.id), 'plan_id': str(plan.id)}


def test_the_shortage_names_the_material(app, plan_short_of_stock):
    from app.models.models import ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        plan = ProductionPlan.query.get(plan_short_of_stock['plan_id'])
        shortages = ProductionPlanService().issue_materials(plan)

    assert len(shortages) == 1, 'only the fabric is short'
    short = shortages[0]
    assert short['name'] == 'Vải nhung xanh rêu'
    assert short['material_code'] == 'VAI-001'


def test_the_shortage_says_how_much_is_missing(app, plan_short_of_stock):
    from app.models.models import ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        plan = ProductionPlan.query.get(plan_short_of_stock['plan_id'])
        short = ProductionPlanService().issue_materials(plan)[0]

    assert short['need'] == 12
    assert short['available'] == 4.5
    assert short['missing'] == 7.5, (
        'the manager should not have to do the subtraction')


def test_the_message_on_screen_names_the_material(client, login,
                                                  plan_short_of_stock):
    """Scoped to the alert: the plan page lists every material either way."""
    import re

    login('admin')
    body = client.post(
        f"/production-plan/{plan_short_of_stock['plan_id']}/issue",
        follow_redirects=True).get_data(as_text=True)

    alerts = ' '.join(re.findall(r'<div class="alert[^"]*"[^>]*>(.*?)</div>',
                                 body, re.S))
    assert 'Vải nhung xanh rêu' in alerts, (
        'the message counted the shortages instead of naming them')
    assert 'Mút D40' not in alerts, (
        'the material that is in stock is not a problem')
