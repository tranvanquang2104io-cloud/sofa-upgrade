"""Home and Reports, separated by role — and every figure scoped to the reader.

Before 2026-09-30 the home screen showed everybody the same four counts, and
the reports were company-wide for anyone granted "reports": a branch manager,
or a staff member, read every branch's revenue and every customer's debt by
name, while the documents themselves were already locked to their branch.

The fixture is two branches, each with one signed contract:
  * MINE — the seeded branch, contract signed THIS month, due in 20 days
  * FAR  — another branch, signed 60 days ago with 30 days to complete, and
           not handed over: LATE.
"""
import datetime as dt
import re

import pytest

TODAY = dt.date.today()


@pytest.fixture()
def two_branches(app, seed):
    from app.config import db
    from app.models.models import Contract, Customer, LifecycleStatus, Order, Store, User

    with app.app_context():
        far = Store(company_id=seed['company_id'], store_code='CN-FAR', name='Chi nhánh Đà Nẵng', is_active=True)
        db.session.add(far)
        db.session.flush()
        far_customer = Customer(company_id=seed['company_id'], store_id=far.id,
                                customer_code='KH-FAR', name='Khách Đà Nẵng')
        db.session.add(far_customer)
        db.session.flush()

        made = {}
        for key, store_id, customer_id, signed, value in (
                ('mine', seed['store_id'], seed['customer_id'], TODAY.replace(day=1), 30_000_000),
                ('far', far.id, far_customer.id, TODAY - dt.timedelta(days=60), 50_000_000)):
            order = Order(company_id=seed['company_id'], store_id=store_id, customer_id=customer_id,
                          order_code=f'DH-{key.upper()}', title=f'Sofa {key}')
            db.session.add(order)
            db.session.flush()
            db.session.add(LifecycleStatus(order_id=order.id, contract_created=True, contract_signed=True))
            db.session.add(Contract(order_id=order.id, company_id=seed['company_id'],
                                    contract_number=f'HD-{key.upper()}', contract_date=signed,
                                    contract_value=value, is_signed=True, is_active=True,
                                    contract_days_complete=(TODAY - signed).days + 20 if key == 'mine' else 30,
                                    advance_percentage=30))
            made[key] = str(order.id)

        manager = User(company_id=seed['company_id'], store_id=seed['store_id'], username='qlcn',
                       email='qlcn@acme.test', full_name='Quản lý chi nhánh', role=User.ROLE_STORE_ADMIN,
                       is_active=True)
        manager.set_password('secret123')
        reporter = User.query.filter_by(username='staff').first()
        reporter.allowed_features = ['orders', 'customers', 'reports']
        db.session.add(manager)
        db.session.commit()
        return {**seed, 'far_store_id': str(far.id), 'mine_order': made['mine'], 'far_order': made['far']}


# -- the one definition of "due" ----------------------------------------------

def test_an_order_is_due_on_the_date_its_contract_promised(app, two_branches):
    from app.models.models import Order
    from app.services.services import order_due_date
    with app.app_context():
        far = Order.query.get(two_branches['far_order'])
        assert order_due_date(far) == TODAY - dt.timedelta(days=30)


# -- the service is scoped ------------------------------------------------------

def test_figures_are_scoped_to_the_branches_given(app, two_branches):
    import uuid
    from app.services.report_service import ReportService
    svc = ReportService()
    with app.app_context():
        mine = [uuid.UUID(two_branches['store_id'])]
        assert svc._booked_total(two_branches['company_id']) == 80_000_000
        assert svc._booked_total(two_branches['company_id'], mine) == 30_000_000
        names = [r['customer_name'] for r in svc.customer_receivables(two_branches['company_id'], mine)]
        assert 'Khách Đà Nẵng' not in names


def test_a_period_counts_only_what_happened_in_it(app, two_branches):
    from app.services.periods import period
    from app.services.report_service import ReportService
    with app.app_context():
        this_month = ReportService()._booked_total(two_branches['company_id'], period=period('month'))
    assert this_month == 30_000_000, 'the contract signed 60 days ago is not this month'


def test_late_is_measured_against_the_promise(app, two_branches):
    from app.services.report_service import ReportService
    with app.app_context():
        late = ReportService().delivery(two_branches['company_id'])['late']
    assert [r['order_code'] for r in late] == ['DH-FAR']
    assert late[0]['days'] == 30


# -- Reports, by role ------------------------------------------------------------

def test_a_company_admin_sees_every_branch_side_by_side(client, login, two_branches):
    login('admin')
    body = client.get('/reports').get_data(as_text=True)
    assert 'data-testid="by-branch"' in body and 'Chi nhánh Đà Nẵng' in body
    assert 'data-testid="margins"' in body


def test_a_company_admin_can_narrow_to_one_branch(client, login, two_branches):
    login('admin')
    body = client.get(f'/reports?period=all&store={two_branches["far_store_id"]}').get_data(as_text=True)
    assert '50,000,000 ₫' in body and '80,000,000 ₫' not in body
    assert 'data-testid="by-branch"' not in body, 'one branch picked: no branch table'


def test_a_branch_manager_sees_only_their_branch(client, login, two_branches):
    login('qlcn')
    body = client.get('/reports?period=all').get_data(as_text=True)
    assert '30,000,000 ₫' in body
    assert '80,000,000 ₫' not in body and '50,000,000 ₫' not in body
    assert 'data-testid="by-branch"' not in body
    assert 'data-testid="margins"' in body, 'a manager does see margins'
    assert 'data-testid="scope-note"' in body


def test_a_branch_manager_cannot_ask_for_another_branch(client, login, two_branches):
    login('qlcn')
    body = client.get(f'/reports?period=all&store={two_branches["far_store_id"]}').get_data(as_text=True)
    assert '50,000,000 ₫' not in body


def test_staff_granted_reports_see_no_margins_and_only_their_branch(client, login, two_branches):
    login('staff')
    body = client.get('/reports?period=all').get_data(as_text=True)
    assert 'data-testid="margins"' not in body, 'cost and profit are management information'
    assert '50,000,000 ₫' not in body


def test_the_debt_report_is_scoped_too(client, login, two_branches):
    login('qlcn')
    assert 'Khách Đà Nẵng' not in client.get('/reports/receivables').get_data(as_text=True)
    login('admin')
    assert 'Khách Đà Nẵng' in client.get('/reports/receivables').get_data(as_text=True)


# -- Home, by role -----------------------------------------------------------------

def _card(body, key):
    m = re.search(rf'data-testid="queue-{key}".*?sf-queue__count">(\d+)<', body, re.S)
    return int(m.group(1)) if m else None


def test_staff_home_is_a_work_queue_without_the_money(client, login, two_branches):
    login('staff')
    body = client.get('/').get_data(as_text=True)
    assert 'data-testid="work-queue"' in body
    assert 'data-testid="headline"' not in body, 'the month\'s money is for managers'
    assert _card(body, 'await_advance') == 1, 'their own branch only'
    assert _card(body, 'late') == 0, 'the late order is in another branch'


def test_a_manager_home_adds_the_month(client, login, two_branches):
    login('qlcn')
    body = client.get('/').get_data(as_text=True)
    assert 'data-testid="headline"' in body
    assert '30,000,000 ₫' in body


def test_the_company_admin_sees_the_late_order(client, login, two_branches):
    login('admin')
    body = client.get('/').get_data(as_text=True)
    assert _card(body, 'late') == 1


@pytest.mark.parametrize('key', ['late', 'await_advance'])
def test_a_card_opens_exactly_the_orders_it_counted(client, login, two_branches, key):
    login('admin')
    count = _card(client.get('/').get_data(as_text=True), key)
    listed = client.get(f'/orders?queue={key}').get_data(as_text=True)
    assert 'data-testid="queue-banner"' in listed
    assert f'— {count} ' in listed
    assert ('DH-FAR' in listed) == (key in ('late', 'await_advance'))


def test_handing_over_takes_an_order_off_the_late_list(app, client, login, two_branches):
    from app.config import db
    from app.models.models import LifecycleStatus
    with app.app_context():
        LifecycleStatus.query.filter_by(order_id=two_branches['far_order']).first().handover_confirmed = True
        db.session.commit()
    login('admin')
    assert _card(client.get('/').get_data(as_text=True), 'late') == 0


def test_a_contract_is_what_the_order_is_worth(app, seeded_order):
    """Only a quotation used to set the order's value: an order contracted
    without one showed 0 ₫ on the home screen, the order list and the handover
    and payment side panels (seen in Chrome on the demo data)."""
    from app.config import db
    from app.models.models import LifecycleStatus, Order
    from app.services.services import ContractService

    with app.app_context():
        db.session.add(LifecycleStatus(order_id=seeded_order['order_id']))
        db.session.commit()
        ContractService().create_contract(seeded_order['order_id'], None, 'HD-NOQ',
                                          dt.date(2026, 9, 1), 52_380_000)
        assert float(Order.query.get(seeded_order['order_id']).total_amount) == 52_380_000
