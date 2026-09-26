"""Every change to stock leaves a line saying what happened and why.

`MaterialStock.current_quantity` is a bare number. When it is wrong — and with
more than one warehouse it will be — there is nothing to look at. Nobody can
say whether 3m is what is left after a job, what arrived short, or what
somebody typed by hand on a Tuesday. "Why does this warehouse say 3m?" becomes
a weekly question the moment a company has two, and today the system cannot
answer it at all.

So each change writes a movement: which material, which branch, how much (signed
— positive in, negative out), what kind of event, and which document caused it.
The stock figure stays where it is and stays authoritative; the movements are
the account of how it got there.

Two things this is NOT:

* not double-entry. A receipt is one line in one place, not a pair between
  a supplier location and a warehouse. The second half would be an accounting
  apparatus nobody in a workshop reads;
* not a recomputation. The movements do not replace `current_quantity`, and
  nothing derives the balance by summing them — that would turn a fast read
  into a scan and make a missing movement corrupt the stock figure rather than
  just the explanation of it.

The invariant worth having is the weaker, useful one: **the movements for a
material and branch add up to what the stock row says**, for stock that this
system changed. It is checked here for the three events that change it.
"""
import datetime as dt

import pytest


@pytest.fixture()
def warehouse_and_material(app, seed):
    from app.config import db
    from app.models import Store
    from app.models.models import (
        Material, MaterialStock, Supplier, Warehouse,
    )

    with app.app_context():
        workshop = Store(company_id=seed['company_id'], store_code='XUONG-H',
                         name='Xưởng Hoài Đức', is_active=True)
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-H', name='Vải Thiên Hà',
                            is_active=True)
        db.session.add_all([workshop, supplier])
        db.session.flush()
        here = Warehouse(company_id=seed['company_id'],
                         store_id=seed['store_id'], warehouse_code='W-H1',
                         name='Kho showroom', is_default=True, is_active=True)
        there = Warehouse(company_id=seed['company_id'],
                          store_id=workshop.id, warehouse_code='W-H2',
                          name='Kho xưởng', is_default=True, is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-H', name='Vải bố',
                            is_active=True)
        db.session.add_all([here, there, material])
        db.session.flush()
        db.session.add(MaterialStock(
            company_id=seed['company_id'], material_id=material.id,
            store_id=seed['store_id'], current_quantity=50))
        db.session.commit()
        return {**seed, 'workshop_id': str(workshop.id),
                'supplier_id': str(supplier.id),
                'material_id': str(material.id),
                'from_warehouse_id': str(here.id),
                'to_warehouse_id': str(there.id)}


def _movements(material_id, store_id=None):
    from app.models.models import StockMovement

    query = StockMovement.query.filter_by(material_id=material_id)
    if store_id is not None:
        query = query.filter_by(store_id=store_id)
    return query.order_by(StockMovement.created_at).all()


def test_a_transfer_writes_a_line_on_each_side(app, warehouse_and_material):
    from app.services.transfers import transfer_stock

    with app.app_context():
        transfer = transfer_stock(
            company_id=warehouse_and_material['company_id'],
            from_warehouse_id=warehouse_and_material['from_warehouse_id'],
            to_warehouse_id=warehouse_and_material['to_warehouse_id'],
            lines=[{'material_id': warehouse_and_material['material_id'],
                    'quantity': 20, 'unit': 'm'}],
            transfer_date=dt.date(2026, 9, 26),
            notes='Chuyển sang xưởng để cắt')

        out = _movements(warehouse_and_material['material_id'],
                         warehouse_and_material['store_id'])
        into = _movements(warehouse_and_material['material_id'],
                          warehouse_and_material['workshop_id'])
        assert len(out) == 1 and len(into) == 1, (
            'a transfer moved stock in two places and left one account or '
            'none')
        assert float(out[0].quantity) == -20
        assert float(into[0].quantity) == 20
        assert out[0].ref_id == transfer.id, (
            'the movement does not say which document caused it, so the '
            'history explains nothing')


def test_a_goods_receipt_writes_one(app, warehouse_and_material):
    from app.config import db
    from app.models.models import PurchaseOrder, PurchaseOrderLine
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        po = PurchaseOrder(
            company_id=warehouse_and_material['company_id'],
            supplier_id=warehouse_and_material['supplier_id'],
            store_id=warehouse_and_material['store_id'], po_number='PO-H',
            order_date=dt.date(2026, 9, 1),
            status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(
            po_id=po.id, material_id=warehouse_and_material['material_id'],
            quantity_ordered=15, unit='m', unit_price=215_000)
        db.session.add(line)
        db.session.commit()

        gr, _warnings = ProcurementService().receive(po, {str(line.id): 15})
        db.session.commit()

        moves = _movements(warehouse_and_material['material_id'],
                           warehouse_and_material['store_id'])
        assert len(moves) == 1
        assert float(moves[0].quantity) == 15
        assert moves[0].ref_id == gr.id


def test_issuing_writes_a_negative_one(app, warehouse_and_material):
    from app.config import db
    from app.models import Order
    from app.models.models import ProductionMaterialLine, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        order = Order(company_id=warehouse_and_material['company_id'],
                      store_id=warehouse_and_material['store_id'],
                      customer_id=warehouse_and_material['customer_id'],
                      order_code='DH-H', title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        plan = ProductionPlan(company_id=warehouse_and_material['company_id'],
                              order_id=order.id, plan_number='KH-H')
        db.session.add(plan)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, material_id=warehouse_and_material['material_id'],
            quantity_required=12, unit='m'))
        db.session.commit()

        ProductionPlanService().issue_materials(
            ProductionPlan.query.get(plan.id))

        moves = _movements(warehouse_and_material['material_id'],
                           warehouse_and_material['store_id'])
        assert len(moves) == 1
        assert float(moves[0].quantity) == -12
        assert moves[0].ref_id == plan.id


def test_the_movements_add_up_to_the_stock_figure(app, warehouse_and_material):
    """The useful invariant: the account explains the balance.

    Not by deriving it — `current_quantity` stays authoritative and nothing
    sums movements to read stock. But what this system changed must be
    accounted for, or the history is decoration.
    """
    from app.config import db
    from app.models.models import MaterialStock
    from app.services.services import MaterialService
    from app.services.transfers import transfer_stock

    with app.app_context():
        opening = 50.0
        transfer_stock(
            company_id=warehouse_and_material['company_id'],
            from_warehouse_id=warehouse_and_material['from_warehouse_id'],
            to_warehouse_id=warehouse_and_material['to_warehouse_id'],
            lines=[{'material_id': warehouse_and_material['material_id'],
                    'quantity': 20, 'unit': 'm'}],
            transfer_date=dt.date(2026, 9, 26))

        row = MaterialStock.query.filter_by(
            material_id=warehouse_and_material['material_id'],
            store_id=warehouse_and_material['store_id']).one()
        moved = sum(float(m.quantity) for m in _movements(
            warehouse_and_material['material_id'],
            warehouse_and_material['store_id']))
        assert opening + moved == float(row.current_quantity)


def test_a_hand_adjustment_is_accounted_for_too(app, warehouse_and_material):
    """The one people reach for when something is wrong, and the one that
    most needs a reason written on it."""
    from app.config import db
    from app.models.models import StockMovement
    from app.services.services import MaterialService

    with app.app_context():
        MaterialService().update_stock(
            warehouse_and_material['material_id'],
            warehouse_and_material['company_id'],
            warehouse_and_material['store_id'], 44)
        db.session.commit()

        moves = _movements(warehouse_and_material['material_id'],
                           warehouse_and_material['store_id'])
        assert len(moves) == 1, (
            'somebody set the quantity by hand and nothing records that they '
            'did')
        assert float(moves[0].quantity) == -6, (
            '50 became 44, so the movement is -6 — a movement recording the '
            'NEW TOTAL rather than the change would not add up')
        assert moves[0].movement_type == StockMovement.TYPE_ADJUST


def test_the_history_is_readable_on_the_material_screen(app, client, login,
                                                        warehouse_and_material):
    """A ledger nobody can read is a ledger that only costs writes.

    Six times in this programme finished work sat unreachable. This one was
    write-only when it was first committed.
    """
    from app.config import db
    from app.services.services import MaterialService

    with app.app_context():
        MaterialService().update_stock(
            warehouse_and_material['material_id'],
            warehouse_and_material['company_id'],
            warehouse_and_material['store_id'], 44)
        db.session.commit()

    login('admin')
    body = client.get(
        f"/materials/{warehouse_and_material['material_id']}").get_data(
        as_text=True)
    assert 'Lịch sử tồn kho' in body, (
        'the movements are recorded and no screen shows them')
    assert '-6' in body, (
        'the change is not on the screen, so the history explains nothing')


def test_a_material_with_no_history_says_why_it_is_empty(app, client, login,
                                                         warehouse_and_material):
    """"Nothing here" must not read as "nothing ever happened".

    Movements before this feature existed were not backfilled, deliberately —
    inventing them would be worse than their absence. The screen has to say so,
    or an empty panel on an old material looks like a missing record.
    """
    login('admin')
    body = client.get(
        f"/materials/{warehouse_and_material['material_id']}").get_data(
        as_text=True)
    assert 'Chỉ ghi từ khi tính năng này được bật' in body
