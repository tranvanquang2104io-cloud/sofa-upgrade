"""Every business screen must be behind a permission a person can grant.

The per-user feature tick boxes on the user form work — they are saved, loaded
into the session and enforced by a `before_request` hook. What they cannot do
is cover a screen that the endpoint→feature map has never heard of, and the map
matches on substrings of the endpoint NAME. That makes it silently wrong in two
directions, and both had happened:

* **Framework agreements were behind nothing.** `list_agreements` matches no
  rule, so a staff user with no permissions at all could list, open, create and
  edit the commercial agreements the company trades under.

* **Supplier invoices were behind the wrong one.** `list_supplier_invoices`
  matches the `supplier` rule, which exists for the supplier master in the
  materials area, and so resolved to `inventory`. Granting someone access to
  stock quietly granted them the ability to record and confirm money the
  company owes.

Neither is visible from the user form — the tick boxes look complete either
way. The only place it shows is here, which is why this test enumerates the
routes rather than checking a handful.
"""
import pytest

from app.utils.auth_utils import feature_for_endpoint

# Screens that are deliberately not feature-gated, each for a stated reason.
# A screen may only join this list with one.
EXEMPT = {
    'index': 'the dashboard itself — the landing page after login',
    'set_language': 'a display preference, not data',
    'check_code': 'read-only "is this code taken?" used by the create forms',
    'get_next_code': 'read-only next-number helper for the create forms; it '
                     'reveals a sequence number and nothing else',
    'api_quotation': 'reads a quotation the caller can already open',
    'api_contract': 'reads a contract the caller can already open',
    'serve_item_image': 'an uploaded image, addressed by opaque filename',
}

# Areas guarded by a role decorator instead (company_admin / store_admin), so a
# feature grant would be the wrong mechanism: these are administration, not work.
ROLE_GUARDED = ('store', 'user', 'setting', 'template', 'extension')


def _business_endpoints(app):
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('dashboard.'):
            continue
        if 'GET' not in rule.methods:
            continue
        name = rule.endpoint.split('.', 1)[1]
        if name in EXEMPT or any(k in name for k in ROLE_GUARDED):
            continue
        yield name, rule.endpoint


def test_every_business_screen_resolves_to_a_feature(app):
    ungated = sorted(
        name for name, endpoint in _business_endpoints(app)
        if feature_for_endpoint(endpoint) is None)

    assert ungated == [], (
        'these screens are behind no permission at all, so every staff user '
        f'can reach them however their tick boxes are set: {ungated}')


@pytest.mark.parametrize('name, expected', [
    # Money the company owes is a purchasing matter, not a stock matter.
    ('list_supplier_invoices', 'purchasing'),
    ('view_supplier_invoice', 'purchasing'),
    ('create_supplier_invoice', 'purchasing'),
    ('confirm_supplier_invoice', 'purchasing'),
    ('pay_supplier_invoice', 'purchasing'),
    # A framework agreement is the contract an order is placed under.
    ('list_agreements', 'orders'),
    ('view_agreement', 'orders'),
    ('create_agreement', 'orders'),
    ('edit_agreement', 'orders'),
    # The rules that were already right, pinned so the fix cannot break them.
    ('list_materials', 'inventory'),
    # `material_suppliers`, not `list_suppliers`: the latter is not a route at
    # all. Under substring matching it resolved to 'inventory' anyway — the
    # word "supplier" was enough — so this line passed while asserting nothing.
    ('material_suppliers', 'inventory'),
    ('view_purchase_order', 'purchasing'),
    ('list_orders', 'orders'),
    ('list_customers', 'customers'),
])
def test_each_screen_sits_behind_the_permission_it_belongs_to(name, expected):
    assert feature_for_endpoint('dashboard.' + name) == expected


def _grant(app, username, features):
    """Set exactly these features on a seeded user."""
    from app.config import db
    from app.models.models import User
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.allowed_features = list(features)
        db.session.commit()


def test_a_staff_user_without_orders_cannot_open_agreements(app, client, login,
                                                            seed):
    """The map being right is not the same as the gate biting."""
    _grant(app, 'staff', ['customers'])
    login('staff')
    assert client.get('/agreements').status_code == 403


def test_a_staff_user_with_orders_can_open_agreements(app, client, login, seed):
    _grant(app, 'staff', ['orders'])
    login('staff')
    assert client.get('/agreements').status_code == 200


def test_stock_access_alone_does_not_reach_supplier_invoices(app, client,
                                                             login, seed):
    """The defect in its own words: inventory must not imply payables."""
    _grant(app, 'staff', ['inventory'])
    login('staff')
    assert client.get('/supplier-invoices').status_code == 403
