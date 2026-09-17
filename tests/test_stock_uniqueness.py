"""Stock rows must be unique per (material, location).

`MaterialStock` already declares
``UniqueConstraint('material_id', 'store_id')``, so this looked covered. It is
not: ``store_id`` is NULLable and SQL treats two NULLs as DISTINCT, so the
constraint never applies to company-level (main-warehouse) rows.

That matters because `ProcurementService.receive()` locates the row with
``.first()``. With two company-level rows for one material, a goods receipt
increments whichever row comes back first while a reader may see the other —
stock silently disagrees with itself, with no error anywhere.
"""
import pytest


@pytest.fixture()
def material(app, seed):
    from app.config import db
    from app.models.models import Material, MaterialCategory, MaterialUnit

    with app.app_context():
        unit = MaterialUnit(company_id=seed["company_id"], name="mét")
        cat = MaterialCategory(company_id=seed["company_id"], name="Vải")
        db.session.add_all([unit, cat])
        db.session.flush()
        m = Material(company_id=seed["company_id"], material_code="MAT-S1",
                     name="Vải test", unit_id=unit.id, category_id=cat.id)
        db.session.add(m)
        db.session.commit()
        return {"material_id": str(m.id), **seed}


def test_duplicate_company_level_stock_rows_are_rejected(app, material):
    """THE GAP: store_id IS NULL rows were not covered by the constraint."""
    from app.config import db
    from app.models.models import MaterialStock

    with app.app_context():
        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=None, current_quantity=10))
        db.session.commit()

        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=None, current_quantity=99))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()

        rows = MaterialStock.query.filter_by(
            material_id=material["material_id"], store_id=None).count()
        assert rows == 1, (
            "a material may hold only one company-level stock row; duplicates "
            "make receive()'s .first() lookup non-deterministic"
        )


def test_duplicate_store_level_stock_rows_are_rejected(app, material):
    """The non-NULL case, which the original constraint did cover."""
    from app.config import db
    from app.models.models import MaterialStock

    with app.app_context():
        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=material["store_id"],
                                     current_quantity=5))
        db.session.commit()

        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=material["store_id"],
                                     current_quantity=7))
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()


def test_company_level_and_store_level_rows_may_coexist(app, material):
    """Different locations are legitimately different rows."""
    from app.config import db
    from app.models.models import MaterialStock

    with app.app_context():
        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=None, current_quantity=10))
        db.session.add(MaterialStock(material_id=material["material_id"],
                                     company_id=material["company_id"],
                                     store_id=material["store_id"],
                                     current_quantity=5))
        db.session.commit()

        assert MaterialStock.query.filter_by(
            material_id=material["material_id"]).count() == 2


# --- a purchase order cannot be sent to nobody ---------------------------

def test_po_without_a_supplier_cannot_be_submitted(app, seed):
    """supplier_id stays nullable so a PO can be drafted before the supplier
    is chosen — but sending it, and later invoicing it, both need one."""
    from app.config import db
    from app.models.models import PurchaseOrder
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        po = PurchaseOrder(company_id=seed["company_id"], po_number="PO-NOSUP",
                           status=PurchaseOrder.STATUS_DRAFT, supplier_id=None)
        db.session.add(po)
        db.session.commit()

        with pytest.raises(ValueError, match='nhà cung cấp'):
            ProcurementService().transition(po, 'submit')

        assert po.status == PurchaseOrder.STATUS_DRAFT, "must stay a draft"


def test_po_with_a_supplier_submits_normally(app, seed):
    from app.config import db
    from app.models.models import PurchaseOrder, Supplier
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        sup = Supplier(company_id=seed["company_id"], supplier_code="SUP-OK",
                       name="NCC Tốt")
        db.session.add(sup)
        db.session.flush()
        po = PurchaseOrder(company_id=seed["company_id"], po_number="PO-SUP",
                           status=PurchaseOrder.STATUS_DRAFT, supplier_id=sup.id)
        db.session.add(po)
        db.session.commit()

        ProcurementService().transition(po, 'submit')
        assert po.status == PurchaseOrder.STATUS_ORDERED
