"""The HĐNT screens: list, create, view, status changes and the price list."""
import datetime as dt

import pytest

from app.models.models import MasterAgreement


@pytest.fixture()
def agreement(app, seed):
    from app.config import db

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-UI-001",
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_DRAFT)
        db.session.add(ma)
        db.session.commit()
        return str(ma.id)


def test_list_page_renders(client, login, agreement):
    login("admin")
    resp = client.get('/agreements')
    assert resp.status_code == 200
    assert 'HDNT-UI-001' in resp.get_data(as_text=True)


def test_create_page_renders(client, login):
    login("admin")
    assert client.get('/agreements/create').status_code == 200


def test_view_page_renders(client, login, agreement):
    login("admin")
    resp = client.get(f'/agreements/{agreement}')
    assert resp.status_code == 200


def test_create_agreement_through_the_form(app, client, login, seed):
    login("admin")
    resp = client.post('/agreements/create', data={
        'agreement_number': 'HDNT-NEW-1',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-01-01',
        'penalty_pct': '8',
        'payment_terms': 'Thanh toán trong 30 ngày',
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        created = MasterAgreement.query.filter_by(
            agreement_number='HDNT-NEW-1').first()
        assert created is not None
        assert created.status == MasterAgreement.STATUS_DRAFT, (
            "a new agreement starts as a draft, not immediately binding"
        )


def test_penalty_above_the_legal_cap_is_refused(app, client, login, seed):
    """LTM 2005 Đ.301 caps a contractual penalty at 8%."""
    login("admin")
    client.post('/agreements/create', data={
        'agreement_number': 'HDNT-BAD-PENALTY',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-01-01',
        'penalty_pct': '20',
    }, follow_redirects=True)

    with app.app_context():
        assert MasterAgreement.query.filter_by(
            agreement_number='HDNT-BAD-PENALTY').first() is None


def test_duplicate_agreement_number_is_refused(app, client, login, seed,
                                               agreement):
    login("admin")
    client.post('/agreements/create', data={
        'agreement_number': 'HDNT-UI-001',
        'customer_id': seed["customer_id"],
        'effective_from': '2026-02-01',
    }, follow_redirects=True)

    with app.app_context():
        assert MasterAgreement.query.filter_by(
            agreement_number='HDNT-UI-001').count() == 1


def test_activate_then_suspend_through_the_page(app, client, login, agreement):
    login("admin")

    client.post(f'/agreements/{agreement}/status', data={'action': 'activate'},
                follow_redirects=True)
    with app.app_context():
        assert MasterAgreement.query.get(agreement).status == 'active'

    client.post(f'/agreements/{agreement}/status',
                data={'action': 'suspend', 'reason': 'Công nợ quá hạn'},
                follow_redirects=True)
    with app.app_context():
        ma = MasterAgreement.query.get(agreement)
        assert ma.status == 'suspended'
        assert 'Công nợ quá hạn' in (ma.notes or '')


def test_adding_a_price_closes_the_previous_line(app, client, login, agreement):
    """A revision must not overwrite history."""
    from app.models.models import MasterAgreementPriceLine

    login("admin")
    client.post(f'/agreements/{agreement}/prices', data={
        'product_name': 'Sofa 3 chỗ', 'agreed_unit_price': '9000000',
        'effective_from': '2026-01-01'}, follow_redirects=True)
    client.post(f'/agreements/{agreement}/prices', data={
        'product_name': 'Sofa 3 chỗ', 'agreed_unit_price': '9500000',
        'effective_from': '2026-06-01'}, follow_redirects=True)

    with app.app_context():
        lines = MasterAgreementPriceLine.query.filter_by(
            agreement_id=agreement).order_by(
            MasterAgreementPriceLine.effective_from).all()
        assert len(lines) == 2, "the old price must be kept, not replaced"
        assert lines[0].effective_to == dt.date(2026, 6, 1), (
            "the superseded line should be closed on the new line's start date"
        )
        assert lines[1].effective_to is None


def test_price_line_needs_a_price_or_a_discount(app, client, login, agreement):
    from app.models.models import MasterAgreementPriceLine

    login("admin")
    client.post(f'/agreements/{agreement}/prices',
                data={'product_name': 'Ghế'}, follow_redirects=True)

    with app.app_context():
        assert MasterAgreementPriceLine.query.filter_by(
            agreement_id=agreement).count() == 0


def test_agreements_are_tenant_scoped(app, client, login, seed, agreement):
    """Another company's agreement must not be readable by id."""
    from app.config import db
    from app.models.models import Company, Customer, Store

    with app.app_context():
        rival = Company(company_code="RVA", name="Rival", email="r@rva.test")
        db.session.add(rival)
        db.session.flush()
        store = Store(company_id=rival.id, store_code="RVS", name="Rival Store")
        db.session.add(store)
        db.session.flush()
        cust = Customer(company_id=rival.id, store_id=store.id,
                        customer_code="RC1", name="RC")
        db.session.add(cust)
        db.session.flush()
        theirs = MasterAgreement(company_id=rival.id, customer_id=cust.id,
                                 agreement_number="HDNT-RIVAL",
                                 effective_from=dt.date(2026, 1, 1))
        db.session.add(theirs)
        db.session.commit()
        theirs_id = str(theirs.id)

    login("admin")
    resp = client.get(f'/agreements/{theirs_id}', follow_redirects=True)
    assert 'HDNT-RIVAL' not in resp.get_data(as_text=True)
