"""Tenant-isolation / IDOR probes (suspected High finding P7).

A logged-in user of company ACME must never be able to read another company's
resources by guessing/knowing its UUID. These tests assert a 403 (or at least
NOT a 200 leaking data). If they fail, that confirms a broken-access-control
vulnerability (OWASP A01).
"""
import uuid

import pytest


@pytest.fixture()
def other_tenant(app):
    """A second, unrelated company with its own store + customer + order."""
    from app.config import db
    from app.models import Company, Store, User, Customer, Order

    with app.app_context():
        c = Company(company_code="RIVAL", name="Rival Sofa", email="x@rival.test")
        db.session.add(c)
        db.session.flush()
        s = Store(company_id=c.id, store_code="RS1", name="Rival Store")
        db.session.add(s)
        db.session.flush()
        u = User(company_id=c.id, store_id=s.id, username="rivaluser",
                 email="u@rival.test", full_name="Rival User", role="user")
        u.set_password("secret123")
        cust = Customer(company_id=c.id, store_id=s.id,
                        customer_code="RCUST-001", name="Rival Customer")
        db.session.add_all([u, cust])
        db.session.flush()
        order = Order(company_id=c.id, store_id=s.id, customer_id=cust.id,
                      order_code="RORD-001", title="Rival Order")
        db.session.add(order)
        db.session.commit()
        return {"company_id": str(c.id), "customer_id": str(cust.id),
                "order_id": str(order.id)}


def _assert_not_leaked(resp, label):
    assert resp.status_code != 200, (
        f"IDOR: {label} returned 200 — cross-tenant data leaked "
        f"(expected 403/redirect)"
    )


def test_admin_cannot_read_other_company_customer(login, client, other_tenant):
    login(username="admin")
    resp = client.get(f"/customers/{other_tenant['customer_id']}",
                      follow_redirects=False)
    _assert_not_leaked(resp, "GET /customers/<rival_id> as company_admin")


def test_staff_cannot_read_other_company_customer(login, client, other_tenant):
    login(username="staff")
    resp = client.get(f"/customers/{other_tenant['customer_id']}",
                      follow_redirects=False)
    _assert_not_leaked(resp, "GET /customers/<rival_id> as staff")


def test_staff_cannot_read_other_company_order(login, client, other_tenant):
    login(username="staff")
    resp = client.get(f"/orders/{other_tenant['order_id']}",
                      follow_redirects=False)
    _assert_not_leaked(resp, "GET /orders/<rival_id> as staff")


def test_unknown_id_does_not_500(login, client):
    """A random non-existent UUID should 404/redirect, not crash with 500."""
    login(username="admin")
    resp = client.get(f"/customers/{uuid.uuid4()}", follow_redirects=False)
    assert resp.status_code != 500, "Unknown customer id crashed with 500"
