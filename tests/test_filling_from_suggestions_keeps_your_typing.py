"""The button said "fill in as well" and behaved like "throw it away".

(My first version of these tests posted `material_id[]`/`quantity[]`. The form
sends `line_material_id[]`/`line_quantity[]`, so nothing was parsed as typed
and two assertions passed for the wrong reason while one failed for the right
one. Posting data the form never sends tests my memory of the field names, not
the product — the same mistake as a fixture that manufactures its own input.)

`pr_form.html` had an `<a href>` INSIDE the `<form>`. Clicking it navigated to
the same screen with `?from=suggestions`, so the title, the branch, the date
needed, the notes and every line typed by hand were gone — with no warning,
because a link is not a submit and the browser has nothing to warn about.

The global restore in `base.html` does not help: it replays a form after a
FAILED POST, and this was never a POST.

The label is `Fill from auto suggestions`. A person reads that as "add the
suggestions to what I have". What happened was "discard what you have and
start from the suggestions" — and the two are indistinguishable until you have
already lost the work.

So it posts now, and the server merges: whatever was typed is kept, and the
suggestions are appended to it. Nothing is lost and the label is true.

Merging rather than replacing also settles a smaller question the old
behaviour never had to answer: a material typed by hand that the suggestion
list also proposes must appear ONCE, with the quantity the person typed. They
looked at the shelf; the suggestion is arithmetic.
"""
import pytest


@pytest.fixture()
def low_stock(app, seed):
    """A material below its minimum, so there is something to suggest."""
    from app.config import db
    from app.models.models import Material, MaterialStock

    with app.app_context():
        material = Material(company_id=seed['company_id'],
                            material_code='VAI-LOW', name='Vai sap het',
                            min_stock_level=100, is_active=True)
        other = Material(company_id=seed['company_id'],
                         material_code='GO-LOW', name='Go sap het',
                         min_stock_level=50, is_active=True)
        db.session.add_all([material, other])
        db.session.flush()
        db.session.add(MaterialStock(material_id=material.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=5))
        db.session.add(MaterialStock(material_id=other.id,
                                     company_id=seed['company_id'],
                                     store_id=seed['store_id'],
                                     current_quantity=1))
        db.session.commit()
        return {**seed, 'low_id': str(material.id), 'other_id': str(other.id)}


def test_the_button_is_not_a_link_that_navigates_away():
    """The shape of the control is the bug.

    A link inside a form cannot carry the form with it, whatever the server
    does afterwards. Checked in the markup because that is where the data loss
    is decided.
    """
    import io
    import pathlib
    import re

    form = (pathlib.Path(__file__).resolve().parent.parent / 'app'
            / 'templates' / 'procurement' / 'pr_form.html')
    text = io.open(form, encoding='utf-8').read()

    inside = text[text.index('<form'):text.rindex('</form>')]
    links = re.findall(r'<a\s[^>]*href="[^"]*create_requisition[^"]*"', inside)
    assert not links, (
        'there is still a link inside the form that navigates to the '
        'requisition screen, so everything typed is discarded when it is '
        f'clicked: {links}')


def test_filling_from_suggestions_keeps_what_was_typed(app, client, login,
                                                       low_stock):
    """Title, branch, notes and hand-typed lines all survive."""
    login('admin')
    response = client.post('/requisitions/create', data={
        'action': 'fill_suggestions',
        'title': 'Bo sung vai thang 10',
        'notes': 'Gap, khach cho',
        'line_material_id[]': [low_stock['other_id']],
        'line_quantity[]': ['7'],
        'line_unit[]': ['m'],
    }, follow_redirects=True)

    body = response.get_data(as_text=True)
    assert 'Bo sung vai thang 10' in body, (
        'the title the user typed was thrown away')
    assert 'Gap, khach cho' in body, 'the notes were thrown away'
    assert low_stock['other_id'] in body, (
        'the line the user typed by hand was thrown away')


def test_the_suggestions_are_added_to_what_was_typed(app, client, login,
                                                     low_stock):
    """"Fill from suggestions" means add, which is what the label promises."""
    login('admin')
    body = client.post('/requisitions/create', data={
        'action': 'fill_suggestions',
        'title': 'Dat hang',
        'line_material_id[]': [low_stock['other_id']],
        'line_quantity[]': ['7'],
        'line_unit[]': ['m'],
    }, follow_redirects=True).get_data(as_text=True)

    assert low_stock['low_id'] in body, (
        'the suggested material was not added, so the button did nothing '
        'visible')
    assert low_stock['other_id'] in body, 'the typed line disappeared'


def test_a_material_typed_by_hand_is_not_duplicated(app, client, login,
                                                    low_stock):
    """They looked at the shelf; the suggestion is arithmetic.

    The person's own number wins, and the row appears once. Two rows for one
    material is a requisition that asks the supplier for it twice.
    """
    login('admin')
    body = client.post('/requisitions/create', data={
        'action': 'fill_suggestions',
        'title': 'Dat hang',
        'line_material_id[]': [low_stock['low_id']],
        'line_quantity[]': ['3'],
        'line_unit[]': ['m'],
    }, follow_redirects=True).get_data(as_text=True)

    assert body.count(f'value="{low_stock["low_id"]}" selected') <= 1, (
        'the material appears twice — once as typed and once as suggested — '
        'so the supplier is asked for it twice')
    assert 'value="3"' in body, (
        "the suggestion overwrote the quantity the person typed after "
        'looking at the shelf')


def test_saving_still_works(app, client, login, low_stock):
    """The new action must not swallow the ordinary submit."""
    from app.models.models import PurchaseRequisition

    login('admin')
    client.post('/requisitions/create', data={
        'title': 'De nghi binh thuong',
        'line_material_id[]': [low_stock['other_id']],
        'line_quantity[]': ['4'],
        'line_unit[]': ['m'],
    }, follow_redirects=True)

    with app.app_context():
        assert PurchaseRequisition.query.count() == 1, (
            'the ordinary save stopped working')
