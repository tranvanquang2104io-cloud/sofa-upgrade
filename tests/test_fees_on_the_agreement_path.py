"""Fees agreed on an Đơn đặt hàng must reach the handover and the final bill.

The handover and payment screens pre-fill the delivery and other fees from
`active_contract`. An order placed under a framework agreement has no contract
— its commitment is the confirmed ĐĐH — so `active_contract` is None, and
`getattr(None, 'shipping_fee', 0)` is 0. The fees the customer agreed to were
dropped without a word.

The handover is the basis for the hóa đơn GTGT, so this undercharges the
customer and takes the VAT base from the wrong number, on the repeat-business
path.

There is one definition of what an order is worth (`order_agreed_value`); this
adds the matching one for what the order was agreed ON, so the two cannot
drift apart.
"""
import datetime as dt

import pytest


@pytest.fixture()
def confirmation_with_fees(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import (
        LifecycleStatus, MasterAgreement, OrderConfirmation,
    )

    with app.app_context():
        agreement = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-FEE',
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(agreement)
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-FEE',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(OrderConfirmation(
            company_id=seed['company_id'], order_id=order.id,
            master_agreement_id=agreement.id,
            confirmation_number='DDH-FEE',
            confirmation_date=dt.date(2026, 9, 1),
            items=[{'name': 'Sofa góc L', 'quantity': 1, 'unit': 'bộ'}],
            subtotal=40_000_000, vat_rate=8, vat_amount=3_200_000,
            shipping_fee=700_000, another_fee=300_000,
            total_amount=44_200_000,
            status=OrderConfirmation.STATUS_CONFIRMED))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_the_commitment_is_the_order_confirmation(app, confirmation_with_fees):
    from app.models import Order
    from app.services.services import order_commitment

    with app.app_context():
        order = Order.query.get(confirmation_with_fees['order_id'])
        commitment = order_commitment(order)

    assert commitment is not None, 'the order has no commitment at all'
    assert float(commitment.shipping_fee) == 700_000
    assert float(commitment.another_fee) == 300_000


def test_a_plain_order_still_resolves_to_its_contract(app, seed):
    """The ordinary path must be unchanged."""
    from app.config import db
    from app.models import Order
    from app.models.models import Contract
    from app.services.services import order_commitment

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-PLAINFEE',
                      title='Sofa băng')
        db.session.add(order)
        db.session.flush()
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-PLAINFEE', contract_date=dt.date(2026, 9, 1),
            contract_value=10_000_000, advance_percentage=0,
            shipping_fee=500_000, is_signed=True, is_active=True))
        db.session.commit()

        commitment = order_commitment(Order.query.get(order.id))

    assert float(commitment.shipping_fee) == 500_000


def test_an_order_with_nothing_agreed_yet_has_no_commitment(app, seed):
    from app.config import db
    from app.models import Order
    from app.services.services import order_commitment

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-NONE',
                      title='Sofa mới')
        db.session.add(order)
        db.session.commit()
        assert order_commitment(Order.query.get(order.id)) is None


def test_the_handover_form_offers_the_agreed_fees(client, login,
                                                  confirmation_with_fees):
    """The screen the user fills in must start from what was agreed."""
    login('admin')
    body = client.get(
        f"/handover/{confirmation_with_fees['order_id']}/create").get_data(
            as_text=True)
    assert '700000' in body.replace(',', '').replace('.', ''), (
        'the delivery fee agreed on the ĐĐH is not offered on the handover'
    )
