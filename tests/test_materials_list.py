"""The materials list must page, and the page control must actually work.

T11 left this list on `.all()`. A sofa workshop carries fabrics, leathers,
foams, frames, legs, springs, zips and glue in every colour and grade it has
ever quoted — several hundred rows is ordinary, and every one of them renders.

The goods-receipt list had the shape of this bug in its worse form: the
template drew a pagination control while the route never passed `pagination`,
so the page was permanently stuck on page 1 and looked like it worked. So this
asserts on what page 2 actually contains, not on the control being present.
"""
import pytest


@pytest.fixture()
def many_materials(app, seed):
    """More materials than fit on one page."""
    from app.config import db
    from app.models.models import Material

    with app.app_context():
        for n in range(1, 46):
            db.session.add(Material(
                company_id=seed['company_id'],
                material_code=f'VT-{n:03d}',
                name=f'Vải bọc mẫu {n:03d}',
                is_active=True))
        db.session.commit()
    return seed


def test_the_list_pages_rather_than_rendering_everything(client, login,
                                                         many_materials):
    login('admin')
    body = client.get('/materials/').get_data(as_text=True)
    assert 'VT-001' in body
    assert 'VT-045' not in body, (
        'every material rendered on one page — the list does not paginate')


def test_page_two_shows_different_materials(client, login, many_materials):
    """The failure that hid itself: a control that renders but never moves."""
    login('admin')
    first = client.get('/materials/?page=1').get_data(as_text=True)
    second = client.get('/materials/?page=2').get_data(as_text=True)

    assert 'VT-001' in first
    assert 'VT-001' not in second, 'page 2 shows the same rows as page 1'
    assert 'VT-045' in second


def test_search_survives_paging(client, login, many_materials):
    """Paging inside a search must not silently drop the search."""
    login('admin')
    body = client.get('/materials/?search=VT-04&page=1').get_data(as_text=True)
    assert 'VT-041' in body
    assert 'VT-001' not in body, 'the search was dropped when the page loaded'
