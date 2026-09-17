"""Procurement lists must paginate and be searchable.

These routes previously returned `.all()` — every purchase order, requisition
and goods receipt the company had ever created, on one page, with no way to
find a specific one. That is fine with a handful of rows and stops being fine
well before a year of real use.
"""
import pytest

PER_PAGE = 20


@pytest.fixture()
def many_pos(app, seed):
    """25 purchase orders — more than one page."""
    from app.config import db
    from app.models.models import PurchaseOrder, Supplier

    with app.app_context():
        sup = Supplier(company_id=seed["company_id"], supplier_code="SUP-L",
                       name="Công ty Vải Sài Gòn")
        other = Supplier(company_id=seed["company_id"], supplier_code="SUP-M",
                         name="Xưởng Gỗ Bình Dương")
        db.session.add_all([sup, other])
        db.session.flush()
        for i in range(25):
            db.session.add(PurchaseOrder(
                company_id=seed["company_id"],
                supplier_id=sup.id if i % 2 == 0 else other.id,
                po_number=f"PO-{i:03d}",
                status=PurchaseOrder.STATUS_DRAFT))
        db.session.commit()
    return seed


def test_po_list_paginates(app, client, login, many_pos):
    from app.services.procurement_service import ProcurementService

    login("admin")
    with app.app_context():
        page1 = ProcurementService().list_pos(many_pos["company_id"], page=1)
        assert page1.total == 25
        assert len(page1.items) == PER_PAGE, "first page must be capped"
        assert page1.has_next

        page2 = ProcurementService().list_pos(many_pos["company_id"], page=2)
        assert len(page2.items) == 5
        assert not page2.has_next


def test_po_list_page_renders_and_does_not_dump_everything(app, client, login,
                                                           many_pos):
    login("admin")
    body = client.get('/purchase-orders').get_data(as_text=True)
    assert body.count('PO-0') <= PER_PAGE * 2, (
        "the first page should not contain all 25 purchase orders"
    )


def test_po_search_by_number(app, login, many_pos):
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        found = ProcurementService().list_pos(many_pos["company_id"],
                                              search="PO-007")
        assert [p.po_number for p in found] == ["PO-007"]


def test_po_search_by_supplier_name(app, many_pos):
    """Searching by who you bought from is the common real-world lookup."""
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        found = ProcurementService().list_pos(many_pos["company_id"],
                                              search="Bình Dương")
        assert len(found) == 12, "the odd-numbered POs belong to that supplier"


def test_po_search_combines_with_the_status_filter(app, many_pos):
    from app.models.models import PurchaseOrder
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        found = ProcurementService().list_pos(
            many_pos["company_id"], status=PurchaseOrder.STATUS_ORDERED,
            search="PO-")
        assert found == [], "no PO is in 'ordered' status yet"


def test_po_search_is_still_tenant_scoped(app, seed, many_pos):
    """A filter must never widen the tenant boundary."""
    from app.config import db
    from app.models.models import Company, PurchaseOrder
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        rival = Company(company_code="RV9", name="Rival", email="r@r.test")
        db.session.add(rival)
        db.session.flush()
        db.session.add(PurchaseOrder(company_id=rival.id, po_number="PO-007",
                                     status=PurchaseOrder.STATUS_DRAFT))
        db.session.commit()

        found = ProcurementService().list_pos(many_pos["company_id"],
                                              search="PO-007")
        assert len(found) == 1
        assert str(found[0].company_id) == str(many_pos["company_id"])


def test_pr_list_paginates(app, seed):
    from app.config import db
    from app.models.models import PurchaseRequisition
    from app.services.requisition_service import RequisitionService

    with app.app_context():
        for i in range(23):
            db.session.add(PurchaseRequisition(
                company_id=seed["company_id"], pr_number=f"PR-{i:03d}",
                status='draft'))
        db.session.commit()

        page1 = RequisitionService().list_prs(seed["company_id"], page=1)
        assert page1.total == 23
        assert len(page1.items) == PER_PAGE


def test_list_without_a_page_still_returns_a_plain_list(app, many_pos):
    """Backward compatibility for any caller that does not paginate."""
    from app.services.procurement_service import ProcurementService

    with app.app_context():
        result = ProcurementService().list_pos(many_pos["company_id"])
        assert isinstance(result, list)
        assert len(result) == 25
