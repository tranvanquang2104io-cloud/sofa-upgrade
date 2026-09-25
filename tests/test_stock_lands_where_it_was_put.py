"""Goods received at a branch must increase that branch's stock, not somebody else's.

`ProcurementService.receive()` looked for a stock row for the receiving branch
and, **when it did not find one**, fell through to the company-level row
(`store_id IS NULL`) and added the quantity there:

    st = MaterialStock.query.filter_by(material_id=..., store_id=target).first()
    if st is None and target is not None:
        st = MaterialStock.query.filter_by(material_id=..., store_id=None).first()

So the first delivery of a material to a new branch does not appear at that
branch at all. It appears in the company warehouse, silently, and every screen
afterwards agrees with each other and disagrees with the shelf.

The issuing side had the same shape (`_stock_for`), so the two halves were
consistent in being wrong together: material issued at the branch also drew
from the company row. With one location that is invisible. With two it is an
undocumented transfer between warehouses, which is precisely what makes an
inventory stop being worth reading.

On the RECEIVING side there is no good reason for it. A material that has never
been at this branch has zero there — the honest answer, and the one that makes
the first delivery create the row instead of hiding in another.

On the ISSUING side there is, today. `MaterialService` creates every new
material's stock row at company level, so that is where all stock currently is;
removing the fallback there would make every issue read zero and stop
production on the first day. Receive first, then issue: stock needs a way of
arriving at the right warehouse before drawing from the right one can be
required. The last test in this file pins that, so it fails and asks the
question once the warehouse resolution lands.
"""
import datetime as dt

import pytest


@pytest.fixture()
def two_branches(app, seed):
    """A company warehouse holding stock, and a branch holding none."""
    from app.config import db
    from app.models import Store
    from app.models.models import Material, MaterialStock, Supplier

    with app.app_context():
        branch = Store(company_id=seed['company_id'], store_code='XUONG',
                       name='Xưởng Hoài Đức', is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-BO', name='Vải bố',
                            is_active=True)
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-K', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add_all([branch, material, supplier])
        db.session.flush()
        # The company-level row the fallback used to reach for.
        db.session.add(MaterialStock(
            company_id=seed['company_id'], material_id=material.id,
            store_id=None, current_quantity=100))
        db.session.commit()
        return {**seed, 'branch_id': str(branch.id),
                'material_id': str(material.id),
                'supplier_id': str(supplier.id)}


def _ordered_po(app, fixture, quantity=20):
    from app.config import db
    from app.models.models import PurchaseOrder, PurchaseOrderLine

    with app.app_context():
        po = PurchaseOrder(
            company_id=fixture['company_id'],
            supplier_id=fixture['supplier_id'],
            store_id=fixture['branch_id'], po_number='PO-KHO',
            order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id,
                                 material_id=fixture['material_id'],
                                 quantity_ordered=quantity, unit='m',
                                 unit_price=215_000)
        db.session.add(line)
        db.session.commit()
        return str(po.id), str(line.id)


def test_a_first_delivery_to_a_branch_lands_at_that_branch(app, two_branches):
    from app.config import db
    from app.models.models import MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id = _ordered_po(app, two_branches)
    with app.app_context():
        po = PurchaseOrder.query.get(po_id)
        ProcurementService().receive(po, {line_id: 20})
        db.session.commit()

        at_branch = MaterialStock.query.filter_by(
            material_id=two_branches['material_id'],
            store_id=two_branches['branch_id']).first()
        assert at_branch is not None, (
            'the delivery created no stock row for the branch it arrived at')
        assert float(at_branch.current_quantity) == 20


def test_the_company_warehouse_is_not_credited_with_it(app, two_branches):
    """The half that makes the figures lie: 100 must still be 100."""
    from app.config import db
    from app.models.models import MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id = _ordered_po(app, two_branches)
    with app.app_context():
        po = PurchaseOrder.query.get(po_id)
        ProcurementService().receive(po, {line_id: 20})
        db.session.commit()

        company_level = MaterialStock.query.filter_by(
            material_id=two_branches['material_id'], store_id=None).one()
        assert float(company_level.current_quantity) == 100, (
            'stock delivered to the workshop was added to the company '
            'warehouse instead, so both figures now disagree with the shelf')


def test_the_total_is_still_right(app, two_branches):
    """Both halves together: nothing was lost, it is just in the right place."""
    from app.config import db
    from app.models.models import Material, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id = _ordered_po(app, two_branches)
    with app.app_context():
        po = PurchaseOrder.query.get(po_id)
        ProcurementService().receive(po, {line_id: 20})
        db.session.commit()

        material = Material.query.get(two_branches['material_id'])
        assert float(material.total_stock) == 120


def test_a_second_delivery_adds_to_the_row_it_made(app, two_branches):
    """The fix must not create a new row per delivery."""
    from app.config import db
    from app.models.models import MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id = _ordered_po(app, two_branches, quantity=40)
    with app.app_context():
        po = PurchaseOrder.query.get(po_id)
        ProcurementService().receive(po, {line_id: 20})
        db.session.commit()
        ProcurementService().receive(po, {line_id: 15})
        db.session.commit()

        rows = MaterialStock.query.filter_by(
            material_id=two_branches['material_id'],
            store_id=two_branches['branch_id']).all()
        assert len(rows) == 1, (
            f'{len(rows)} stock rows for one material at one branch; a reader '
            'sees one of them and a receipt increments another')
        assert float(rows[0].current_quantity) == 35


def test_the_issuing_fallback_is_gone_too(app):
    """Both halves of the same defect are fixed now.

    This test used to pin the issuing fallback as deliberate, on the grounds
    that `MaterialService` puts all stock at company level so removing it would
    stop production on day one. That was wrong, and measuring said so: with the
    fallback taken out, exactly one test in the suite failed — this one.

    `create_material` in the service does create only the company-level row,
    but the ROUTE then calls `ensure_stock_entries_for_stores`, which creates
    one per branch. I read one layer and concluded about the system, which is
    the same mistake as every "checked by name" defect in this programme —
    except this one reached a commit message (e2042b2).

    The real gap was a branch opened AFTER the materials exist, which had no
    rows at all. `StoreService.create_store` now makes them, at zero, and
    `tests/test_a_new_branch_can_hold_stock.py` pins that.
    """
    import inspect

    from app.services import services

    source = inspect.getsource(services.ProductionPlanService._stock_for)
    assert 'store_id=None' not in source, (
        'issuing can draw from the company warehouse again, so a branch can '
        'take material no document says was moved there')
