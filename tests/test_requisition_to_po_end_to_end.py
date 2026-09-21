"""The front of P2P: what to buy, and turning that into orders.

Two steps the earlier validation skipped — the suggestion that says how much to
buy, and the conversion of an approved requisition into purchase orders.

The suggestion formula, from the service: **buy = need − on hand + minimum**,
where `need` is what live production plans still require and have not been
issued. Two materials are set up so the arithmetic differs in every term:

    velvet  plan needs 50, issued 10 → need 40; stock 15; min 5
            → 40 − 15 + 5 = 30

    foam    plan needs 0;             stock 2;  min 8
            → 0 − 2 + 8  = 6          (bought because it is below minimum)

    leather plan needs 0;             stock 20; min 5
            → nothing suggested       (nothing needs it and stock is fine)

Conversion groups by supplier, because one order per supplier is what actually
gets sent. Velvet and foam share a supplier, leather has another, so an
approved requisition covering all three produces two purchase orders.
"""
import datetime as dt

import pytest

from app.services.requisition_service import RequisitionService
from app.services.services import ProductionPlanService

TODAY = dt.date(2026, 6, 20)

VELVET_NEED, VELVET_ISSUED, VELVET_STOCK, VELVET_MIN = 50, 10, 15, 5
VELVET_SUGGEST = (VELVET_NEED - VELVET_ISSUED) - VELVET_STOCK + VELVET_MIN  # 30

FOAM_STOCK, FOAM_MIN = 2, 8
FOAM_SUGGEST = FOAM_MIN - FOAM_STOCK                                        # 6

LEATHER_STOCK, LEATHER_MIN = 20, 5


@pytest.fixture()
def workshop(app, seed):
    """Three materials, two suppliers, and a live plan needing velvet."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, Material, MaterialCategory, MaterialStock, MaterialUnit,
        ProductionMaterialLine, Supplier,
    )

    with app.app_context():
        supplier_a = Supplier(company_id=seed['company_id'],
                              supplier_code='NCC-A', name='NCC Vải Mút')
        supplier_b = Supplier(company_id=seed['company_id'],
                              supplier_code='NCC-B', name='NCC Da')
        unit = MaterialUnit(company_id=seed['company_id'], name='mét')
        category = MaterialCategory(company_id=seed['company_id'], name='Vật tư')
        db.session.add_all([supplier_a, supplier_b, unit, category])
        db.session.flush()

        velvet = Material(company_id=seed['company_id'], material_code='VAI-PR',
                          name='Vải nhung', unit_id=unit.id,
                          category_id=category.id, supplier_id=supplier_a.id,
                          unit_price=250_000, min_stock_level=VELVET_MIN)
        foam = Material(company_id=seed['company_id'], material_code='MUT-PR',
                        name='Mút D40', unit_id=unit.id,
                        category_id=category.id, supplier_id=supplier_a.id,
                        unit_price=150_000, min_stock_level=FOAM_MIN)
        leather = Material(company_id=seed['company_id'], material_code='DA-PR',
                           name='Da bò', unit_id=unit.id,
                           category_id=category.id, supplier_id=supplier_b.id,
                           unit_price=900_000, min_stock_level=LEATHER_MIN)
        db.session.add_all([velvet, foam, leather])
        db.session.flush()

        for material, quantity in ((velvet, VELVET_STOCK), (foam, FOAM_STOCK),
                                   (leather, LEATHER_STOCK)):
            db.session.add(MaterialStock(
                company_id=seed['company_id'], material_id=material.id,
                store_id=seed['store_id'], current_quantity=quantity))

        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PR',
                      title='Sofa')
        db.session.add(order)
        db.session.flush()
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-PR', contract_date=TODAY,
            contract_value=50_000_000, is_signed=True,
            items=[{'name': 'Sofa góc', 'unit': 'bộ', 'quantity': 1,
                    'unit_price': 50_000_000, 'total': 50_000_000}])
        db.session.add(contract)
        db.session.commit()

        plan = ProductionPlanService().create_from_contract(contract)
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=plan.items[0].id if plan.items else None,
            material_id=velvet.id, quantity_required=VELVET_NEED,
            quantity_issued=VELVET_ISSUED, unit='mét'))
        db.session.commit()

        return {'velvet_id': str(velvet.id), 'foam_id': str(foam.id),
                'leather_id': str(leather.id),
                'supplier_a': str(supplier_a.id),
                'supplier_b': str(supplier_b.id), **seed}


def _suggestions(company_id):
    """Flatten the per-supplier groups into {material id: line}."""
    data = ProductionPlanService().purchase_suggestions(company_id)
    rows = {str(line['material'].id): line
            for group in data['groups'] for line in group['lines']}
    return data, rows


# --- what to buy ----------------------------------------------------------

def test_a_material_short_for_a_live_plan_is_suggested(app, workshop):
    with app.app_context():
        _data, rows = _suggestions(workshop['company_id'])
        assert float(rows[workshop['velvet_id']]['suggested']) == VELVET_SUGGEST


def test_the_issued_part_is_not_asked_for_again(app, workshop):
    """10 of the 50 are already on the bench; only the remainder is a need."""
    with app.app_context():
        _data, rows = _suggestions(workshop['company_id'])
        assert float(rows[workshop['velvet_id']]['required']) == (
            VELVET_NEED - VELVET_ISSUED)


def test_a_material_below_its_minimum_is_suggested_with_no_plan(app, workshop):
    with app.app_context():
        _data, rows = _suggestions(workshop['company_id'])
        assert float(rows[workshop['foam_id']]['suggested']) == FOAM_SUGGEST


def test_a_material_with_enough_stock_is_not_suggested(app, workshop):
    with app.app_context():
        _data, rows = _suggestions(workshop['company_id'])
        assert workshop['leather_id'] not in rows


def test_the_estimate_is_the_quantity_times_the_price(app, workshop):
    with app.app_context():
        _data, rows = _suggestions(workshop['company_id'])
        assert float(rows[workshop['velvet_id']]['est_cost']) == (
            VELVET_SUGGEST * 250_000)


def test_suggestions_do_not_cross_tenants(app, workshop):
    from app.config import db
    from app.models import Company

    with app.app_context():
        rival = Company(company_code='SUG', name='Rival', email='r@sug.test')
        db.session.add(rival)
        db.session.commit()

        data = ProductionPlanService().purchase_suggestions(rival.id)
        assert data['count'] == 0


# --- turning it into orders ----------------------------------------------

@pytest.fixture()
def approved_requisition(app, workshop):
    from app.config import db
    from app.models.models import PurchaseRequisition, PurchaseRequisitionLine

    with app.app_context():
        requisition = PurchaseRequisition(
            company_id=workshop['company_id'], store_id=workshop['store_id'],
            pr_number='PR-001', request_date=TODAY,
            status=PurchaseRequisition.STATUS_APPROVED)
        db.session.add(requisition)
        db.session.flush()
        db.session.add_all([
            PurchaseRequisitionLine(pr_id=requisition.id,
                                    material_id=workshop['velvet_id'],
                                    quantity=VELVET_SUGGEST, unit='mét'),
            PurchaseRequisitionLine(pr_id=requisition.id,
                                    material_id=workshop['foam_id'],
                                    quantity=FOAM_SUGGEST, unit='mét'),
            PurchaseRequisitionLine(pr_id=requisition.id,
                                    material_id=workshop['leather_id'],
                                    quantity=3, unit='mét'),
        ])
        db.session.commit()
        return {'pr_id': str(requisition.id), **workshop}


def _requisition(pr_id):
    from app.models.models import PurchaseRequisition
    return PurchaseRequisition.query.get(pr_id)


def test_one_order_per_supplier(app, approved_requisition):
    """Two suppliers, so two orders — one per envelope that gets sent."""
    with app.app_context():
        created = RequisitionService().convert_to_pos(
            _requisition(approved_requisition['pr_id']))
        assert len(created) == 2

        by_supplier = {str(po.supplier_id): po for po in created}
        assert set(by_supplier) == {approved_requisition['supplier_a'],
                                    approved_requisition['supplier_b']}


def test_the_lines_land_on_the_right_order(app, approved_requisition):
    with app.app_context():
        created = RequisitionService().convert_to_pos(
            _requisition(approved_requisition['pr_id']))
        by_supplier = {str(po.supplier_id): po for po in created}

        shared = by_supplier[approved_requisition['supplier_a']]
        assert len(shared.lines) == 2
        assert len(by_supplier[approved_requisition['supplier_b']].lines) == 1


def test_the_quantities_survive_the_conversion(app, approved_requisition):
    with app.app_context():
        created = RequisitionService().convert_to_pos(
            _requisition(approved_requisition['pr_id']))
        quantities = {
            str(line.material_id): float(line.quantity_ordered)
            for po in created for line in po.lines
        }
        assert quantities[approved_requisition['velvet_id']] == VELVET_SUGGEST
        assert quantities[approved_requisition['foam_id']] == FOAM_SUGGEST


def test_converting_marks_the_requisition_done(app, approved_requisition):
    from app.models.models import PurchaseRequisition

    with app.app_context():
        RequisitionService().convert_to_pos(
            _requisition(approved_requisition['pr_id']))
        assert _requisition(
            approved_requisition['pr_id']).status == (
                PurchaseRequisition.STATUS_CONVERTED)


def test_an_unapproved_requisition_cannot_be_converted(app, workshop):
    from app.config import db
    from app.models.models import PurchaseRequisition, PurchaseRequisitionLine

    with app.app_context():
        requisition = PurchaseRequisition(
            company_id=workshop['company_id'], store_id=workshop['store_id'],
            pr_number='PR-DRAFT', request_date=TODAY,
            status=PurchaseRequisition.STATUS_DRAFT)
        db.session.add(requisition)
        db.session.flush()
        db.session.add(PurchaseRequisitionLine(
            pr_id=requisition.id, material_id=workshop['velvet_id'],
            quantity=5, unit='mét'))
        db.session.commit()

        with pytest.raises(ValueError):
            RequisitionService().convert_to_pos(requisition)


def test_an_empty_requisition_cannot_be_converted(app, workshop):
    from app.config import db
    from app.models.models import PurchaseRequisition

    with app.app_context():
        requisition = PurchaseRequisition(
            company_id=workshop['company_id'], store_id=workshop['store_id'],
            pr_number='PR-EMPTY', request_date=TODAY,
            status=PurchaseRequisition.STATUS_APPROVED)
        db.session.add(requisition)
        db.session.commit()

        with pytest.raises(ValueError):
            RequisitionService().convert_to_pos(requisition)
