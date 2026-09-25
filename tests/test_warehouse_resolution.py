"""Which warehouse a document means — and when not to ask at all.

The product has to hold two things at once. A workshop with one address must
see no new field anywhere: its screens should look exactly as they did before
warehouses existed. A company that later separates its shop, its workshop and
its store must be able to say, per goods receipt and per material line, where
the stock is.

The rule that does both without a setting: **ask only when there is more than
one warehouse**. Creating the second warehouse is what turns the question on,
and that is an act with a meaning in the business. A checkbox in Settings would
be a question put to somebody who does not have the problem yet — and it can
disagree with the data, which is worse: create a second warehouse, forget the
checkbox, and every receipt keeps landing in the first one while every screen
stays silent about it.

Also pinned: a warehouse id belonging to another company is refused rather than
quietly replaced with this company's default. Substituting would put stock
somewhere nobody asked for, which is the exact failure the whole separation
exists to prevent — the silent company-level fallback in another costume.
"""
import pytest


@pytest.fixture()
def one_warehouse(app, seed):
    from app.config import db
    from app.models.models import Warehouse

    with app.app_context():
        warehouse = Warehouse(company_id=seed['company_id'],
                              store_id=seed['store_id'],
                              warehouse_code='KHO-1', name='Kho Showroom',
                              is_default=True, is_active=True)
        db.session.add(warehouse)
        db.session.commit()
        return {**seed, 'warehouse_id': str(warehouse.id)}


@pytest.fixture()
def two_warehouses(app, one_warehouse):
    from app.config import db
    from app.models import Store
    from app.models.models import Warehouse

    with app.app_context():
        workshop = Store(company_id=one_warehouse['company_id'],
                         store_code='XUONG', name='Xưởng Hoài Đức',
                         is_active=True)
        db.session.add(workshop)
        db.session.flush()
        second = Warehouse(company_id=one_warehouse['company_id'],
                           store_id=workshop.id, warehouse_code='KHO-2',
                           name='Kho Xưởng', is_default=False, is_active=True)
        db.session.add(second)
        db.session.commit()
        return {**one_warehouse, 'workshop_id': str(workshop.id),
                'second_warehouse_id': str(second.id)}


# --------------------------------------------------------------------------
# Do not ask a question the company does not have.
# --------------------------------------------------------------------------

def test_one_warehouse_means_no_field_on_any_screen(app, one_warehouse):
    from app.services.warehouses import must_choose

    with app.app_context():
        assert must_choose(one_warehouse['company_id']) is False


def test_a_company_with_no_warehouse_yet_is_not_asked_either(app, seed):
    """Before the migration has run, or on a brand-new company."""
    from app.services.warehouses import must_choose

    with app.app_context():
        assert must_choose(seed['company_id']) is False


def test_the_second_warehouse_turns_the_question_on(app, two_warehouses):
    """No setting: the act of creating it is what does this."""
    from app.services.warehouses import must_choose

    with app.app_context():
        assert must_choose(two_warehouses['company_id']) is True


def test_a_deactivated_warehouse_does_not_count(app, two_warehouses):
    """Closing one must put the screens back the way they were."""
    from app.config import db
    from app.models.models import Warehouse
    from app.services.warehouses import must_choose

    with app.app_context():
        second = Warehouse.query.get(two_warehouses['second_warehouse_id'])
        second.is_active = False
        db.session.commit()
        assert must_choose(two_warehouses['company_id']) is False


# --------------------------------------------------------------------------
# The cascade.
# --------------------------------------------------------------------------

def test_a_document_at_a_location_uses_that_location_s_warehouse(
        app, two_warehouses):
    from app.services.warehouses import resolve

    with app.app_context():
        chosen = resolve(two_warehouses['company_id'],
                         store_id=two_warehouses['workshop_id'])
        assert str(chosen.id) == two_warehouses['second_warehouse_id'], (
            'a receipt at the workshop resolved to the showroom warehouse')


def test_what_the_user_chose_beats_the_location_default(app, two_warehouses):
    """Somebody naming a warehouse has said what the defaults cannot know."""
    from app.services.warehouses import resolve

    with app.app_context():
        chosen = resolve(two_warehouses['company_id'],
                         chosen_id=two_warehouses['warehouse_id'],
                         store_id=two_warehouses['workshop_id'])
        assert str(chosen.id) == two_warehouses['warehouse_id']


def test_a_location_with_no_warehouse_of_its_own_uses_the_company_default(
        app, two_warehouses):
    """A branch that sells but stores nothing still has to receive goods."""
    from app.config import db
    from app.models import Store
    from app.services.warehouses import resolve

    with app.app_context():
        kiosk = Store(company_id=two_warehouses['company_id'],
                      store_code='KIOSK', name='Quầy Vincom', is_active=True)
        db.session.add(kiosk)
        db.session.commit()

        chosen = resolve(two_warehouses['company_id'], store_id=kiosk.id)
        assert str(chosen.id) == two_warehouses['warehouse_id'], (
            'a location without a warehouse resolved to nothing, which blocks '
            'the work rather than protecting anything')


def test_a_warehouse_from_another_company_is_refused_not_substituted(
        app, two_warehouses):
    """Substituting would put stock somewhere nobody asked for."""
    from app.config import db
    from app.models import Company, Store
    from app.models.models import Warehouse
    from app.services.warehouses import resolve

    with app.app_context():
        other = Company(company_code='OTHER', name='Xưởng khác',
                        email='o@b.test')
        db.session.add(other)
        db.session.flush()
        other_store = Store(company_id=other.id, store_code='S',
                            name='Cơ sở', is_active=True)
        db.session.add(other_store)
        db.session.flush()
        theirs = Warehouse(company_id=other.id, store_id=other_store.id,
                           warehouse_code='KHO-X', name='Kho của họ',
                           is_default=True, is_active=True)
        db.session.add(theirs)
        db.session.commit()

        with pytest.raises(ValueError):
            resolve(two_warehouses['company_id'], chosen_id=str(theirs.id))


def test_several_warehouses_with_no_default_returns_nothing_to_guess_with(
        app, two_warehouses):
    """Better to ask than to pick one and put the stock somewhere nobody chose."""
    from app.config import db
    from app.models.models import Warehouse
    from app.services.warehouses import default_for_company

    with app.app_context():
        first = Warehouse.query.get(two_warehouses['warehouse_id'])
        first.is_default = False
        db.session.commit()
        assert default_for_company(two_warehouses['company_id']) is None


# --------------------------------------------------------------------------
# The wire: a receipt records the warehouse, and the stock row it touches
# carries it too.
# --------------------------------------------------------------------------

def _po_at(app, fixture, store_id, quantity=20):
    import datetime as dt

    from app.config import db
    from app.models.models import (
        Material, PurchaseOrder, PurchaseOrderLine, Supplier,
    )

    with app.app_context():
        supplier = Supplier(company_id=fixture['company_id'],
                            supplier_code='NCC-W', name='Vải Thiên Hà',
                            is_active=True)
        material = Material(company_id=fixture['company_id'],
                            material_code='VAI-W', name='Vải bố',
                            is_active=True)
        db.session.add_all([supplier, material])
        db.session.flush()
        po = PurchaseOrder(company_id=fixture['company_id'],
                           supplier_id=supplier.id, store_id=store_id,
                           po_number='PO-W', order_date=dt.date(2026, 9, 1),
                           status=PurchaseOrder.STATUS_ORDERED)
        db.session.add(po)
        db.session.flush()
        line = PurchaseOrderLine(po_id=po.id, material_id=material.id,
                                 quantity_ordered=quantity, unit='m',
                                 unit_price=215_000)
        db.session.add(line)
        db.session.commit()
        return str(po.id), str(line.id), str(material.id)


def test_a_receipt_records_which_warehouse_took_the_goods(app, two_warehouses):
    from app.config import db
    from app.models.models import GoodsReceipt, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id, _ = _po_at(app, two_warehouses,
                               two_warehouses['workshop_id'])
    with app.app_context():
        ProcurementService().receive(PurchaseOrder.query.get(po_id),
                                     {line_id: 20})
        db.session.commit()

        gr = GoodsReceipt.query.filter_by(po_id=po_id).one()
        assert gr.warehouse_id is not None, (
            'the receipt says which branch took delivery and not where the '
            'goods went — the stock row becomes the only record of it')
        assert str(gr.warehouse_id) == two_warehouses['second_warehouse_id']


def test_the_stock_row_carries_the_warehouse_too(app, two_warehouses):
    """Otherwise the receipt and the stock disagree about where things are."""
    from app.config import db
    from app.models.models import MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id, material_id = _po_at(app, two_warehouses,
                                         two_warehouses['workshop_id'])
    with app.app_context():
        ProcurementService().receive(PurchaseOrder.query.get(po_id),
                                     {line_id: 20})
        db.session.commit()

        row = MaterialStock.query.filter_by(material_id=material_id).one()
        assert str(row.warehouse_id) == two_warehouses['second_warehouse_id']


def test_a_company_with_one_warehouse_still_receives_normally(app,
                                                              one_warehouse):
    """The common case must not need anybody to choose anything."""
    from app.config import db
    from app.models.models import GoodsReceipt, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id, _ = _po_at(app, one_warehouse, one_warehouse['store_id'])
    with app.app_context():
        ProcurementService().receive(PurchaseOrder.query.get(po_id),
                                     {line_id: 20})
        db.session.commit()

        gr = GoodsReceipt.query.filter_by(po_id=po_id).one()
        assert str(gr.warehouse_id) == one_warehouse['warehouse_id']


def test_a_company_with_no_warehouses_receives_exactly_as_before(app, seed):
    """Before the migration runs, nothing may break.

    A deployment upgrades code and database separately, and a company that has
    not been migrated yet has no warehouses at all. Receiving has to keep
    working, writing no warehouse rather than refusing.
    """
    from app.config import db
    from app.models.models import GoodsReceipt, MaterialStock, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    po_id, line_id, material_id = _po_at(app, seed, seed['store_id'])
    with app.app_context():
        ProcurementService().receive(PurchaseOrder.query.get(po_id),
                                     {line_id: 20})
        db.session.commit()

        gr = GoodsReceipt.query.filter_by(po_id=po_id).one()
        assert gr.warehouse_id is None
        row = MaterialStock.query.filter_by(material_id=material_id).one()
        assert float(row.current_quantity) == 20, (
            'the delivery was refused or lost because no warehouse existed')
