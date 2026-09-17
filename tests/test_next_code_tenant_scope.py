"""`/api/next-code/<doc_type>` must derive the next number from the CALLER's
company only.

Finding (2026-09): `get_next_code` loaded `company_id` but never applied it to
the MAX(number) query, so the suggested next code was computed across *all*
tenants. That both leaks volume information about other companies and makes a
tenant's own numbering jump unpredictably when an unrelated company creates a
document.
"""
import datetime as dt

import pytest


@pytest.fixture()
def rival_with_high_numbers(app, seed):
    """A second company holding documents with very high numbers (QT-900...).

    ACME (the seeded tenant) has none, so a correctly scoped lookup must
    suggest QT-001 regardless of what RIVAL holds.
    """
    from app.config import db
    from app.models import Company, Store, User, Customer, Order
    from app.models.models import Quotation, Contract

    with app.app_context():
        c = Company(company_code="RIVAL2", name="Rival Sofa 2", email="x@rival2.test")
        db.session.add(c)
        db.session.flush()
        s = Store(company_id=c.id, store_code="RS2", name="Rival Store 2")
        db.session.add(s)
        db.session.flush()
        u = User(company_id=c.id, store_id=s.id, username="rival2",
                 email="u@rival2.test", full_name="Rival User 2", role="user")
        u.set_password("secret123")
        cust = Customer(company_id=c.id, store_id=s.id,
                        customer_code="R2CUST-001", name="Rival Customer 2")
        db.session.add_all([u, cust])
        db.session.flush()
        order = Order(company_id=c.id, store_id=s.id, customer_id=cust.id,
                      order_code="R2ORD-001", title="Rival Order 2")
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(company_id=c.id, order_id=order.id,
                                 quotation_number="QT-900",
                                 quotation_date=dt.date(2026, 1, 1),
                                 total_amount=0))
        db.session.add(Contract(company_id=c.id, order_id=order.id,
                                contract_number="CT-900",
                                contract_date=dt.date(2026, 1, 1),
                                contract_value=0))
        db.session.commit()
        return {"company_id": str(c.id)}


@pytest.mark.parametrize("doc_type,prefix", [("quotation", "QT-"), ("contract", "CT-")])
def test_next_code_ignores_other_tenants(client, login, rival_with_high_numbers,
                                         doc_type, prefix):
    """ACME has no documents, so the next code must be 001 — not 901."""
    login("admin")

    resp = client.get(f"/api/next-code/{doc_type}")
    assert resp.status_code == 200, resp.data

    next_code = resp.get_json()["next_code"]
    assert next_code == f"{prefix}001", (
        f"cross-tenant leak: {doc_type} suggested {next_code!r}; the other "
        f"company's {prefix}900 must not influence this tenant's numbering"
    )


def test_next_code_uses_own_tenant_maximum(app, client, login, seed,
                                           rival_with_high_numbers):
    """With its own QT-007, ACME must be offered QT-008."""
    from app.config import db
    from app.models import Order
    from app.models.models import Quotation

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-NC1",
                      title="Numbering order")
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(company_id=seed["company_id"], order_id=order.id,
                                 quotation_number="QT-007",
                                 quotation_date=dt.date(2026, 1, 2),
                                 total_amount=0))
        db.session.commit()

    login("admin")
    resp = client.get("/api/next-code/quotation")
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["next_code"] == "QT-008"


def test_check_code_ignores_other_tenants(client, login, rival_with_high_numbers):
    """A number used by ANOTHER company must not be reported as taken.

    Document numbers are unique per company (AUDIT D8), so RIVAL2 holding
    QT-900 must not stop ACME from using QT-900.
    """
    login("admin")

    resp = client.post("/api/check-code/quotation", json={"code": "QT-900"})
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["exists"] is False, (
        "cross-tenant leak: another company's QT-900 was reported as already "
        "existing for this tenant"
    )


def test_check_code_still_detects_own_duplicate(app, client, login, seed):
    """The check must still catch a genuine duplicate inside the company."""
    from app.config import db
    from app.models import Order
    from app.models.models import Quotation

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-NC2",
                      title="Dup order")
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(company_id=seed["company_id"], order_id=order.id,
                                 quotation_number="QT-055",
                                 quotation_date=dt.date(2026, 1, 3),
                                 total_amount=0))
        db.session.commit()

    login("admin")
    resp = client.post("/api/check-code/quotation", json={"code": "QT-055"})
    assert resp.status_code == 200, resp.data
    assert resp.get_json()["exists"] is True
