"""The two edit screens the missing-screen triage justified.

The brief said not to add CRUD everywhere, so this is deliberately narrow:
only the gaps where the absence actually blocks a real correction.

Order edit: there was NO way to edit an order at all, so a typo in the title
was permanent — and that title prints on every document generated from the
order.

Agreement edit: I shipped create + view without it, which left a draft
agreement that could not be corrected.
"""
import datetime as dt

import pytest

from app.models.models import MasterAgreement


@pytest.fixture()
def order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-EDIT",
                  title="Sofa 3 cho da bo", description="ban dau")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id))
        db.session.commit()
        return str(o.id)


# --- order edit -----------------------------------------------------------

def test_order_edit_page_renders(client, login, order):
    login("admin")
    resp = client.get(f'/orders/{order}/edit')
    assert resp.status_code == 200
    assert 'Sofa 3 cho da bo' in resp.get_data(as_text=True)


def test_a_typo_in_the_order_title_can_be_corrected(app, client, login, order):
    """The whole point: this was impossible before."""
    from app.models import Order

    login("admin")
    client.post(f'/orders/{order}/edit', data={
        'title': 'Sofa 3 cho da bo that',
        'description': 'da sua',
        'notes': 'ghi chu',
    }, follow_redirects=True)

    with app.app_context():
        o = Order.query.get(order)
        assert o.title == 'Sofa 3 cho da bo that'
        assert o.description == 'da sua'


def test_order_edit_refuses_an_empty_title(app, client, login, order):
    from app.models import Order

    login("admin")
    client.post(f'/orders/{order}/edit', data={'title': '   '},
                follow_redirects=True)

    with app.app_context():
        assert Order.query.get(order).title == 'Sofa 3 cho da bo'


def test_order_edit_cannot_change_the_money(app, client, login, order):
    """Amounts are derived from the order's documents, not typed here."""
    from app.models import Order

    login("admin")
    client.post(f'/orders/{order}/edit', data={
        'title': 'Still fine',
        'total_amount': '999999999',
        'customer_id': 'something-else',
    }, follow_redirects=True)

    with app.app_context():
        o = Order.query.get(order)
        assert float(o.total_amount or 0) == 0, "posted total must be ignored"


def test_a_canceled_order_cannot_be_edited(app, client, login, order):
    from app.config import db
    from app.models import Order

    with app.app_context():
        o = Order.query.get(order)
        o.is_canceled = True
        db.session.commit()

    login("admin")
    resp = client.get(f'/orders/{order}/edit', follow_redirects=True)
    assert 'name="title"' not in resp.get_data(as_text=True)


def test_order_edit_is_tenant_scoped(app, client, login, seed):
    from app.config import db
    from app.models import Company, Customer, Order, Store

    with app.app_context():
        c = Company(company_code="OE", name="Other", email="o@oe.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="OES", name="S")
        db.session.add(st)
        db.session.flush()
        cu = Customer(company_id=c.id, store_id=st.id, customer_code="OEC",
                      name="C")
        db.session.add(cu)
        db.session.flush()
        o = Order(company_id=c.id, store_id=st.id, customer_id=cu.id,
                  order_code="ZZOTHERORD", title="Theirs")
        db.session.add(o)
        db.session.commit()
        other_id = str(o.id)

    login("admin")
    client.post(f'/orders/{other_id}/edit', data={'title': 'HACKED'},
                follow_redirects=True)

    with app.app_context():
        assert Order.query.get(other_id).title == 'Theirs'


# --- agreement edit -------------------------------------------------------

@pytest.fixture()
def agreement(app, seed):
    from app.config import db

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-EDIT-1",
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_DRAFT, penalty_pct=8)
        db.session.add(ma)
        db.session.commit()
        return str(ma.id)


def test_agreement_edit_page_renders_with_values(client, login, agreement):
    login("admin")
    body = client.get(f'/agreements/{agreement}/edit').get_data(as_text=True)
    assert 'HDNT-EDIT-1' in body


def test_a_draft_agreement_can_be_corrected(app, client, login, seed, agreement):
    login("admin")
    client.post(f'/agreements/{agreement}/edit', data={
        'agreement_number': 'HDNT-EDIT-1B',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-02-01',
        'penalty_pct': '5',
        'payment_terms': 'Thanh toan trong 45 ngay',
    }, follow_redirects=True)

    with app.app_context():
        ma = MasterAgreement.query.get(agreement)
        assert ma.agreement_number == 'HDNT-EDIT-1B'
        assert float(ma.penalty_pct) == 5
        assert ma.payment_terms == 'Thanh toan trong 45 ngay'


def test_edit_still_enforces_the_legal_penalty_cap(app, client, login, seed,
                                                   agreement):
    """The cap must hold on edit as well as on create."""
    login("admin")
    client.post(f'/agreements/{agreement}/edit', data={
        'agreement_number': 'HDNT-EDIT-1',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-01-01',
        'penalty_pct': '25',
    }, follow_redirects=True)

    with app.app_context():
        assert float(MasterAgreement.query.get(agreement).penalty_pct) == 8


def test_edit_refuses_a_number_another_agreement_already_uses(
        app, client, login, seed, agreement):
    from app.config import db

    with app.app_context():
        other = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-TAKEN",
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_DRAFT)
        db.session.add(other)
        db.session.commit()

    login("admin")
    client.post(f'/agreements/{agreement}/edit', data={
        'agreement_number': 'HDNT-TAKEN',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-01-01',
    }, follow_redirects=True)

    with app.app_context():
        assert MasterAgreement.query.get(agreement).agreement_number == 'HDNT-EDIT-1'


def test_a_terminated_agreement_cannot_be_rewritten(app, client, login, seed,
                                                    agreement):
    """Orders were issued citing its terms; history must not be edited."""
    from app.config import db

    with app.app_context():
        ma = MasterAgreement.query.get(agreement)
        ma.status = MasterAgreement.STATUS_TERMINATED
        db.session.commit()

    login("admin")
    client.post(f'/agreements/{agreement}/edit', data={
        'agreement_number': 'HDNT-REWRITTEN',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-01-01',
    }, follow_redirects=True)

    with app.app_context():
        assert MasterAgreement.query.get(agreement).agreement_number == 'HDNT-EDIT-1'
