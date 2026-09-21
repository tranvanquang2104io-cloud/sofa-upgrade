"""Production, correct to the đồng — the chain that joins buying to selling.

This is where P2P and O2C meet: material bought at a known cost is issued to a
job sold at a known price, and the difference is what the business earned.

The numbers, fixed once so a drift fails:

    bought   100 m velvet @ 250,000 → stock 100, average cost 250,000
             plus 20 m foam  @ 150,000 → stock 20

    the job  sold for 32,344,000 (the O2C contract)

    issue    40 m velvet  = 10,000,000
             15 m foam    =  2,250,000
                            ----------
                            12,250,000   material cost

    stock after issue      60 m velvet, 5 m foam
    gross margin           32,344,000 − 12,250,000 = 20,094,000

Labour is excluded from that figure and the service says so, because a
material-only difference presented as profit flatters every job.
"""
import datetime as dt

import pytest

from app.services.procurement_service import ProcurementService
from app.services.services import ProductionPlanService

TODAY = dt.date(2026, 6, 20)

VELVET_QTY, VELVET_COST = 100, 250_000
FOAM_QTY, FOAM_COST = 20, 150_000

VELVET_ISSUED, FOAM_ISSUED = 40, 15
MATERIAL_COST = VELVET_ISSUED * VELVET_COST + FOAM_ISSUED * FOAM_COST  # 12,250,000

CONTRACT_VALUE = 32_344_000
GROSS_MARGIN = CONTRACT_VALUE - MATERIAL_COST                          # 20,094,000


@pytest.fixture()
def stocked_job(app, seed):
    """Two materials received into stock, and a signed contract with a plan."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, Material, MaterialCategory, MaterialUnit, ProductionMaterialLine,
        PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-SX', name='NCC Vật Tư')
        unit = MaterialUnit(company_id=seed['company_id'], name='mét')
        category = MaterialCategory(company_id=seed['company_id'], name='Vật tư')
        db.session.add_all([supplier, unit, category])
        db.session.flush()

        velvet = Material(company_id=seed['company_id'], material_code='VAI-SX',
                          name='Vải nhung', unit_id=unit.id,
                          category_id=category.id)
        foam = Material(company_id=seed['company_id'], material_code='MUT-SX',
                        name='Mút D40', unit_id=unit.id, category_id=category.id)
        db.session.add_all([velvet, foam])
        db.session.flush()

        order_po = PurchaseOrder(
            company_id=seed['company_id'], supplier_id=supplier.id,
            store_id=seed['store_id'], po_number='PO-SX', order_date=TODAY,
            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(order_po)
        db.session.flush()
        velvet_line = PurchaseOrderLine(
            po_id=order_po.id, material_id=velvet.id,
            quantity_ordered=VELVET_QTY, unit='mét', unit_price=VELVET_COST,
            line_total=VELVET_QTY * VELVET_COST)
        foam_line = PurchaseOrderLine(
            po_id=order_po.id, material_id=foam.id, quantity_ordered=FOAM_QTY,
            unit='mét', unit_price=FOAM_COST, line_total=FOAM_QTY * FOAM_COST)
        db.session.add_all([velvet_line, foam_line])
        db.session.commit()

        ProcurementService().receive(
            order_po,
            {str(velvet_line.id): VELVET_QTY, str(foam_line.id): FOAM_QTY},
            store_id=seed['store_id'])

        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-SX',
                      title='Bộ sofa')
        db.session.add(order)
        db.session.flush()
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-SX', contract_date=TODAY,
            contract_value=CONTRACT_VALUE, is_signed=True,
            items=[{'name': 'Sofa góc', 'unit': 'bộ', 'quantity': 1,
                    'unit_price': CONTRACT_VALUE, 'total': CONTRACT_VALUE}])
        db.session.add(contract)
        db.session.commit()

        plan = ProductionPlanService().create_from_contract(contract)
        item_id = plan.items[0].id if plan.items else None
        db.session.add_all([
            ProductionMaterialLine(plan_id=plan.id, plan_item_id=item_id,
                                   material_id=velvet.id,
                                   quantity_required=VELVET_ISSUED, unit='mét'),
            ProductionMaterialLine(plan_id=plan.id, plan_item_id=item_id,
                                   material_id=foam.id,
                                   quantity_required=FOAM_ISSUED, unit='mét'),
        ])
        db.session.commit()

        return {'plan_id': str(plan.id), 'order_id': str(order.id),
                'velvet_id': str(velvet.id), 'foam_id': str(foam.id), **seed}


def _plan(plan_id):
    from app.models.models import ProductionPlan
    return ProductionPlan.query.get(plan_id)


def _stock(material_id):
    from app.models.models import MaterialStock
    rows = MaterialStock.query.filter_by(material_id=material_id).all()
    return sum(float(r.current_quantity or 0) for r in rows)


# --- receiving fed the costs ---------------------------------------------

def test_the_materials_arrived_with_their_costs(app, stocked_job):
    from app.models.models import Material

    with app.app_context():
        assert _stock(stocked_job['velvet_id']) == VELVET_QTY
        assert _stock(stocked_job['foam_id']) == FOAM_QTY
        assert float(Material.query.get(
            stocked_job['velvet_id']).avg_cost) == VELVET_COST
        assert float(Material.query.get(
            stocked_job['foam_id']).avg_cost) == FOAM_COST


# --- issuing --------------------------------------------------------------

def test_issuing_deducts_exactly_what_the_plan_needs(app, stocked_job):
    with app.app_context():
        shortages = ProductionPlanService().issue_materials(
            _plan(stocked_job['plan_id']))
        assert shortages == []

        assert _stock(stocked_job['velvet_id']) == VELVET_QTY - VELVET_ISSUED
        assert _stock(stocked_job['foam_id']) == FOAM_QTY - FOAM_ISSUED


def test_a_shortage_deducts_nothing_at_all(app, stocked_job):
    """Half-issuing a job would leave the stock figures lying."""
    from app.config import db
    from app.models.models import ProductionMaterialLine

    with app.app_context():
        line = ProductionMaterialLine.query.filter_by(
            plan_id=stocked_job['plan_id'],
            material_id=stocked_job['foam_id']).first()
        line.quantity_required = FOAM_QTY + 5        # more foam than exists
        db.session.commit()

        shortages = ProductionPlanService().issue_materials(
            _plan(stocked_job['plan_id']))

        assert len(shortages) == 1
        assert shortages[0]['need'] == FOAM_QTY + 5
        assert shortages[0]['available'] == FOAM_QTY
        assert _stock(stocked_job['velvet_id']) == VELVET_QTY, (
            "the velvet was available, but a partial issue must not happen"
        )


def test_issuing_twice_does_not_deduct_twice(app, stocked_job):
    with app.app_context():
        ProductionPlanService().issue_materials(_plan(stocked_job['plan_id']))
        ProductionPlanService().issue_materials(_plan(stocked_job['plan_id']))

        assert _stock(stocked_job['velvet_id']) == VELVET_QTY - VELVET_ISSUED


# --- what the job cost and earned ----------------------------------------

def test_the_job_cost_is_issued_quantity_times_average_cost(app, stocked_job):
    with app.app_context():
        ProductionPlanService().issue_materials(_plan(stocked_job['plan_id']))

        cost = ProductionPlanService().material_cost(_plan(stocked_job['plan_id']))
        assert cost['total'] == MATERIAL_COST
        assert cost['complete'] is True


def test_nothing_issued_costs_nothing(app, stocked_job):
    with app.app_context():
        cost = ProductionPlanService().material_cost(_plan(stocked_job['plan_id']))
        assert cost['total'] == 0


def test_the_margin_is_the_contract_value_less_the_material(app, stocked_job):
    with app.app_context():
        ProductionPlanService().issue_materials(_plan(stocked_job['plan_id']))

        margin = ProductionPlanService().order_margin(_plan(stocked_job['plan_id']))
        assert margin['revenue'] == CONTRACT_VALUE
        assert margin['material_cost'] == MATERIAL_COST
        assert margin['gross_margin'] == GROSS_MARGIN


def test_the_margin_says_labour_is_not_in_it(app, stocked_job):
    with app.app_context():
        margin = ProductionPlanService().order_margin(_plan(stocked_job['plan_id']))
        assert margin['excludes_labour'] is True


def test_a_material_with_no_recorded_cost_is_counted_as_unpriced(app,
                                                                 stocked_job):
    """A total that quietly omits a line is worse than one that says so."""
    from app.config import db
    from app.models.models import Material

    with app.app_context():
        ProductionPlanService().issue_materials(_plan(stocked_job['plan_id']))
        Material.query.get(stocked_job['foam_id']).avg_cost = 0
        db.session.commit()

        cost = ProductionPlanService().material_cost(_plan(stocked_job['plan_id']))
        assert cost['unpriced_lines'] == 1
        assert cost['complete'] is False
        assert cost['total'] == VELVET_ISSUED * VELVET_COST
