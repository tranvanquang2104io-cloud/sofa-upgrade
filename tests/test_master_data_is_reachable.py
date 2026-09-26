"""Every kind of record a company maintains must have a way in.

Three times in this programme the same thing has happened, and each time it was
found by accident rather than by looking:

* recording a supplier's invoice had a complete route and no button anywhere —
  reachable only by typing its URL;
* printing a framework agreement had a variable collector, a template type and
  a document model, and no branch in the generator, so nothing could ever be
  produced — "three quarters finished and produced nothing";
* warehouses had a model, a migration that moved real stock, a resolution
  cascade and a wired receiving path, and no route and no template at all.
  Nobody could create a second warehouse, so the choice never appeared and
  every receipt kept resolving to the one the migration made.

None of those is a bug in the work that was done. They are the work being
unreachable, which is a different failure and one that no test of the work
itself can see — the model tests pass, the service tests pass, and the feature
does not exist for anybody using the product.

So the list below is written by hand, one line per kind of record, and each one
names the route that creates it. A new kind of master data fails this test until
somebody writes down where a user gets at it. The failure is the question being
asked, the same way `permission_map` asks where a new endpoint belongs.

Deliberately NOT automatic. Deriving "every model needs a create route" from
the models would be wrong about half of them: a `GoodsReceipt` is created by
receiving against a purchase order and must NOT have a create screen of its
own, and a `LifecycleStatus` is not a thing a person makes at all. Which
records a person maintains is a judgement, so it is written down rather than
guessed.
"""
import pytest

# kind of record -> the endpoint a user reaches to create one
CREATED_BY = {
    'Customer': 'dashboard.create_customer',
    'Material': 'dashboard.create_material',
    'Order': 'dashboard.create_order',
    'Store': 'dashboard.create_store',
    'Supplier': 'dashboard.material_suppliers',
    'User': 'dashboard.create_user',
    'Warehouse': 'dashboard.create_warehouse',
    'StockTransfer': 'dashboard.create_stock_transfer',
    'MasterAgreement': 'dashboard.create_agreement',
    'PurchaseRequisition': 'dashboard.create_requisition',
    'PurchaseOrder': 'dashboard.create_purchase_order',
    'DocumentTemplate': 'dashboard.upload_template',
}

# Records that are the RESULT of doing something else, and must not have a
# create screen. Written down so that "it has no create route" is a claim
# somebody made on purpose rather than something nobody noticed.
MADE_BY_DOING_SOMETHING_ELSE = {
    'GoodsReceipt': 'receiving against a purchase order',
    'SupplierInvoice': 'recording the supplier invoice for a purchase order',
    'ProductionPlan': 'signing a contract',
    'LifecycleStatus': 'the order itself; nobody creates one',
    'Document': 'generating a document from a template',
    'MaterialStock': 'the first receipt of a material into a warehouse',
    'SupplierPaymentAllocation': 'paying a supplier invoice',
}


# The screens a person starts from. Reached from the navigation, not from
# another screen — see `test_the_list_screen_is_in_the_menu`.
LISTED_IN_THE_MENU = {
    'dashboard.list_customers',
    'dashboard.list_materials',
    'dashboard.list_orders',
    'dashboard.list_stores',
    'dashboard.list_warehouses',
    'dashboard.list_stock_transfers',
    'dashboard.list_approvals',
    'dashboard.list_purchase_orders',
}


@pytest.mark.parametrize('kind, endpoint', sorted(CREATED_BY.items()))
def test_a_user_can_reach_the_screen_that_creates_it(app, kind, endpoint):
    assert endpoint in app.view_functions, (
        f'{kind} is maintained by users and {endpoint} does not exist, so the '
        'only way to make one is through the database')


def _links_to(endpoint, within=None):
    import io
    import pathlib

    templates = (pathlib.Path(__file__).resolve().parents[1] / 'app'
                 / 'templates')
    needle = "'" + endpoint + "'"
    paths = [templates / within] if within else list(templates.rglob('*.html'))
    return any(needle in io.open(path, encoding='utf-8').read()
               for path in paths)


@pytest.mark.parametrize('kind, endpoint', sorted(CREATED_BY.items()))
def test_something_links_to_it(kind, endpoint):
    """A route nobody links to is reachable only by typing its URL.

    That is how the supplier-invoice screen sat unused: the route was complete
    and correct and no page in the product mentioned it.
    """
    assert _links_to(endpoint), (
        f'no screen links to {endpoint}, so a user reaches {kind} only by '
        'typing the URL')


@pytest.mark.parametrize('endpoint', sorted(LISTED_IN_THE_MENU))
def test_the_list_screen_is_in_the_menu(endpoint):
    """The link above is not enough on its own, and my own first version missed it.

    `create_warehouse` passed the test above because the WAREHOUSE LIST links
    to it — and nothing linked to the warehouse list. A chain of links is only
    as reachable as its first link, so the screens people start from have to be
    in the navigation, not merely linked from somewhere.
    """
    assert _links_to(endpoint, within='base.html'), (
        f'{endpoint} is in no menu, so every screen reached from it is '
        'unreachable too')


def test_every_listed_kind_is_a_real_model():
    """Guard the list itself: a renamed model must not leave a dead line."""
    import app.models.models as models

    for kind in list(CREATED_BY) + list(MADE_BY_DOING_SOMETHING_ELSE):
        assert hasattr(models, kind), (
            f'{kind} is listed here but is not a model any more; the line is '
            'now asserting nothing')
