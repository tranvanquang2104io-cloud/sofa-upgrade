"""The six routes no test had ever opened.

Coverage was measured, not guessed: 6 of 107 dashboard routes were never
referenced by any test. Two of them serve files and were examined first (the
image route blocks path traversal, the document download checks tenancy, and
the download led to the referrer-redirect work). These are the other four.

Nothing here is a bug report — the point is that "is it correct and complete"
cannot be answered for a screen nobody has ever exercised. Each test states the
property that must hold, so a future change to these routes cannot quietly
break them.
"""
import datetime as dt

import pytest


# --- language switch ------------------------------------------------------

def test_switching_language_sticks(client, login):
    login("admin")
    client.get('/set-language/vi')
    assert client.get('/orders').get_data(as_text=True).count('Đơn hàng') > 0


def test_an_unknown_language_is_ignored_not_stored(client, login):
    """A bad value must leave the session alone rather than blanking the UI."""
    login("admin")
    client.get('/set-language/vi')
    client.get('/set-language/zz')

    with client.session_transaction() as session:
        assert session.get('lang') == 'vi'


def test_the_language_switch_cannot_bounce_the_user_off_site(client, login):
    login("admin")
    resp = client.get('/set-language/vi',
                      headers={'Referer': 'https://evil.com/steal'})
    assert 'evil.com' not in (resp.headers.get('Location') or '')


# --- material categories --------------------------------------------------

def test_a_category_can_be_created_and_is_listed(app, client, login, seed):
    login("admin")
    client.post('/materials/categories',
                data={'action': 'create', 'name': 'Vải bọc cao cấp',
                      'sort_order': '1'},
                follow_redirects=True)

    body = client.get('/materials/categories').get_data(as_text=True)
    assert 'Vải bọc cao cấp' in body


def test_a_category_belongs_to_one_company_only(app, client, login, seed):
    from app.config import db
    from app.models import Company
    from app.models.models import MaterialCategory

    with app.app_context():
        rival = Company(company_code="CAT", name="Rival", email="r@cat.test")
        db.session.add(rival)
        db.session.flush()
        db.session.add(MaterialCategory(company_id=rival.id,
                                        name='ZZRIVALCATEGORY'))
        db.session.commit()

    login("admin")
    body = client.get('/materials/categories').get_data(as_text=True)
    assert 'ZZRIVALCATEGORY' not in body


# --- production plan: behind-schedule flag and norms ----------------------

@pytest.fixture()
def a_plan(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract
    from app.services.services import ProductionPlanService

    with app.app_context():
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code='DH-PLAN-T',
                  title='Sofa')
        db.session.add(o)
        db.session.flush()
        c = Contract(company_id=seed['company_id'], order_id=o.id,
                     contract_number='CT-PLAN-T',
                     contract_date=dt.date(2026, 1, 1), contract_value=1_000_000,
                     is_signed=True,
                     items=[{'name': 'Sofa 3 chỗ', 'unit': 'bộ', 'quantity': 1,
                             'unit_price': 1_000_000, 'total': 1_000_000}])
        db.session.add(c)
        db.session.commit()

        plan = ProductionPlanService().create_from_contract(c)
        db.session.commit()
        return {'plan_id': str(plan.id), 'order_id': str(o.id),
                'item_id': str(plan.items[0].id) if plan.items else None,
                **seed}


def test_marking_a_plan_behind_schedule_and_clearing_it(app, client, login,
                                                        a_plan):
    from app.models.models import ProductionPlan

    login("admin")
    client.post(f"/production-plan/{a_plan['plan_id']}/delay",
                data={'delayed': '1', 'delay_reason': 'Thiếu vải'},
                follow_redirects=True)
    with app.app_context():
        assert ProductionPlan.query.get(a_plan['plan_id']).is_delayed is True

    client.post(f"/production-plan/{a_plan['plan_id']}/delay",
                data={'delayed': '0'}, follow_redirects=True)
    with app.app_context():
        assert ProductionPlan.query.get(a_plan['plan_id']).is_delayed is False


def test_the_delay_flag_of_another_company_cannot_be_touched(app, client,
                                                             login, a_plan):
    from app.config import db
    from app.models import Company, Customer, Order, Store
    from app.models.models import Contract, ProductionPlan
    from app.services.services import ProductionPlanService

    with app.app_context():
        c = Company(company_code="PLN", name="Rival", email="r@pln.test")
        db.session.add(c)
        db.session.flush()
        st = Store(company_id=c.id, store_code="PLS", name="S")
        db.session.add(st)
        db.session.flush()
        cu = Customer(company_id=c.id, store_id=st.id, customer_code="PLC",
                      name="KH")
        db.session.add(cu)
        db.session.flush()
        o = Order(company_id=c.id, store_id=st.id, customer_id=cu.id,
                  order_code='ZZ-PLAN-R', title='T')
        db.session.add(o)
        db.session.flush()
        ct = Contract(company_id=c.id, order_id=o.id, contract_number='ZZCT-R',
                      contract_date=dt.date(2026, 1, 1), contract_value=1,
                      is_signed=True, items=[])
        db.session.add(ct)
        db.session.commit()
        rival_plan = ProductionPlanService().create_from_contract(ct)
        db.session.commit()
        rival_plan_id = str(rival_plan.id)

    login("admin")
    client.post(f"/production-plan/{rival_plan_id}/delay",
                data={'delayed': '1'}, follow_redirects=True)

    with app.app_context():
        assert ProductionPlan.query.get(rival_plan_id).is_delayed is False


@pytest.fixture()
def a_plan_with_materials(app, a_plan):
    """The same plan, with one material line on its first item."""
    from app.config import db
    from app.models.models import (
        Material, MaterialCategory, MaterialUnit, ProductionMaterialLine,
    )

    with app.app_context():
        unit = MaterialUnit(company_id=a_plan['company_id'], name='m')
        cat = MaterialCategory(company_id=a_plan['company_id'], name='Vai')
        db.session.add_all([unit, cat])
        db.session.flush()
        mat = Material(company_id=a_plan['company_id'], material_code='M-NORM',
                       name='Vải nhung', unit_id=unit.id, category_id=cat.id)
        db.session.add(mat)
        db.session.flush()
        db.session.add(ProductionMaterialLine(
            plan_id=a_plan['plan_id'], plan_item_id=a_plan['item_id'],
            material_id=mat.id, quantity_required=6, unit='m'))
        db.session.commit()
        return a_plan


def test_saving_a_norm_writes_one_per_material(app, client, login,
                                               a_plan_with_materials):
    """The control: without this, the refusal tests below prove nothing."""
    from app.models.models import MaterialNorm

    login("admin")
    client.post(f"/production-plan/{a_plan_with_materials['plan_id']}"
                f"/save-norm/{a_plan_with_materials['item_id']}",
                follow_redirects=True)

    with app.app_context():
        assert MaterialNorm.query.count() == 1


def test_saving_a_norm_requires_the_item_to_belong_to_the_plan(
        app, client, login, a_plan_with_materials):
    """The item id comes from the URL, so it has to be checked against the plan."""
    import uuid

    from app.models.models import MaterialNorm

    login("admin")
    body = client.post(
        f"/production-plan/{a_plan_with_materials['plan_id']}/save-norm/{uuid.uuid4()}",
        follow_redirects=True).get_data(as_text=True)

    with app.app_context():
        assert MaterialNorm.query.count() == 0
    assert ('không' in body.lower() or 'not found' in body.lower()), (
        "a click that does nothing must say so; silence reads as a broken button"
    )


def test_an_item_with_no_materials_does_not_claim_it_saved(
        app, client, login, a_plan):
    """save_as_norm loops over the material lines, so with none it writes
    nothing — while the handler flashed "saved" regardless."""
    from app.models.models import MaterialNorm

    login("admin")
    body = client.post(f"/production-plan/{a_plan['plan_id']}"
                       f"/save-norm/{a_plan['item_id']}",
                       follow_redirects=True).get_data(as_text=True)

    with app.app_context():
        assert MaterialNorm.query.count() == 0
    assert 'Đã lưu định mức để tái sử dụng' not in body, (
        "telling the user something was saved when nothing was is worse than "
        "telling them there was nothing to save"
    )
