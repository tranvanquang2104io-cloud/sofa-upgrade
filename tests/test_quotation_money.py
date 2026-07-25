"""Money / VAT calculation + document-number uniqueness for quotations.

The subtotal/VAT/total math is computed inside the route handler
(`create_quotation` in dashboard_routes.py), so these are exercised over HTTP.
Known bugs are marked xfail(strict=False) so they are documented without
breaking the overnight suite; the xfail markers get removed in Phase 5 once fixed.
"""
import pytest


def _post_quotation(client, order_id, number, items, *, vat_rate=10,
                    shipping=0, another=0, date="2026-07-25"):
    data = {
        "quotation_number": number,
        "quotation_date": date,
        "vat_rate": str(vat_rate),
        "shipping_fee": str(shipping),
        "another_fee": str(another),
        "validity_days": "30",
        "item_name[]": [i[0] for i in items],
        "item_unit[]": [i[1] for i in items],
        "item_quantity[]": [str(i[2]) for i in items],
        "item_price[]": [str(i[3]) for i in items],
    }
    return client.post(f"/quotations/{order_id}/create", data=data,
                       follow_redirects=True)


def _get_quotation(app, number):
    from app.models import Quotation
    with app.app_context():
        return Quotation.query.filter_by(quotation_number=number).first()


def test_quotation_totals_are_correct(app, client, login, seeded_order):
    login(username="admin")
    _post_quotation(client, seeded_order["order_id"], "Q-001",
                    items=[("Fabric", "m", 2, 100000)],
                    vat_rate=10, shipping=30000, another=5000)
    q = _get_quotation(app, "Q-001")
    assert q is not None, "quotation was not created"
    assert float(q.subtotal) == 200000.0
    assert float(q.vat_amount) == 20000.0        # 200000 * 10%
    assert float(q.total_amount) == 255000.0     # 200000 + 20000 + 30000 + 5000


def test_quotation_multi_item_subtotal(app, client, login, seeded_order):
    login(username="admin")
    _post_quotation(client, seeded_order["order_id"], "Q-002",
                    items=[("Foam", "pc", 3, 50000), ("Legs", "set", 1, 120000)],
                    vat_rate=8)
    q = _get_quotation(app, "Q-002")
    assert q is not None
    assert float(q.subtotal) == 270000.0         # 150000 + 120000
    assert float(q.vat_amount) == 21600.0        # 270000 * 8%
    assert float(q.total_amount) == 291600.0


def test_negative_quantity_is_rejected(app, client, login, seeded_order):
    login(username="admin")
    _post_quotation(client, seeded_order["order_id"], "Q-NEG",
                    items=[("Fabric", "m", -2, 100000)])
    q = _get_quotation(app, "Q-NEG")
    # DESIRED: rejected (no quotation) or clamped to >= 0. CURRENT: created negative.
    assert q is None or float(q.subtotal) >= 0


@pytest.mark.xfail(strict=False, reason="B3/P2: document numbers are globally "
                   "unique instead of per-tenant (dashboard_routes.py:591 & model)")
def test_same_quotation_number_allowed_across_tenants(app, client, login, seeded_order):
    # Tenant A (ACME) uses Q-DUP.
    login(username="admin")
    _post_quotation(client, seeded_order["order_id"], "Q-DUP",
                    items=[("Fabric", "m", 1, 100000)])
    assert _get_quotation(app, "Q-DUP") is not None

    # Build tenant B with its own admin + order.
    from app.config import db
    from app.models import Company, Store, User, Customer, Order
    with app.app_context():
        b = Company(company_code="BETA", name="Beta Sofa", email="b@beta.test")
        db.session.add(b); db.session.flush()
        bs = Store(company_id=b.id, store_code="B1", name="Beta Store")
        db.session.add(bs); db.session.flush()
        ba = User(company_id=b.id, username="badmin", email="ba@beta.test",
                  full_name="Beta Admin", role="company_admin")
        ba.set_password("secret123")
        bc = Customer(company_id=b.id, store_id=bs.id, customer_code="BC-1", name="Beta Cust")
        db.session.add_all([ba, bc]); db.session.flush()
        bo = Order(company_id=b.id, store_id=bs.id, customer_id=bc.id,
                   order_code="BORD-1", title="Beta order")
        db.session.add(bo); db.session.commit()
        b_order_id = str(bo.id)

    # Tenant B logs in and tries the SAME number — should be allowed (per-tenant).
    login(username="badmin", company_code="BETA")
    _post_quotation(client, b_order_id, "Q-DUP",
                    items=[("Fabric", "m", 1, 100000)])
    from app.models import Quotation
    with app.app_context():
        count = Quotation.query.filter_by(quotation_number="Q-DUP").count()
    assert count == 2, "tenant B could not reuse a number already used by tenant A"
