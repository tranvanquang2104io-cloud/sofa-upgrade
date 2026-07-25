"""Per-tenant contract numbers (W6b/B3): two companies can reuse a number."""


def _make_company(app, code):
    from app.config import db
    from app.models import Company, Store, User, Customer, Order
    with app.app_context():
        c = Company(company_code=code, name=code, email=f"{code}@t.test")
        db.session.add(c); db.session.flush()
        s = Store(company_id=c.id, store_code=f"{code}-S", name="Store")
        db.session.add(s); db.session.flush()
        u = User(company_id=c.id, username=f"{code}admin", email=f"a@{code}.test",
                 full_name="Admin", role="company_admin")
        u.set_password("secret123")
        cust = Customer(company_id=c.id, store_id=s.id, customer_code=f"{code}-C", name="Cust")
        db.session.add_all([u, cust]); db.session.flush()
        o = Order(company_id=c.id, store_id=s.id, customer_id=cust.id,
                  order_code=f"{code}-O", title="order")
        db.session.add(o); db.session.commit()
        return {"code": code, "admin": f"{code}admin", "order_id": str(o.id)}


def _post_contract(client, order_id, number):
    return client.post(f"/contracts/{order_id}/create", data={
        "contract_number": number,
        "contract_date": "2026-07-26",
        "item_name[]": ["Work"], "item_unit[]": ["job"],
        "item_quantity[]": ["1"], "item_price[]": ["1000000"],
    }, follow_redirects=True)


def test_same_contract_number_allowed_across_tenants(app, client, login):
    a = _make_company(app, "AAA")
    b = _make_company(app, "BBB")

    login(username=a["admin"], company_code="AAA")
    _post_contract(client, a["order_id"], "C-DUP")

    login(username=b["admin"], company_code="BBB")
    _post_contract(client, b["order_id"], "C-DUP")

    from app.models import Contract
    with app.app_context():
        assert Contract.query.filter_by(contract_number="C-DUP").count() == 2, \
            "tenant B could not reuse a contract number used by tenant A"
