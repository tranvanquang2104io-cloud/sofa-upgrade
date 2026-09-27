"""The receive screen asked where twice, and the answer that counted was hidden.

`po_view.html` had two selects for one question. "Nhap vao kho" (a warehouse)
sat above the quantity table, with the note *"Ton kho se tang o kho nay"*.
"Into Store" (a branch) sat below it, far enough away that nobody would read
them as the same question.

Stock increases by `store_id`. The warehouse only LABELLED the receipt. So the
note was false, and I wrote it: a storeman who picked the fabric warehouse and
left the branch select alone put the delivery wherever the branch box happened
to point, while the screen told him it had gone to the warehouse he chose.

That is the worst kind of stock error. It does not error, it does not look
wrong, and it is found weeks later by somebody standing in front of a shelf
that disagrees with the system.

One question now. When the company has warehouses, the warehouse select is the
only control and the BRANCH IS DERIVED FROM IT -- not the other way round,
because `MaterialStock` is still keyed by (material, store), so the warehouse
is the finer answer and the branch follows from it. A company that has not
been migrated to warehouses yet still sees a branch select, because it has no
warehouses to choose from and receiving has to keep working: deployments
upgrade code and database separately.

The second half is T-05, and it is the same screen: `store_id` arrived raw
from the form and was written straight onto the stock row. `@store_admin_required`
only establishes that somebody is an admin of SOME branch.
"""
import datetime as dt

import pytest


@pytest.fixture()
def po_with_warehouses(app, seed):
    """A purchase order, two branches, and a warehouse in each."""
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Store, Supplier, Warehouse,
    )

    with app.app_context():
        far = Store(company_id=seed['company_id'], store_code='CH-FAR2',
                    name='Chi nhanh Long An', is_active=True)
        db.session.add(far)
        db.session.flush()

        here = Warehouse(company_id=seed['company_id'],
                         store_id=seed['store_id'], warehouse_code='KHO-HERE',
                         name='Kho chinh', is_active=True, is_default=True)
        there = Warehouse(company_id=seed['company_id'], store_id=far.id,
                          warehouse_code='KHO-THERE', name='Kho Long An',
                          is_active=True)
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-1', name='Cong ty vai',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-R', name='Vai nhung do',
                            is_active=True)
        db.session.add_all([here, there, supplier, material])
        db.session.flush()

        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'],
                           supplier_id=supplier.id, po_number='PO-RCV',
                           order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id, material_id=material.id,
                                 quantity_ordered=10, unit='m',
                                 unit_price=100_000)
        db.session.add(line)
        db.session.commit()

        return {**seed, 'po_id': str(po.id), 'line_id': str(line.id),
                'far_store_id': str(far.id), 'here_id': str(here.id),
                'there_id': str(there.id), 'material_id': str(material.id)}


def _stock(app, material_id, store_id):
    from app.models.models import MaterialStock

    with app.app_context():
        row = MaterialStock.query.filter_by(material_id=material_id,
                                            store_id=store_id).first()
        return float(row.current_quantity) if row else 0.0


def test_the_chosen_warehouse_decides_which_branch_stock_increases_at(
        app, po_with_warehouses):
    """Pick the far warehouse; the far branch's stock is what goes up.

    Before, the warehouse was a label and the branch select decided. Choosing
    the far warehouse while the branch box still said the near branch put the
    goods in the near branch, under a note saying otherwise.
    """
    from app.models.models import GoodsReceipt, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        po = PurchaseOrder.query.get(po_with_warehouses['po_id'])
        gr, _ = ProcurementService().receive(
            po, {po_with_warehouses['line_id']: '10'},
            warehouse_id=po_with_warehouses['there_id'])
        gr_id = str(gr.id)

    assert _stock(app, po_with_warehouses['material_id'],
                  po_with_warehouses['far_store_id']) == 10, (
        'the goods did not arrive at the branch whose warehouse was chosen')
    assert _stock(app, po_with_warehouses['material_id'],
                  po_with_warehouses['store_id']) == 0, (
        "the goods arrived at the PO's branch instead of the chosen warehouse")

    with app.app_context():
        assert str(GoodsReceipt.query.get(gr_id).warehouse_id) == \
            po_with_warehouses['there_id']


def test_the_screen_asks_where_exactly_once(app, client, login,
                                            po_with_warehouses):
    """Two controls for one question is how the wrong one gets left alone."""
    login('admin')
    body = client.get(
        f"/purchase-orders/{po_with_warehouses['po_id']}").get_data(
            as_text=True)

    assert body.count('name="warehouse_id"') == 1, (
        'the warehouse select is missing or duplicated')
    assert 'name="store_id"' not in body, (
        'the branch select is still on the screen alongside the warehouse '
        'select, so the two can still disagree')


def test_a_company_without_warehouses_can_still_receive(app, seed):
    """Code and database are deployed separately; receiving must not stop."""
    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        supplier = Supplier(company_id=seed['company_id'],
                            supplier_code='NCC-2', name='NCC hai',
                            is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-N', name='Vai nau',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=seed['company_id'],
                           store_id=seed['store_id'], supplier_id=supplier.id,
                           po_number='PO-NOWH', order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id, material_id=material.id,
                                 quantity_ordered=5, unit='m',
                                 unit_price=50_000)
        db.session.add(line)
        db.session.commit()
        material_id, line_id = str(material.id), str(line.id)

        ProcurementService().receive(po, {line_id: '5'})

    assert _stock(app, material_id, seed['store_id']) == 5, (
        'a company with no warehouses could not receive goods at all')


# --- T-05: the raw store_id -------------------------------------------------

def test_a_branch_from_another_company_is_refused_not_substituted(
        app, po_with_warehouses):
    """`store_id` came straight off the form onto the stock row.

    Refused rather than quietly replaced with a default: silently receiving
    into somewhere nobody named is how stock ends up in a place no one can
    explain later.
    """
    from app.config import db
    from app.models.models import Company, PurchaseOrder, Store
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        other = Company(company_code='OTHER2', name='Cong ty khac',
                        email='o2@test', is_active=True)
        db.session.add(other)
        db.session.flush()
        foreign = Store(company_id=other.id, store_code='CH-Z', name='CH Z',
                        is_active=True)
        db.session.add(foreign)
        db.session.commit()
        foreign_id = str(foreign.id)

        po = PurchaseOrder.query.get(po_with_warehouses['po_id'])
        with pytest.raises(ValueError):
            ProcurementService().receive(
                po, {po_with_warehouses['line_id']: '10'},
                store_id=foreign_id)

    assert _stock(app, po_with_warehouses['material_id'], foreign_id) == 0, (
        "stock was written into another company's branch")


def test_a_warehouse_from_another_company_is_still_refused(
        app, po_with_warehouses):
    """This already held; it must keep holding once the branch derives from it."""
    from app.config import db
    from app.models.models import Company, PurchaseOrder, Store, Warehouse
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        other = Company(company_code='OTHER3', name='Cong ty ba',
                        email='o3@test', is_active=True)
        db.session.add(other)
        db.session.flush()
        store = Store(company_id=other.id, store_code='CH-W', name='CH W',
                      is_active=True)
        db.session.add(store)
        db.session.flush()
        foreign_wh = Warehouse(company_id=other.id, store_id=store.id,
                               warehouse_code='KHO-Z', name='Kho Z',
                               is_active=True)
        db.session.add(foreign_wh)
        db.session.commit()

        po = PurchaseOrder.query.get(po_with_warehouses['po_id'])
        with pytest.raises(ValueError):
            ProcurementService().receive(
                po, {po_with_warehouses['line_id']: '10'},
                warehouse_id=str(foreign_wh.id))


def test_setting_stock_by_hand_checks_the_branch_too(app, seed):
    """`update_material_stock` is the other raw `store_id` T-05 named.

    `MaterialService.update_stock` checked that the MATERIAL belonged to the
    caller's company and stopped there. The branch came off the form and went
    onto the stock row. Setting a figure by hand is already the event that
    most needs explaining later; doing it to a branch you are not in is worse.
    """
    from app.config import db
    from app.models.models import Company, Material, Store
    from app.services.services import MaterialService

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-H', name='Vai tay',
                            is_active=True)
        other = Company(company_code='OTHER4', name='Cong ty bon',
                        email='o4@test', is_active=True)
        db.session.add_all([material, other])
        db.session.flush()
        foreign = Store(company_id=other.id, store_code='CH-Q', name='CH Q',
                        is_active=True)
        db.session.add(foreign)
        db.session.commit()

        with pytest.raises(ValueError):
            MaterialService().update_stock(
                str(material.id), seed['company_id'],
                store_id=str(foreign.id), quantity=50)


def test_setting_stock_in_your_own_branch_still_works(app, seed):
    """The ordinary case; a check that blocks real work is not a check."""
    from app.config import db
    from app.models.models import Material
    from app.services.services import MaterialService

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-K', name='Vai kem',
                            is_active=True)
        db.session.add(material)
        db.session.commit()

        material_id = str(material.id)
        MaterialService().update_stock(
            material_id, seed['company_id'],
            store_id=seed['store_id'], quantity=42)

    assert _stock(app, material_id, seed['store_id']) == 42
