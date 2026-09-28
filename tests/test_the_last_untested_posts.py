"""The rest of the endpoints nobody had ever posted to.

Twenty-two at the start of T-19, twelve after the first two batches, none
after this one. The interesting ones here guard money and stock:

  * a signed contract must not be editable — it is what the customer signed;
  * a confirmed handover must not be editable — the customer accepted it;
  * which warehouse a material line draws from decides which shelf empties.

The rest are master data, where the thing worth checking is that an edit
reaches the record rather than that the route returns 302.
"""
import datetime as dt

import pytest


@pytest.fixture()
def signed_contract(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-EDIT',
                      title='Sofa goc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       contract_created=True,
                                       contract_signed=True))
        contract = Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-EDIT', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=50,
            is_signed=True, is_active=True)
        db.session.add(contract)
        db.session.commit()
        return {**seed, 'order_id': str(order.id),
                'contract_id': str(contract.id)}


def test_a_signed_contract_cannot_be_edited(app, client, login,
                                            signed_contract):
    """It is the document the customer signed. Changing it changes history."""
    from app.models.models import Contract

    login('admin')
    client.post(f"/contracts/{signed_contract['contract_id']}/edit", data={
        'contract_number': 'HD-EDIT', 'contract_date': '2026-09-01',
        'item_name[]': ['Sofa re'], 'item_unit[]': ['Bo'],
        'item_quantity[]': ['1'], 'item_price[]': ['1'],
        'vat_rate': '0', 'advance_percentage': '90',
    }, follow_redirects=True)

    with app.app_context():
        after = Contract.query.get(signed_contract['contract_id'])
        assert float(after.contract_value) == 20_000_000, (
            'a signed contract was rewritten, so our copy no longer matches '
            'the paper the customer holds')
        assert float(after.advance_percentage) == 50


def test_an_unsigned_contract_can_still_be_edited(app, client, login,
                                                  signed_contract):
    """The refusal must be about SIGNED, not about editing."""
    from app.config import db
    from app.models.models import Contract

    with app.app_context():
        contract = Contract.query.get(signed_contract['contract_id'])
        contract.is_signed = False
        db.session.commit()

    # The value comes from the LINE ITEMS, not a `contract_value` field —
    # `parse_line_items` + `totals_from_form`, same as quotations. My first
    # version posted `contract_value` directly and the contract came out at
    # zero, because no items meant no subtotal. Posting fields the form does
    # not send tests my guess at the form, which is the fifth time that has
    # bitten me in this refactor.
    login('admin')
    client.post(f"/contracts/{signed_contract['contract_id']}/edit", data={
        'contract_number': 'HD-EDIT', 'contract_date': '2026-09-01',
        'item_name[]': ['Sofa goc L'], 'item_unit[]': ['Bo'],
        'item_quantity[]': ['1'], 'item_price[]': ['18000000'],
        'vat_rate': '0', 'advance_percentage': '40',
    }, follow_redirects=True)

    with app.app_context():
        after = Contract.query.get(signed_contract['contract_id'])
        assert float(after.contract_value) == 18_000_000, (
            'an unsigned contract could not be corrected, so the only way to '
            'fix a typo is to cancel and start again')


def test_a_confirmed_handover_cannot_be_edited(app, client, login, seed):
    """The customer signed for these goods on this date."""
    from app.config import db
    from app.models import Order
    from app.models.models import HandoverRecord, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-HEDIT',
                      title='Sofa bang', total_amount=9_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       handover_confirmed=True))
        record = HandoverRecord(
            company_id=seed['company_id'], order_id=order.id,
            report_number='BB-HEDIT', report_date=dt.date(2026, 9, 1),
            handover_date=dt.date(2026, 9, 1), is_confirmed=True)
        db.session.add(record)
        db.session.commit()
        record_id = str(record.id)

    login('admin')
    client.post(f'/handover/{record_id}/edit', data={
        'report_number': 'BB-HEDIT', 'report_date': '2026-09-01',
        'handover_date': '2026-12-31',
    }, follow_redirects=True)

    with app.app_context():
        after = HandoverRecord.query.get(record_id)
        assert after.handover_date == dt.date(2026, 9, 1), (
            'the delivery date on a handover the customer had already signed '
            'for was moved')


def test_naming_the_warehouse_a_material_line_draws_from(app, client, login,
                                                         seed):
    """Which shelf empties when this plan is issued."""
    from app.config import db
    from app.models import Order
    from app.models.models import (
        Contract, Material, ProductionMaterialLine, ProductionPlan, Warehouse,
    )

    with app.app_context():
        warehouse = Warehouse(company_id=seed['company_id'],
                              store_id=seed['store_id'],
                              warehouse_code='KHO-LINE', name='Kho vai',
                              is_active=True)
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-LINE', name='Vai',
                            is_active=True)
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-LINE',
                      title='Sofa goc L')
        db.session.add_all([warehouse, material, order])
        db.session.flush()
        plan = ProductionPlan(company_id=seed['company_id'], order_id=order.id,
                              plan_number='KH-LINE',
                              status=ProductionPlan.STATUS_DRAFT)
        db.session.add(plan)
        db.session.flush()
        line = ProductionMaterialLine(plan_id=plan.id, material_id=material.id,
                                      quantity_required=5, unit='m')
        db.session.add(line)
        db.session.commit()
        plan_id, line_id = str(plan.id), str(line.id)
        warehouse_id = str(warehouse.id)

    login('admin')
    client.post(f'/production-plan/{plan_id}/materials/{line_id}/warehouse',
                data={'warehouse_id': warehouse_id}, follow_redirects=True)

    with app.app_context():
        assert str(ProductionMaterialLine.query.get(line_id).warehouse_id) == \
            warehouse_id, (
            'the line still does not say which warehouse it is drawn from, so '
            'issuing it empties whichever shelf the default picks')


def test_a_store_can_be_created_and_retired(app, client, login, seed):
    from app.models.models import Store

    login('admin')
    client.post('/stores/create', data={
        'store_code': 'CH-NEW', 'name': 'Chi nhanh moi',
    }, follow_redirects=True)

    with app.app_context():
        made = Store.query.filter_by(store_code='CH-NEW').first()
        assert made is not None, 'the store was not created'
        store_id = str(made.id)

    client.post(f'/stores/{store_id}/edit',
                data={'store_code': 'CH-NEW', 'name': 'Chi nhanh doi ten'},
                follow_redirects=True)

    with app.app_context():
        assert Store.query.get(store_id).name == 'Chi nhanh doi ten', (
            'renaming a branch through the screen did not reach the record')

    client.post(f'/stores/{store_id}/deactivate', follow_redirects=True)

    with app.app_context():
        assert Store.query.get(store_id).is_active is False


def test_editing_a_material_reaches_the_record(app, client, login, seed):
    from app.config import db
    from app.models.models import Material

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-ED', name='Ten cu',
                            min_stock_level=5, is_active=True)
        db.session.add(material)
        db.session.commit()
        material_id = str(material.id)

    login('admin')
    client.post(f'/materials/{material_id}/edit', data={
        'material_code': 'VAI-ED', 'name': 'Ten moi',
        'unit_price': '99000', 'min_stock_level': '50',
    }, follow_redirects=True)

    with app.app_context():
        after = Material.query.get(material_id)
        assert after.name == 'Ten moi'
        assert float(after.min_stock_level) == 50, (
            'the reorder level did not change, so the low-stock warning still '
            'uses the old number')
