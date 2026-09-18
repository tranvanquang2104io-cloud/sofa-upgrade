"""Did this job make money?

G3, the top remaining gap. The system already tracked what was issued to each
production plan; it just had no price, so a bespoke job's cost was unknowable
and "did we make money on this order" could not be answered at all.

The rules being pinned:
  * moving average, blended on each goods receipt;
  * a receipt with NO price is skipped, never averaged in as zero;
  * cost is based on what was ISSUED, not what was required;
  * an unpriced material is reported, not silently treated as free;
  * margin excludes labour and says so.
"""
import datetime as dt
from decimal import Decimal

import pytest

from app.services.procurement_service import ProcurementService
from app.services.services import ProductionPlanService


@pytest.fixture()
def po_setup(app, seed):
    """A supplier, a material and an ordered PO for 10 @ 100,000."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialUnit, PurchaseOrder,
        PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        sup = Supplier(company_id=seed["company_id"], supplier_code="S-C",
                       name="NCC")
        unit = MaterialUnit(company_id=seed["company_id"], name="m")
        cat = MaterialCategory(company_id=seed["company_id"], name="v")
        db.session.add_all([sup, unit, cat])
        db.session.flush()
        mat = Material(company_id=seed["company_id"], material_code="M-C",
                       name="Vai nhung", unit_id=unit.id, category_id=cat.id)
        db.session.add(mat)
        db.session.flush()
        po = PurchaseOrder(company_id=seed["company_id"], supplier_id=sup.id,
                           store_id=seed["store_id"], po_number="PO-C1",
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id, material_id=mat.id,
                                 quantity_ordered=10, unit="m",
                                 unit_price=100_000, line_total=1_000_000)
        db.session.add(line)
        db.session.commit()
        return {'po_id': str(po.id), 'line_id': str(line.id),
                'material_id': str(mat.id), **seed}


def _material(mid):
    from app.models.models import Material
    return Material.query.get(mid)


def _po(pid):
    from app.models.models import PurchaseOrder
    return PurchaseOrder.query.get(pid)


# --- moving average -------------------------------------------------------

def test_first_receipt_sets_the_cost(app, po_setup):
    with app.app_context():
        ProcurementService().receive(_po(po_setup['po_id']),
                                     {po_setup['line_id']: 10},
                                     store_id=po_setup['store_id'])
        assert float(_material(po_setup['material_id']).avg_cost) == 100_000


def test_a_second_receipt_at_a_different_price_blends(app, po_setup):
    """10 @ 100,000 then 10 @ 200,000 averages to 150,000."""
    from app.config import db
    from app.models.models import PurchaseOrder, PurchaseOrderLine

    with app.app_context():
        ProcurementService().receive(_po(po_setup['po_id']),
                                     {po_setup['line_id']: 10},
                                     store_id=po_setup['store_id'])

        po2 = PurchaseOrder(company_id=po_setup["company_id"],
                            supplier_id=_po(po_setup['po_id']).supplier_id,
                            store_id=po_setup["store_id"], po_number="PO-C2",
                            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po2)
        db.session.flush()
        line2 = PurchaseOrderLine(po_id=po2.id,
                                  material_id=po_setup['material_id'],
                                  quantity_ordered=10, unit="m",
                                  unit_price=200_000, line_total=2_000_000)
        db.session.add(line2)
        db.session.commit()

        ProcurementService().receive(po2, {str(line2.id): 10},
                                     store_id=po_setup['store_id'])
        assert float(_material(po_setup['material_id']).avg_cost) == 150_000


def test_a_receipt_with_no_price_does_not_average_in_a_zero(app, po_setup):
    """Averaging in a zero would understate everything afterwards."""
    from app.config import db
    from app.models.models import PurchaseOrderLine

    with app.app_context():
        ProcurementService().receive(_po(po_setup['po_id']),
                                     {po_setup['line_id']: 5},
                                     store_id=po_setup['store_id'])
        before = float(_material(po_setup['material_id']).avg_cost)

        line = PurchaseOrderLine.query.get(po_setup['line_id'])
        line.unit_price = 0
        db.session.commit()

        ProcurementService().receive(_po(po_setup['po_id']),
                                     {po_setup['line_id']: 5},
                                     store_id=po_setup['store_id'])
        assert float(_material(po_setup['material_id']).avg_cost) == before


# --- cost of a job --------------------------------------------------------

@pytest.fixture()
def plan_with_issued_material(app, po_setup):
    """A production plan that has had 4 units issued to it."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, ProductionMaterialLine

    with app.app_context():
        ProcurementService().receive(_po(po_setup['po_id']),
                                     {po_setup['line_id']: 10},
                                     store_id=po_setup['store_id'])

        o = Order(company_id=po_setup["company_id"],
                  store_id=po_setup["store_id"],
                  customer_id=po_setup["customer_id"], order_code="ORD-COST",
                  title="Cost job")
        db.session.add(o)
        db.session.flush()
        c = Contract(company_id=po_setup["company_id"], order_id=o.id,
                     contract_number="CT-COST",
                     contract_date=dt.date(2026, 1, 1),
                     contract_value=3_000_000, is_signed=True,
                     items=[{'name': 'Sofa', 'unit': 'bo', 'quantity': 1,
                             'unit_price': 3_000_000, 'total': 3_000_000}])
        db.session.add(c)
        db.session.commit()

        plan = ProductionPlanService().create_from_contract(c)
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=po_setup['material_id'],
            quantity_required=6, quantity_issued=4, unit="m"))
        db.session.commit()
        return str(plan.id)


def _plan(pid):
    from app.models.models import ProductionPlan
    return ProductionPlan.query.get(pid)


def test_cost_uses_what_was_issued_not_what_was_required(
        app, plan_with_issued_material):
    """Required 6, issued 4 — the business has spent 4 units' worth."""
    with app.app_context():
        cost = ProductionPlanService().material_cost(
            _plan(plan_with_issued_material))
        assert cost['total'] == 400_000, "4 x 100,000, not 6 x 100,000"
        assert cost['complete'] is True


def test_an_unpriced_material_is_reported_not_hidden(app,
                                                     plan_with_issued_material):
    """A total that quietly omits a line is worse than one that says so."""
    from app.config import db
    from app.models.models import Material, ProductionMaterialLine

    with app.app_context():
        plan = _plan(plan_with_issued_material)
        line = plan.material_lines[0]
        Material.query.get(line.material_id).avg_cost = 0
        db.session.commit()

        cost = ProductionPlanService().material_cost(_plan(plan_with_issued_material))
        assert cost['unpriced_lines'] == 1
        assert cost['complete'] is False


def test_margin_is_revenue_minus_material_cost(app, plan_with_issued_material):
    with app.app_context():
        margin = ProductionPlanService().order_margin(
            _plan(plan_with_issued_material))
        assert margin['revenue'] == 3_000_000
        assert margin['material_cost'] == 400_000
        assert margin['gross_margin'] == 2_600_000


def test_margin_states_that_labour_is_excluded(app, plan_with_issued_material):
    """Presenting a material-only figure as profit would flatter every job."""
    with app.app_context():
        margin = ProductionPlanService().order_margin(
            _plan(plan_with_issued_material))
        assert margin['excludes_labour'] is True


def test_margin_uses_the_order_confirmation_when_there_is_no_contract(
        app, po_setup):
    """Revenue must follow whichever document the order was agreed on."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, MasterAgreement, OrderConfirmation, ProductionMaterialLine,
    )

    with app.app_context():
        o = Order(company_id=po_setup["company_id"],
                  store_id=po_setup["store_id"],
                  customer_id=po_setup["customer_id"], order_code="ORD-DDH-C",
                  title="DDH job")
        db.session.add(o)
        db.session.flush()
        c = Contract(company_id=po_setup["company_id"], order_id=o.id,
                     contract_number="CT-TMP",
                     contract_date=dt.date(2026, 1, 1), contract_value=0,
                     items=[{'name': 'Sofa', 'unit': 'bo', 'quantity': 1,
                             'unit_price': 0, 'total': 0}])
        db.session.add(c)
        db.session.flush()
        plan = ProductionPlanService().create_from_contract(c)

        # the order was actually agreed via a DDH, not this draft contract
        c.is_signed = False
        ma = MasterAgreement(company_id=po_setup["company_id"],
                             customer_id=po_setup["customer_id"],
                             agreement_number="HDNT-C",
                             effective_from=dt.date(2026, 1, 1),
                             status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(ma)
        db.session.flush()
        db.session.add(OrderConfirmation(
            company_id=po_setup["company_id"], order_id=o.id,
            master_agreement_id=ma.id, confirmation_number="DDH-C",
            confirmation_date=dt.date(2026, 1, 2), total_amount=5_000_000,
            status=OrderConfirmation.STATUS_CONFIRMED))
        db.session.commit()

        margin = ProductionPlanService().order_margin(_plan(str(plan.id)))
        assert margin['revenue'] == 5_000_000


def test_a_plan_with_nothing_issued_costs_nothing(app, plan_with_issued_material):
    from app.config import db

    with app.app_context():
        plan = _plan(plan_with_issued_material)
        for line in plan.material_lines:
            line.quantity_issued = 0
        db.session.commit()

        cost = ProductionPlanService().material_cost(
            _plan(plan_with_issued_material))
        assert cost['total'] == 0
        assert cost['complete'] is True, (
            "nothing issued is not the same as something unpriced"
        )
