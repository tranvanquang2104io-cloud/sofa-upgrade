"""One material short must not hold up the other nine.

`issue_materials` checks every line, and if ANY is short it issues NOTHING. On
a single-location workshop that is defensible: everything is in one room, so a
shortage is usually real and the job cannot start anyway.

With material drawn from several warehouses it stops being defensible. A plan
needing ten materials, nine of them on the shelf and one still with the
supplier, cannot have the nine handed over — so the upholsterer waits for
fabric he already has, and somebody eventually writes the numbers down on
paper and stops using the screen.

But issuing part of a plan silently would be worse than refusing: the foreman
presses Cấp phát, sees a success message, and does not learn that a third of
the job is missing until he is looking for it.

So it is an explicit choice. `issue_materials` refuses exactly as it always
did — same call, same result, and every existing caller keeps its behaviour —
and `issue_materials(plan, allow_partial=True)` hands over what is there and
says what is still missing. The screen asks; the service does not decide.

Also fixed here, because partial issuing makes it reachable:
`quantity_issued` was ASSIGNED `quantity_required` rather than increased by
what was actually taken. Under all-or-nothing the two are the same number, so
nothing showed. Issue 12 of 20 and then 8 more, and the assignment would say
20 after the first handover — the plan would look complete with 8m still on
the shelf.
"""
import pytest


@pytest.fixture()
def plan_with_one_short_material(app, seed):
    """Two materials: 30m of fabric on hand, and no foam at all."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Material, MaterialStock, ProductionMaterialLine, ProductionPlan,
    )

    with app.app_context():
        fabric = Material(company_id=seed['company_id'],
                          material_code='VAI-P', name='Vải bố', is_active=True)
        foam = Material(company_id=seed['company_id'],
                        material_code='MUT-P', name='Mút D40', is_active=True)
        db.session.add_all([fabric, foam])
        db.session.flush()
        db.session.add_all([
            MaterialStock(company_id=seed['company_id'],
                          material_id=fabric.id, store_id=seed['store_id'],
                          current_quantity=30),
            MaterialStock(company_id=seed['company_id'],
                          material_id=foam.id, store_id=seed['store_id'],
                          current_quantity=0),
        ])
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PART',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-PART')
        db.session.add(plan)
        db.session.flush()
        fabric_line = ProductionMaterialLine(
            plan_id=plan.id, material_id=fabric.id,
            quantity_required=20, unit='m')
        foam_line = ProductionMaterialLine(
            plan_id=plan.id, material_id=foam.id,
            quantity_required=6, unit='tấm')
        db.session.add_all([fabric_line, foam_line])
        db.session.commit()
        return {**seed, 'plan_id': str(plan.id),
                'fabric_id': str(fabric.id), 'foam_id': str(foam.id),
                'fabric_line_id': str(fabric_line.id)}


def test_the_default_still_refuses_the_whole_plan(app,
                                                  plan_with_one_short_material):
    """Every existing caller must behave exactly as before."""
    from app.models.models import MaterialStock, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        shortages = ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan_with_one_short_material['plan_id']))
        assert len(shortages) == 1
        assert shortages[0]['material_code'] == 'MUT-P'

        fabric = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['fabric_id']).one()
        assert float(fabric.current_quantity) == 30, (
            'the refusal took fabric anyway')


def test_asking_for_a_partial_issue_hands_over_what_is_there(
        app, plan_with_one_short_material):
    from app.models.models import MaterialStock, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        shortages = ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan_with_one_short_material['plan_id']),
            allow_partial=True)

        fabric = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['fabric_id']).one()
        assert float(fabric.current_quantity) == 10, (
            'the fabric that was on the shelf was not handed over')
        assert len(shortages) == 1, (
            'a partial issue must still say what is missing — a success '
            'message alone leaves the foreman to discover it')
        assert shortages[0]['material_code'] == 'MUT-P'


def test_the_short_material_is_not_issued_at_all(app,
                                                 plan_with_one_short_material):
    """Partial means per line, not "take whatever is there on every line"."""
    from app.models.models import MaterialStock, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan_with_one_short_material['plan_id']),
            allow_partial=True)
        foam = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['foam_id']).one()
        assert float(foam.current_quantity) == 0


def test_issuing_the_rest_later_adds_up(app, plan_with_one_short_material):
    """`quantity_issued` must accumulate, not be assigned the requirement.

    Under all-or-nothing the two were the same number, so the assignment never
    showed. It shows the moment a plan is issued twice.
    """
    from app.config import db
    from app.models.models import (
        MaterialStock, ProductionMaterialLine, ProductionPlan,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        # Only 12m of the 20 needed is on the shelf for the first handover.
        fabric = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['fabric_id']).one()
        fabric.current_quantity = 12
        db.session.commit()

        ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan_with_one_short_material['plan_id']),
            allow_partial=True)
        line = ProductionMaterialLine.query.get(
            plan_with_one_short_material['fabric_line_id'])
        assert float(line.quantity_issued) == 12, (
            f'12m was handed over and the line says {line.quantity_issued} — '
            'the plan would look complete with 8m still on the shelf')

        # The rest arrives.
        fabric = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['fabric_id']).one()
        fabric.current_quantity = 8
        db.session.commit()

        ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan_with_one_short_material['plan_id']),
            allow_partial=True)
        line = ProductionMaterialLine.query.get(
            plan_with_one_short_material['fabric_line_id'])
        assert float(line.quantity_issued) == 20


def test_the_plan_screen_offers_the_partial_handover(app, client, login,
                                                    plan_with_one_short_material):
    """A button, checked on the rendered page — not on the source.

    The first version of this asserted `'allow_partial' in body or True`,
    which is true whatever the page contains. A tautology in a test is worse
    than no test: it reports coverage that does not exist.
    """
    from app.config import db
    from app.models.models import ProductionPlan

    with app.app_context():
        plan = ProductionPlan.query.get(
            plan_with_one_short_material['plan_id'])
        plan.status = ProductionPlan.STATUS_APPROVED
        db.session.commit()
        order_id = str(plan.order_id)

    login('admin')
    body = client.get(f'/orders/{order_id}/production-plan').get_data(
        as_text=True)
    assert 'name="allow_partial"' in body, (
        'the plan screen has no way to ask for a partial handover, so the '
        'feature exists and nothing can reach it')


def test_the_partial_handover_reaches_the_service_from_the_screen(
        app, client, login, plan_with_one_short_material):
    """Checked because finished-but-unreachable has happened three times here.

    The route called `issue_materials(plan)` with no `allow_partial`, so the
    feature existed and the screen could not ask for it.
    """
    from app.config import db
    from app.models.models import MaterialStock, ProductionPlan

    with app.app_context():
        plan = ProductionPlan.query.get(
            plan_with_one_short_material['plan_id'])
        plan.status = ProductionPlan.STATUS_APPROVED
        db.session.commit()
        plan_id = str(plan.id)

    login('admin')
    client.post(f'/production-plan/{plan_id}/issue',
                data={'allow_partial': '1'}, follow_redirects=True)

    with app.app_context():
        fabric = MaterialStock.query.filter_by(
            material_id=plan_with_one_short_material['fabric_id']).one()
        assert float(fabric.current_quantity) == 10, (
            'the partial handover did not reach the service from the screen')
