"""End-to-end: drive full order lifecycles through the real HTTP routes.

Covers Order -> Quotation -> approve -> Contract -> sign -> Advance payment ->
Handover -> Final payment -> completed, asserting the lifecycle flags and the
NR3 company_id / D9 extension persistence along the way.
"""


def _first(app, model, **kw):
    with app.app_context():
        obj = model.query.filter_by(**kw).first()
        if obj is not None:
            _ = obj.id  # ensure loaded before detach
        return obj


def _lifecycle(app, order_id):
    from app.models.models import LifecycleStatus
    with app.app_context():
        return LifecycleStatus.query.filter_by(order_id=order_id).first()


def test_full_order_lifecycle_to_completion(app, client, login, seed):
    from app.models.models import Order, Quotation, Contract, HandoverRecord, PaymentReport
    login(username="admin")
    sid, cust = seed["store_id"], seed["customer_id"]

    # 1. Order
    client.post("/orders/create", data={
        "store_id": sid, "customer_id": cust, "order_code": "E2E-1", "title": "Full flow",
    }, follow_redirects=True)
    order = _first(app, Order, order_code="E2E-1")
    assert order is not None, "order not created"
    oid = str(order.id)

    # 2. Quotation + approve
    client.post(f"/quotations/{oid}/create", data={
        "quotation_number": "E2E-Q1", "quotation_date": "2026-07-26", "vat_rate": "10",
        "item_name[]": ["Sofa"], "item_unit[]": ["cái"],
        "item_quantity[]": ["1"], "item_price[]": ["1000000"],
    }, follow_redirects=True)
    q = _first(app, Quotation, quotation_number="E2E-Q1")
    assert q is not None, "quotation not created"
    client.post(f"/quotations/{q.id}/approve", follow_redirects=True)
    assert _lifecycle(app, oid).quotation_approved

    # 3. Contract + sign
    client.post(f"/contracts/{oid}/create", data={
        "contract_number": "E2E-C1", "contract_date": "2026-07-26", "vat_rate": "10",
        "advance_percentage": "30",
        "item_name[]": ["Sofa"], "item_unit[]": ["cái"],
        "item_quantity[]": ["1"], "item_price[]": ["1000000"],
    }, follow_redirects=True)
    c = _first(app, Contract, contract_number="E2E-C1")
    assert c is not None, "contract not created"
    client.post(f"/contracts/{c.id}/sign", follow_redirects=True)
    assert _lifecycle(app, oid).contract_signed
    # Feature 2: signing the contract auto-creates a production plan.
    from app.models.models import ProductionPlan
    with app.app_context():
        assert ProductionPlan.query.filter_by(order_id=oid).first() is not None

    # 4. Advance payment + confirm (allowed once contract is signed)
    client.post(f"/payment/{oid}/create?type=advance", data={
        "report_number": "E2E-PA1", "payment_type": "advance",
        "report_date": "2026-07-26", "payment_date": "2026-07-26",
        "item_name[]": ["Advance"], "item_unit[]": ["lần"],
        "item_quantity[]": ["1"], "item_price[]": ["300000"],
        "advance_percentage": "30", "advance_amount": "0",
    }, follow_redirects=True)
    pa = _first(app, PaymentReport, report_number="E2E-PA1")
    assert pa is not None, "advance payment not created"
    client.post(f"/payment/{pa.id}/confirm", follow_redirects=True)
    assert _lifecycle(app, oid).advance_paid

    # 5. Handover + confirm
    client.post(f"/handover/{oid}/create", data={
        "report_number": "E2E-H1", "report_date": "2026-07-26", "handover_date": "2026-07-26",
        "item_name[]": ["Sofa"], "item_unit[]": ["cái"],
        "item_delivered_qty[]": ["1"], "item_accepted_qty[]": ["1"],
        "item_status[]": ["accepted"], "item_reason[]": [""], "item_price[]": ["1000000"],
    }, follow_redirects=True)
    h = _first(app, HandoverRecord, report_number="E2E-H1")
    assert h is not None, "handover not created"
    client.post(f"/handover/{h.id}/confirm", follow_redirects=True)
    assert _lifecycle(app, oid).handover_confirmed

    # 6. Final payment + confirm (allowed once handover confirmed) -> completed
    client.post(f"/payment/{oid}/create?type=final", data={
        "report_number": "E2E-PF1", "payment_type": "final",
        "report_date": "2026-07-26", "payment_date": "2026-07-26",
        "item_name[]": ["Final"], "item_unit[]": ["lần"],
        "item_quantity[]": ["1"], "item_price[]": ["800000"], "advance_amount": "0",
    }, follow_redirects=True)
    pf = _first(app, PaymentReport, report_number="E2E-PF1")
    assert pf is not None, "final payment not created"
    client.post(f"/payment/{pf.id}/confirm", follow_redirects=True)

    lc = _lifecycle(app, oid)
    assert lc.fully_paid and lc.completed, "order did not reach completion"

    # NR3: company_id was populated on the documents.
    assert str(q.company_id) == seed["company_id"]
    assert str(c.company_id) == seed["company_id"]


def test_order_with_extension_fields_e2e(app, client, login, seed):
    """A second order that uses admin-configured extension fields (D9)."""
    from app.config import db
    from app.models.models import Order, Quotation, Contract, ExtensionFieldConfig
    cid = seed["company_id"]
    with app.app_context():
        db.session.add_all([
            ExtensionFieldConfig(company_id=cid, entity_type="quotation", field_key="extend01",
                                 is_enabled=True, label="PO Number", data_type="text", is_required=True),
            ExtensionFieldConfig(company_id=cid, entity_type="contract", field_key="extend01",
                                 is_enabled=True, label="Warranty (months)", data_type="number"),
        ])
        db.session.commit()

    login(username="admin")
    client.post("/orders/create", data={
        "store_id": seed["store_id"], "customer_id": seed["customer_id"],
        "order_code": "E2E-2", "title": "With extensions",
    }, follow_redirects=True)
    order = _first(app, Order, order_code="E2E-2")
    oid = str(order.id)

    client.post(f"/quotations/{oid}/create", data={
        "quotation_number": "E2E-Q2", "quotation_date": "2026-07-26", "vat_rate": "8",
        "extend01": "PO-2026-777",
        "item_name[]": ["Sofa"], "item_unit[]": ["cái"],
        "item_quantity[]": ["2"], "item_price[]": ["500000"],
    }, follow_redirects=True)
    q = _first(app, Quotation, quotation_number="E2E-Q2")
    assert q is not None and q.extend01 == "PO-2026-777"
    client.post(f"/quotations/{q.id}/approve", follow_redirects=True)

    client.post(f"/contracts/{oid}/create", data={
        "contract_number": "E2E-C2", "contract_date": "2026-07-26", "vat_rate": "8",
        "advance_percentage": "50", "extend01": "24",
        "item_name[]": ["Sofa"], "item_unit[]": ["cái"],
        "item_quantity[]": ["2"], "item_price[]": ["500000"],
    }, follow_redirects=True)
    c = _first(app, Contract, contract_number="E2E-C2")
    assert c is not None and c.extend01 == "24"


def test_order_cancel_e2e(app, client, login, seed):
    """A third order that is canceled before completion."""
    from app.models.models import Order
    login(username="admin")
    client.post("/orders/create", data={
        "store_id": seed["store_id"], "customer_id": seed["customer_id"],
        "order_code": "E2E-3", "title": "To cancel",
    }, follow_redirects=True)
    order = _first(app, Order, order_code="E2E-3")
    assert order is not None and not order.is_canceled
    client.post(f"/orders/{order.id}/cancel", data={"canceled_reason": "customer changed mind"},
                follow_redirects=True)
    cancelled = _first(app, Order, order_code="E2E-3")
    assert cancelled.is_canceled
