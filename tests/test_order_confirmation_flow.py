"""Issuing an ĐƠN ĐẶT HÀNG from the order page.

This is where feature 4.3 becomes reachable to a user: an order whose customer
has an active HĐNT no longer asks for a whole new contract.
"""
import datetime as dt

import pytest

from app.models.models import MasterAgreement, OrderConfirmation


@pytest.fixture()
def order_with_approved_quotation(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus, Quotation

    items = [{'name': 'Sofa 3 cho', 'unit': 'bo', 'quantity': 2,
              'unit_price': 10_000_000, 'total': 20_000_000}]
    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-DDH",
                      title="Order under framework agreement")
        db.session.add(order)
        db.session.flush()
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order.id,
            quotation_number="QT-DDH", quotation_date=dt.date(2026, 6, 1),
            items=items, subtotal=20_000_000, vat_rate=8, vat_amount=1_600_000,
            total_amount=21_600_000, is_approved=True))
        db.session.add(LifecycleStatus(order_id=order.id, quotation_created=True,
                                       quotation_approved=True))
        db.session.commit()
        return {**seed, "order_id": str(order.id)}


@pytest.fixture()
def active_agreement(app, seed):
    from app.config import db

    with app.app_context():
        ma = MasterAgreement(
            company_id=seed["company_id"], customer_id=seed["customer_id"],
            agreement_number="HDNT-FLOW-1",
            signed_date=dt.date(2026, 1, 1),
            effective_from=dt.date(2026, 1, 1),
            effective_to=dt.date(2026, 12, 31),
            status=MasterAgreement.STATUS_ACTIVE,
            payment_terms="Thanh toan trong 30 ngay")
        db.session.add(ma)
        db.session.commit()
        return str(ma.id)


def test_order_page_offers_a_contract_when_there_is_no_agreement(
        client, login, order_with_approved_quotation):
    login("admin")
    body = client.get(f'/orders/{order_with_approved_quotation["order_id"]}') \
        .get_data(as_text=True)
    assert 'contracts/' in body, "the ordinary contract route should be offered"


def test_order_page_offers_the_confirmation_when_an_agreement_covers_it(
        client, login, order_with_approved_quotation, active_agreement):
    login("admin")
    body = client.get(f'/orders/{order_with_approved_quotation["order_id"]}') \
        .get_data(as_text=True)
    assert 'HDNT-FLOW-1' in body, "the covering agreement should be named"
    assert 'order-confirmation' in body, "the issue action should be offered"


def test_issuing_the_confirmation_creates_and_confirms_it(
        app, client, login, order_with_approved_quotation, active_agreement):
    order_id = order_with_approved_quotation["order_id"]
    login("admin")

    resp = client.post(f'/orders/{order_id}/order-confirmation', data={},
                       follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        conf = OrderConfirmation.query.filter_by(order_id=order_id).first()
        assert conf is not None, "the confirmation should have been issued"
        assert conf.is_confirmed
        assert conf.cited_agreement_number == "HDNT-FLOW-1"
        assert float(conf.total_amount) == 21_600_000


def test_issuing_the_confirmation_advances_the_lifecycle(
        app, client, login, order_with_approved_quotation, active_agreement):
    """An accepted order is offer + acceptance in one step."""
    from app.models import Order

    order_id = order_with_approved_quotation["order_id"]
    login("admin")
    client.post(f'/orders/{order_id}/order-confirmation', data={},
                follow_redirects=True)

    with app.app_context():
        lifecycle = Order.query.get(order_id).lifecycle
        assert lifecycle.contract_created is True
        assert lifecycle.contract_signed is True


def test_agreement_prices_override_the_quoted_price(
        app, client, login, order_with_approved_quotation, active_agreement):
    from app.config import db
    from app.models.models import MasterAgreementPriceLine
    from app.services.agreement_service import product_key

    with app.app_context():
        db.session.add(MasterAgreementPriceLine(
            agreement_id=active_agreement, product_key=product_key('Sofa 3 cho'),
            product_name='Sofa 3 cho', agreed_unit_price=9_000_000))
        db.session.commit()

    order_id = order_with_approved_quotation["order_id"]
    login("admin")
    client.post(f'/orders/{order_id}/order-confirmation', data={},
                follow_redirects=True)

    with app.app_context():
        conf = OrderConfirmation.query.filter_by(order_id=order_id).first()
        assert conf.items[0]['unit_price'] == 9_000_000
        assert float(conf.subtotal) == 18_000_000


def test_cannot_issue_without_an_agreement(app, client, login,
                                           order_with_approved_quotation):
    order_id = order_with_approved_quotation["order_id"]
    login("admin")
    client.post(f'/orders/{order_id}/order-confirmation', data={},
                follow_redirects=True)

    with app.app_context():
        assert OrderConfirmation.query.filter_by(order_id=order_id).first() is None


def test_cannot_issue_without_an_approved_quotation(app, client, login, seed,
                                                    active_agreement):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                      customer_id=seed["customer_id"], order_code="ORD-NOQ",
                      title="No quotation")
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()
        order_id = str(order.id)

    login("admin")
    client.post(f'/orders/{order_id}/order-confirmation', data={},
                follow_redirects=True)

    with app.app_context():
        assert OrderConfirmation.query.filter_by(order_id=order_id).first() is None


def test_a_suspended_agreement_blocks_issuing(app, client, login,
                                              order_with_approved_quotation,
                                              active_agreement):
    """Suspension must actually stop new orders, not just look different."""
    from app.services.agreement_service import AgreementService

    with app.app_context():
        AgreementService.suspend(MasterAgreement.query.get(active_agreement),
                                 reason='Cong no qua han')

    order_id = order_with_approved_quotation["order_id"]
    login("admin")
    client.post(f'/orders/{order_id}/order-confirmation', data={},
                follow_redirects=True)

    with app.app_context():
        assert OrderConfirmation.query.filter_by(order_id=order_id).first() is None
