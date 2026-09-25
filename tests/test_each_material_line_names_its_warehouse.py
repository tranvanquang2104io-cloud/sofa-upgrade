"""Each material line says which warehouse it is drawn from.

The owner: "từng thành phần nguyên vật liệu trong đơn đó thì phải được chỉ
định lấy từ kho nào ra để trừ tồn kho".

A plan built at the workshop may take its fabric from the fabric store and its
frames from the timber yard — different places, one job. Until now the whole
plan drew from one location, resolved from the plan and ultimately from the
branch that sold the order.

A line with no warehouse of its own draws from the plan's production site, as
it always did. So a workshop that keeps everything in one place sets nothing
and sees no change.

**A limitation, stated rather than hidden.** `MaterialStock` is keyed by
(material, store), not by warehouse, so a line's warehouse resolves to the
store that warehouse belongs to. Two warehouses inside the SAME branch
therefore share one stock row and cannot be told apart — choosing between them
changes nothing. Drawing from another BRANCH's warehouse works, which is the
case the owner described (production at one site, the store at another).
Re-keying stock by warehouse is a data migration of its own and is recorded in
REFACTOR-2026Q3.md rather than smuggled in here; pretending the finer case
works would be worse than saying it does not.
"""
import pytest


@pytest.fixture()
def two_sites(app, seed):
    """A workshop that builds, and a separate fabric store that holds."""
    from app.config import db
    from app.models import Order, Store
    from app.models.models import (
        Material, MaterialStock, ProductionMaterialLine, ProductionPlan,
        Warehouse,
    )

    with app.app_context():
        workshop = Store(company_id=seed['company_id'], store_code='XUONG-L',
                         name='Xưởng Hoài Đức', is_active=True)
        depot = Store(company_id=seed['company_id'], store_code='KHO-VAI',
                      name='Kho vải Long Biên', is_active=True)
        db.session.add_all([workshop, depot])
        db.session.flush()
        depot_warehouse = Warehouse(company_id=seed['company_id'],
                                    store_id=depot.id,
                                    warehouse_code='W-VAI', name='Kho vải',
                                    is_default=True, is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-L', name='Vải bố',
                            is_active=True)
        db.session.add_all([depot_warehouse, material])
        db.session.flush()

        # The fabric is at the depot; the workshop holds none.
        db.session.add_all([
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id, store_id=depot.id,
                          current_quantity=60),
            MaterialStock(company_id=seed['company_id'],
                          material_id=material.id, store_id=workshop.id,
                          current_quantity=0),
        ])

        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-LINE',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-LINE',
                              production_store_id=workshop.id)
        db.session.add(plan)
        db.session.flush()
        line = ProductionMaterialLine(plan_id=plan.id,
                                      material_id=material.id,
                                      quantity_required=20, unit='m')
        db.session.add(line)
        db.session.commit()
        return {**seed, 'plan_id': str(plan.id), 'line_id': str(line.id),
                'material_id': str(material.id),
                'workshop_id': str(workshop.id), 'depot_id': str(depot.id),
                'depot_warehouse_id': str(depot_warehouse.id)}


def test_a_line_without_a_warehouse_draws_from_the_production_site(
        app, two_sites):
    """The common case must not change: nobody sets anything."""
    from app.models.models import ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        levels = ProductionPlanService().stock_levels(
            ProductionPlan.query.get(two_sites['plan_id']))
        row = levels[two_sites['line_id']]
        assert row['available'] == 0, (
            'the line names no warehouse, so it must read the workshop, which '
            f"holds nothing — it read {row['available']}")
        assert row['short'] is True


def test_naming_a_warehouse_moves_where_the_line_reads_from(app, two_sites):
    from app.config import db
    from app.models.models import ProductionMaterialLine, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        line = ProductionMaterialLine.query.get(two_sites['line_id'])
        line.warehouse_id = two_sites['depot_warehouse_id']
        db.session.commit()

        levels = ProductionPlanService().stock_levels(
            ProductionPlan.query.get(two_sites['plan_id']))
        row = levels[two_sites['line_id']]
        assert row['available'] == 60, (
            'the line says it is drawn from the fabric store, which holds '
            f"60m, and the plan still reads {row['available']}")
        assert row['short'] is False


def test_issuing_deducts_from_the_warehouse_the_line_names(app, two_sites):
    """Reading the right place is half; taking from it is the half that counts."""
    from app.config import db
    from app.models.models import (
        MaterialStock, ProductionMaterialLine, ProductionPlan,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        line = ProductionMaterialLine.query.get(two_sites['line_id'])
        line.warehouse_id = two_sites['depot_warehouse_id']
        db.session.commit()

        shortages = ProductionPlanService().issue_materials(
            ProductionPlan.query.get(two_sites['plan_id']))
        assert shortages == [], f'refused: {shortages}'

        depot = MaterialStock.query.filter_by(
            material_id=two_sites['material_id'],
            store_id=two_sites['depot_id']).one()
        workshop = MaterialStock.query.filter_by(
            material_id=two_sites['material_id'],
            store_id=two_sites['workshop_id']).one()
        assert float(depot.current_quantity) == 40, (
            '20m was issued and the fabric store still shows '
            f'{depot.current_quantity}')
        assert float(workshop.current_quantity) == 0, (
            'the workshop was debited for fabric it never held')


def test_a_warehouse_from_another_company_is_refused(app, two_sites):
    """The same rule as receiving: refuse, do not substitute."""
    from app.config import db
    from app.models import Company, Store
    from app.models.models import (
        ProductionMaterialLine, ProductionPlan, Warehouse,
    )
    from app.services.services import ProductionPlanService

    with app.app_context():
        other = Company(company_code='OTHER-L', name='Xưởng khác',
                        email='o@l.test')
        db.session.add(other)
        db.session.flush()
        their_store = Store(company_id=other.id, store_code='S',
                            name='Cơ sở', is_active=True)
        db.session.add(their_store)
        db.session.flush()
        theirs = Warehouse(company_id=other.id, store_id=their_store.id,
                           warehouse_code='W-X', name='Kho của họ',
                           is_default=True, is_active=True)
        db.session.add(theirs)
        db.session.flush()

        line = ProductionMaterialLine.query.get(two_sites['line_id'])
        line.warehouse_id = theirs.id
        db.session.commit()

        with pytest.raises(ValueError):
            ProductionPlanService().stock_levels(
                ProductionPlan.query.get(two_sites['plan_id']))
