"""The menu says where you are — once — and shows a manager what is waiting.

Before: the current menu item was chosen by substring tests on the endpoint
name. Measured over every screen, six lit up TWO items (each purchase-order
screen lit Orders, because `purchase_order` contains `order`) and nine lit up
none (warehouses, transfers, approvals, supplier invoices, documents).
"""
import re

import pytest

from app.utils.nav import NOT_A_SCREEN, SECTION_OF
from tests.test_the_approval_queue_is_per_branch import (  # noqa: F401 — fixtures
    branch_manager, two_branches_with_requests,
)

ACTIVE_ITEM = re.compile(r'class="nav-link(?:[^"]*\s)?active(?:\s[^"]*)?"[^>]*>\s*<i class="bi ([\w-]+)"')


def _dashboard_get_endpoints(app):
    return {rule.endpoint.split('.', 1)[1] for rule in app.url_map.iter_rules()
            if rule.endpoint.startswith('dashboard.') and 'GET' in rule.methods}


def test_every_screen_is_placed_on_purpose(app):
    """A new screen fails here until someone decides which menu it lives under."""
    endpoints = _dashboard_get_endpoints(app)
    unplaced = sorted(endpoints - set(SECTION_OF) - NOT_A_SCREEN)
    assert not unplaced, f'screens with no menu section: {unplaced}'


def test_the_map_names_only_real_screens(app):
    """A renamed route must not leave a dead entry that silently matches nothing."""
    endpoints = _dashboard_get_endpoints(app)
    stale = sorted((set(SECTION_OF) | NOT_A_SCREEN) - endpoints)
    assert not stale, f'map entries with no route: {stale}'
    assert not set(SECTION_OF) & NOT_A_SCREEN


@pytest.mark.parametrize('url, icon', [
    ('/purchase-orders', 'bi-cart'),              # was: Orders AND Purchasing
    ('/supplier-invoices', 'bi-cart'),            # was: nothing
    ('/reports/receivables', 'bi-graph-up-arrow'),  # was: Customers AND Reports
    ('/warehouses', 'bi-box-seam'),               # was: nothing; now under Inventory
    ('/warehouses/transfers', 'bi-box-seam'),     # was: nothing; now under Inventory
    ('/approvals', 'bi-inbox'),                   # was: nothing
    ('/orders', 'bi-bag'),                        # Bán hàng
    ('/customers', 'bi-bag'),                     # Bán hàng
    ('/agreements', 'bi-bag'),                    # Bán hàng
])
def test_exactly_one_menu_item_is_current(client, login, url, icon):
    login('admin')
    body = client.get(url).get_data(as_text=True)
    nav = body.split('id="navbarNav"', 1)[1].split('</nav>', 1)[0]
    assert ACTIVE_ITEM.findall(nav) == [icon]


def test_stock_screens_are_under_inventory_not_administration(client, login):
    login('admin')
    nav = client.get('/').get_data(as_text=True).split('</nav>', 1)[0]
    inventory, rest = nav.split('bi-box-seam"></i>', 1)[1].split('</ul>', 1)
    admin_menu = rest.split('bi-building-gear', 1)[1].split('</ul>', 1)[0]
    for url in ('/warehouses"', '/warehouses/transfers"'):
        assert url in inventory
        assert url not in admin_menu


def test_a_manager_sees_how_many_requests_wait_for_them(
        app, client, two_branches_with_requests, branch_manager, login):
    """The badge counts what the approvals screen would list — this branch only."""
    login('qlcn')
    body = client.get('/').get_data(as_text=True)
    badge = re.search(r'data-testid="nav-approvals-count">(\d+)<', body)
    assert badge and badge.group(1) == '1'


def test_a_company_admin_counts_every_branch(
        app, client, two_branches_with_requests, login):
    login('admin')
    body = client.get('/').get_data(as_text=True)
    badge = re.search(r'data-testid="nav-approvals-count">(\d+)<', body)
    assert badge and badge.group(1) == '2'


def test_nothing_waiting_shows_no_number(client, login):
    login('admin')
    body = client.get('/').get_data(as_text=True)
    assert 'data-testid="nav-approvals"' in body
    assert 'data-testid="nav-approvals-count"' not in body


def test_staff_who_cannot_decide_do_not_get_the_inbox(client, login):
    login('staff')
    body = client.get('/').get_data(as_text=True)
    assert 'data-testid="nav-approvals"' not in body


def test_the_bar_fits_one_line_on_a_laptop(client, login):
    """Twelve top-level items wrapped every label at 1366px, measured in Chrome.

    The bar is six areas now. This guards the count, which is what decides the
    width; the pixels themselves were checked in a real browser.
    """
    login('admin')
    body = client.get('/').get_data(as_text=True)
    left = body.split('class="navbar-nav me-auto"', 1)[1].split('class="navbar-nav ms-auto"', 1)[0]
    top_level = re.findall(r'<li class="nav-item(?: dropdown)?">', left)
    assert len(top_level) <= 6, f'{len(top_level)} top-level menu items'
    assert 'white-space: nowrap' in open('app/static/css/style.css', encoding='utf-8').read()
