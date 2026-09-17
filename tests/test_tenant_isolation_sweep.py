"""A sweep of EVERY detail route against another tenant's record id.

The existing isolation tests probe customers and orders only. The repository's
default lookup (`BaseRepository.get_by_id`) is unscoped — it is a plain
`query.get(id)` — so tenant safety depends entirely on each route remembering
to check ownership. That is a property worth measuring across the whole
surface rather than assuming, because a single forgetful route is a data leak.

Each probe asks: logged in as ACME, can I read RIVAL's record by id?
A pass means the route refused (403 / redirect) or at least did not render the
other tenant's identifying data.
"""
import datetime as dt

import pytest


@pytest.fixture()
def rival(app):
    """A second company with one of everything, each carrying a marker string."""
    from app.config import db
    from app.models import Company, Customer, Order, Store, User
    from app.models.models import (
        Contract, GoodsReceipt, HandoverRecord, LifecycleStatus, Material,
        MaterialCategory, MaterialUnit, MasterAgreement, PaymentReport,
        PurchaseOrder, PurchaseRequisition, Quotation, Supplier,
        SupplierInvoice,
    )

    with app.app_context():
        c = Company(company_code="SWEEP", name="Rival Sweep Co",
                    email="s@sweep.test")
        db.session.add(c)
        db.session.flush()
        s = Store(company_id=c.id, store_code="SWS", name="Sweep Store")
        db.session.add(s)
        db.session.flush()
        u = User(company_id=c.id, store_id=s.id, username="sweepuser",
                 email="u@sweep.test", full_name="Sweep User", role="user")
        u.set_password("secret123")
        cust = Customer(company_id=c.id, store_id=s.id,
                        customer_code="SWEEP-CUST", name="ZZMARKERCUST")
        db.session.add_all([u, cust])
        db.session.flush()

        order = Order(company_id=c.id, store_id=s.id, customer_id=cust.id,
                      order_code="ZZMARKERORD", title="Rival sweep order")
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))

        q = Quotation(company_id=c.id, order_id=order.id,
                      quotation_number="ZZMARKERQT",
                      quotation_date=dt.date(2026, 1, 1), total_amount=0)
        ct = Contract(company_id=c.id, order_id=order.id,
                      contract_number="ZZMARKERCT",
                      contract_date=dt.date(2026, 1, 1), contract_value=0)
        hr = HandoverRecord(company_id=c.id, order_id=order.id,
                            report_number="ZZMARKERHR",
                            report_date=dt.date(2026, 1, 1),
                            handover_date=dt.date(2026, 1, 1))
        pr_rep = PaymentReport(company_id=c.id, order_id=order.id,
                               report_number="ZZMARKERPM",
                               report_date=dt.date(2026, 1, 1),
                               payment_date=dt.date(2026, 1, 1),
                               payment_type='advance', amount=0)
        db.session.add_all([q, ct, hr, pr_rep])

        unit = MaterialUnit(company_id=c.id, name="sweepunit")
        cat = MaterialCategory(company_id=c.id, name="sweepcat")
        sup = Supplier(company_id=c.id, supplier_code="SWSUP",
                       name="ZZMARKERSUP")
        db.session.add_all([unit, cat, sup])
        db.session.flush()
        mat = Material(company_id=c.id, material_code="ZZMARKERMAT",
                       name="ZZMARKERMATNAME", unit_id=unit.id,
                       category_id=cat.id)
        db.session.add(mat)
        db.session.flush()

        po = PurchaseOrder(company_id=c.id, supplier_id=sup.id,
                           po_number="ZZMARKERPO",
                           status=PurchaseOrder.STATUS_RECEIVED)
        pr = PurchaseRequisition(company_id=c.id, pr_number="ZZMARKERPR",
                                 status='draft')
        db.session.add_all([po, pr])
        db.session.flush()
        gr = GoodsReceipt(company_id=c.id, po_id=po.id,
                          gr_number="ZZMARKERGR")
        ma = MasterAgreement(company_id=c.id, customer_id=cust.id,
                             agreement_number="ZZMARKERMA",
                             effective_from=dt.date(2026, 1, 1))
        inv = SupplierInvoice(company_id=c.id, supplier_id=sup.id, po_id=po.id,
                              invoice_number="ZZMARKERINV",
                              invoice_date=dt.date(2026, 1, 1), total_amount=0)
        db.session.add_all([gr, ma, inv])
        db.session.commit()

        return {
            'customer': str(cust.id), 'order': str(order.id),
            'quotation': str(q.id), 'contract': str(ct.id),
            'handover': str(hr.id), 'payment': str(pr_rep.id),
            'material': str(mat.id), 'po': str(po.id), 'pr': str(pr.id),
            'gr': str(gr.id), 'agreement': str(ma.id), 'invoice': str(inv.id),
        }


# (url template, key into the rival fixture, marker that must not appear)
PROBES = [
    ('/customers/{customer}', 'customer', 'ZZMARKERCUST'),
    ('/orders/{order}', 'order', 'ZZMARKERORD'),
    ('/quotations/{quotation}/view', 'quotation', 'ZZMARKERQT'),
    ('/contracts/{contract}/view', 'contract', 'ZZMARKERCT'),
    ('/handover/{handover}', 'handover', 'ZZMARKERHR'),
    ('/payment/{payment}', 'payment', 'ZZMARKERPM'),
    ('/materials/{material}', 'material', 'ZZMARKERMATNAME'),
    ('/purchase-orders/{po}', 'po', 'ZZMARKERPO'),
    ('/requisitions/{pr}', 'pr', 'ZZMARKERPR'),
    ('/goods-receipts/{gr}', 'gr', 'ZZMARKERGR'),
    ('/agreements/{agreement}', 'agreement', 'ZZMARKERMA'),
    ('/supplier-invoices/{invoice}', 'invoice', 'ZZMARKERINV'),
    ('/api/quotations/{quotation}', 'quotation', 'ZZMARKERQT'),
    ('/api/contracts/{contract}', 'contract', 'ZZMARKERCT'),
]


@pytest.mark.parametrize("url_tpl,key,marker",
                         PROBES, ids=[p[0] for p in PROBES])
def test_detail_route_does_not_leak_another_tenant(client, login, rival,
                                                   url_tpl, key, marker):
    login("admin")
    url = url_tpl.format(**rival)
    resp = client.get(url, follow_redirects=True)

    body = resp.get_data(as_text=True)
    assert marker not in body, (
        f"TENANT LEAK: {url} rendered another company's record "
        f"(marker {marker!r} found in the response)"
    )


@pytest.mark.parametrize("url_tpl,key,marker",
                         PROBES, ids=[p[0] for p in PROBES])
def test_detail_route_does_not_500_on_a_foreign_id(client, login, rival,
                                                   url_tpl, key, marker):
    """Refusing is fine; crashing is not — a 500 leaks a stack trace."""
    login("admin")
    resp = client.get(url_tpl.format(**rival), follow_redirects=False)
    assert resp.status_code < 500, f"{url_tpl} returned {resp.status_code}"


# --- the repository-level safe default -----------------------------------

def test_base_repository_offers_a_tenant_scoped_lookup(app, seed, rival):
    """New code should have a safe lookup available without inventing one."""
    from app.repositories.repository import OrderRepository

    with app.app_context():
        repo = OrderRepository()

        # Another tenant's order is invisible through the scoped lookup...
        assert repo.get_for_company(rival['order'], seed['company_id']) is None
        # ...while the unscoped default happily returns it, which is exactly
        # why the scoped one exists.
        assert repo.get_by_id(rival['order']) is not None


def test_scoped_lookup_returns_our_own_record(app, seed):
    from app.config import db
    from app.models import Order
    from app.repositories.repository import OrderRepository

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='ORD-SCOPE',
                  title='Mine')
        db.session.add(o)
        db.session.commit()
        found = OrderRepository().get_for_company(str(o.id), seed['company_id'])
        assert found is not None
        assert found.order_code == 'ORD-SCOPE'


def test_scoped_lookup_refuses_a_model_without_company_id(app):
    """Fail loudly rather than silently returning an unscoped result."""
    import pytest as _pytest
    from app.repositories.repository import LifecycleStatusRepository

    with app.app_context():
        with _pytest.raises(AttributeError, match='company_id'):
            LifecycleStatusRepository().get_for_company('x', 'y')
