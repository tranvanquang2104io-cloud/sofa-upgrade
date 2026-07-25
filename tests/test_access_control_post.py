"""Access control on state-changing POSTs + role gating + create-flow state machine.

Positive tests assert good behaviour (should pass). xfail tests document
confirmed defects (removed in Phase 5 once fixed).
"""
import pytest


def _make_rival(app):
    """A separate tenant with store + customer; returns their ids."""
    from app.config import db
    from app.models import Company, Store, Customer
    with app.app_context():
        c = Company(company_code="RIVAL", name="Rival", email="r@rival.test")
        db.session.add(c); db.session.flush()
        s = Store(company_id=c.id, store_code="RS1", name="Rival Store")
        db.session.add(s); db.session.flush()
        cust = Customer(company_id=c.id, store_id=s.id, customer_code="RC-1", name="Rival Cust")
        db.session.add(cust); db.session.commit()
        return {"store_id": str(s.id), "customer_id": str(cust.id)}


# --- RBAC (should PASS: verifies gating works) ---------------------------------

def test_staff_cannot_open_company_settings(login, client):
    login(username="staff")  # role == 'user'
    resp = client.get("/settings/company")
    assert resp.status_code == 403


def test_staff_cannot_create_store(login, client):
    login(username="staff")
    resp = client.get("/stores/create")
    assert resp.status_code == 403


# --- B5: cross-tenant order creation (POST IDOR) -------------------------------

@pytest.mark.xfail(strict=False, reason="B5: create_order uses unscoped "
                   "get_by_id and never checks customer.company_id -> a user can "
                   "create an order referencing another tenant's store/customer")
def test_create_order_rejects_cross_tenant_customer(app, client, login):
    login(username="admin")  # ACME company_admin
    rival = _make_rival(app)
    client.post("/orders/create", data={
        "store_id": rival["store_id"],
        "customer_id": rival["customer_id"],
        "order_code": "HACK-1",
        "title": "cross tenant",
    }, follow_redirects=True)
    from app.models import Order
    with app.app_context():
        leaked = Order.query.filter_by(customer_id=rival["customer_id"]).first()
    assert leaked is None, "an order was created against another tenant's customer"


# --- B6: contract created without an approved quotation ------------------------

@pytest.mark.xfail(strict=False, reason="B6: create_contract does not require an "
                   "approved quotation (quotation_id optional, no is_approved check)")
def test_create_contract_requires_approved_quotation(app, client, login, seeded_order):
    login(username="admin")
    client.post(f"/contracts/{seeded_order['order_id']}/create", data={
        "contract_number": "C-1",
        "contract_date": "2026-07-25",
        "item_name[]": ["Work"],
        "item_unit[]": ["job"],
        "item_quantity[]": ["1"],
        "item_price[]": ["1000000"],
    }, follow_redirects=True)
    from app.models import Contract
    with app.app_context():
        c = Contract.query.filter_by(order_id=seeded_order["order_id"]).first()
    assert c is None, "contract created without an approved quotation"
