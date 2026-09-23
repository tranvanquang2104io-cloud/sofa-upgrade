"""An order agreed by framework agreement must reach the workshop too.

`create_from_contract` is called from exactly one place: signing a contract. An
order placed under a HĐNT never has a contract — its commitment is the confirmed
Đơn đặt hàng — so it got no production plan at all.

Everything downstream hangs off the plan: the material lines, `issue_materials`
and therefore the STOCK DEDUCTION, the material cost, the margin, and the
/production list. So for framework customers the fabric they consume is never
taken off stock, and on-hand quantity, low-stock and purchase suggestions drift
further every job — for exactly the repeat-business customers a workshop most
wants to keep supplying.

It is invisible from the order screen, which looks complete: the lifecycle says
contract-created and contract-signed, because the confirmation sets both.
"""
import datetime as dt

import pytest


@pytest.fixture()
def agreement_order(app, seed):
    """An order covered by an active framework agreement, with a draft ĐĐH."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        LifecycleStatus, MasterAgreement, OrderConfirmation,
    )

    with app.app_context():
        agreement = MasterAgreement(
            company_id=seed['company_id'], customer_id=seed['customer_id'],
            agreement_number='HDNT-001',
            effective_from=dt.date(2026, 1, 1),
            status=MasterAgreement.STATUS_ACTIVE)
        db.session.add(agreement)
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HDNT',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       quotation_approved=True))

        confirmation = OrderConfirmation(
            company_id=seed['company_id'], order_id=order.id,
            master_agreement_id=agreement.id,
            confirmation_number='DDH-001',
            confirmation_date=dt.date(2026, 9, 1),
            items=[{'name': 'Sofa góc L', 'quantity': 2, 'unit': 'bộ'},
                   {'name': 'Ghế đôn', 'quantity': 4, 'unit': 'cái'}],
            subtotal=40_000_000, total_amount=43_200_000,
            status=OrderConfirmation.STATUS_DRAFT)
        db.session.add(confirmation)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'confirmation_id': str(confirmation.id)}


def test_confirming_an_order_confirmation_creates_the_plan(app,
                                                           agreement_order):
    from app.models.models import OrderConfirmation, ProductionPlan
    from app.services.agreement_service import AgreementService

    with app.app_context():
        confirmation = OrderConfirmation.query.get(
            agreement_order['confirmation_id'])
        AgreementService.confirm(confirmation)

        plan = ProductionPlan.query.filter_by(
            order_id=agreement_order['order_id']).first()

    assert plan is not None, (
        'a framework-agreement order never reaches the workshop, so its '
        'materials are never taken off stock')


def test_the_plan_carries_the_items_that_were_ordered(app, agreement_order):
    from app.models.models import OrderConfirmation, ProductionPlan
    from app.services.agreement_service import AgreementService

    with app.app_context():
        confirmation = OrderConfirmation.query.get(
            agreement_order['confirmation_id'])
        AgreementService.confirm(confirmation)

        plan = ProductionPlan.query.filter_by(
            order_id=agreement_order['order_id']).first()
        names = sorted(item.source_name for item in plan.items)
        quantities = {item.source_name: float(item.quantity)
                      for item in plan.items}

    assert names == ['Ghế đôn', 'Sofa góc L']
    assert quantities['Sofa góc L'] == 2
    assert quantities['Ghế đôn'] == 4


def test_creating_the_plan_twice_yields_one_plan(app, agreement_order):
    """An order has one plan however many times the call is made.

    Confirming the SAME confirmation twice is refused by the service, and
    rightly so. What has to hold here is that the plan creation itself is
    idempotent — it is reached from two paths now, and an order that somehow
    arrives at both must not end up with two plans.
    """
    from app.models.models import OrderConfirmation, ProductionPlan
    from app.services.agreement_service import AgreementService
    from app.services.services import ProductionPlanService

    with app.app_context():
        confirmation = OrderConfirmation.query.get(
            agreement_order['confirmation_id'])
        AgreementService.confirm(confirmation)
        ProductionPlanService().create_from_contract(confirmation)

        plans = ProductionPlan.query.filter_by(
            order_id=agreement_order['order_id']).all()

    assert len(plans) == 1


def test_the_plan_appears_on_the_production_list(client, login, app,
                                                 agreement_order):
    """The workshop's own screen is where this has to show up."""
    from app.models.models import OrderConfirmation
    from app.services.agreement_service import AgreementService

    with app.app_context():
        AgreementService.confirm(OrderConfirmation.query.get(
            agreement_order['confirmation_id']))

    login('admin')
    body = client.get('/production').get_data(as_text=True)
    assert 'DH-HDNT' in body
