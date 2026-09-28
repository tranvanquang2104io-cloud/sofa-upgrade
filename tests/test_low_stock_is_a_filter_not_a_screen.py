"""One materials list with a filter, instead of a second screen.

The owner asked for `/materials/low-stock` to go and be replaced by a filter.
Checked before agreeing: `low_stock.html` showed four columns, and
`materials/list.html` ALREADY shows all four — the warning row highlight, the
"Low Stock" badge, and `total_stock / min_stock_level` — plus five more. The
separate screen added no information, only a second place to look.

But the capability it provided is real: "show me only the ones running out" is
what a person opens that menu item to do. So the filter is added FIRST and the
screen removed after, rather than the other way round. Removing a capability
and calling it cleanup is how a tidy-up becomes a regression.

What is NOT removed: `ProductionPlanService.low_stock_materials`. It is what
`purchase_suggestions` is built on. Deleting a screen is not a reason to
delete the arithmetic behind it, and a grep for the route name would have
suggested otherwise.
"""
import pytest


@pytest.fixture()
def mixed_stock(app, seed):
    """One material below its minimum, one comfortably above."""
    from app.config import db
    from app.models.models import Material, MaterialStock

    with app.app_context():
        low = Material(company_id=seed['company_id'], material_code='VAI-CAN',
                       name='Vai sap het', min_stock_level=100, is_active=True)
        fine = Material(company_id=seed['company_id'], material_code='VAI-DU',
                        name='Vai con nhieu', min_stock_level=10,
                        is_active=True)
        db.session.add_all([low, fine])
        db.session.flush()
        db.session.add(MaterialStock(material_id=low.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=2))
        db.session.add(MaterialStock(material_id=fine.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=500))
        db.session.commit()
        return seed


def test_the_filter_shows_only_what_is_running_out(client, login,
                                                   mixed_stock):
    login('admin')
    body = client.get('/materials/?low_stock=1').get_data(as_text=True)

    assert 'VAI-CAN' in body, 'the material below its minimum is missing'
    assert 'VAI-DU' not in body, (
        'a material with plenty in stock showed up in the low-stock filter, '
        'so the filter is not filtering')


def test_the_unfiltered_list_still_shows_everything(client, login,
                                                    mixed_stock):
    """The filter must be a filter, not a new default."""
    login('admin')
    body = client.get('/materials/').get_data(as_text=True)

    assert 'VAI-CAN' in body
    assert 'VAI-DU' in body


def test_the_old_screen_is_gone(client, login, mixed_stock):
    """Two places showing the same thing is two places to keep in step."""
    login('admin')
    assert client.get('/materials/low-stock').status_code == 404


def test_the_menu_points_at_the_filter(client, login, mixed_stock):
    """A dead menu item is worse than a removed one."""
    login('admin')
    body = client.get('/materials/').get_data(as_text=True)
    assert 'low_stock=1' in body, (
        'nothing on the screen offers the low-stock filter, so the capability '
        'was removed rather than moved')


def test_the_arithmetic_behind_it_is_untouched(app, mixed_stock):
    """`low_stock_materials` feeds purchase suggestions and must survive."""
    from app.services.services import ProductionPlanService

    with app.app_context():
        found = ProductionPlanService().low_stock_materials(
            mixed_stock['company_id'])
        codes = {m.material_code for m in found}
        assert 'VAI-CAN' in codes, (
            'deleting the screen also broke the calculation that purchase '
            'suggestions is built on')


def test_a_malformed_id_is_not_found_rather_than_a_crash(client, login,
                                                         mixed_stock):
    """Removing the screen exposed a latent bug worth more than the cleanup.

    With `/materials/low-stock` gone, that URL fell through to
    `/materials/<material_id>`, which handed "low-stock" to the database as a
    UUID and got back `ValueError: badly formed hexadecimal UUID string` — a
    500. So ANY mistyped or stale material link crashed the screen instead of
    saying "not found", and the same was true for every other model.

    A malformed id is a request for something that does not exist. The callers
    already treat None that way; the repository just never got far enough to
    return one.
    """
    login('admin')

    for url in ('/materials/low-stock',
                '/materials/not-a-uuid',
                '/orders/also-not-a-uuid'):
        status = client.get(url).status_code
        assert status != 500, (
            f'{url} crashed the screen instead of reporting not-found '
            f'(HTTP {status})')
