"""A line-item row is written once, and the "add row" path uses that one.

Five screens shared a line-item schema and carried nine copies of the row
between them — each screen had TWO: one built by Jinja when the page loads,
one built by a JavaScript template literal when the user presses "Thêm dòng".
Nobody had to be careless for those to drift, and they had: the name box read
"Item name / work" on five and "goods" on two, and the remove button was
`bi-x` in some copies and `bi-trash` in others.

Adding the per-line VAT column by hand would have turned nine copies into nine
more complicated copies, and made the next line-item change a nine-place
change. So the markup moved into `_item_row.html`, and the JavaScript path
clones the rendered template instead of rebuilding it.

Handover is deliberately not part of this. Its rows carry delivered quantity,
accepted quantity, a status and a rejection reason, and no `item_quantity[]`
at all; it has its own parser for that reason. A macro with two shapes would
be a copy again with extra steps.

What is pinned here:

* the converted screens contain no hand-written `item_price[]` input — that is
  the mechanical form of "there is one source";
* the row a screen ADDS carries the same fields as the row it LOADS, which is
  the property the two copies kept losing;
* the VAT column is hidden on a document that does not use it, and the inputs
  are still submitted while hidden, because empty means "use the document's
  rate" and a missing input would mean something else entirely.
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

# Screens converted so far. Adding a screen to the macro means adding it here.
CONVERGED = ['quotations/create.html', 'payments/create.html']

# Not converged and not wrong: a different row schema, with its own parser.
DIFFERENT_BY_DESIGN = ['handover/create.html', 'handover/edit.html']


def _text(name):
    return io.open(TEMPLATES / name, encoding='utf-8').read()


@pytest.mark.parametrize('screen', CONVERGED)
def test_the_screen_does_not_write_its_own_row(screen):
    text = _text(screen)
    assert 'name="item_price[]"' not in text, (
        f'{screen} still writes a line-item row by hand, so there are two '
        'sources for it again')


@pytest.mark.parametrize('screen', CONVERGED)
def test_the_screen_uses_the_macro(screen):
    text = _text(screen)
    assert 'item_row(' in text, f'{screen} does not render the shared row'
    assert 'item_row_head(' in text, (
        f'{screen} writes its own header, which would lose the VAT column when '
        'the body gains it')


@pytest.mark.parametrize('screen', CONVERGED)
def test_the_added_row_comes_from_the_rendered_template(screen):
    """The JS path must clone, not rebuild — rebuilding is how they drifted."""
    text = _text(screen)
    assert 'item_row_template(' in text, (
        f'{screen} has no row template for the add-row path to clone')
    assert 'cloneItemRow(' in text, (
        f'{screen} builds the added row some other way')
    # Scoped to a row, not to the file: the payment screen builds an unrelated
    # bank-account block from a template literal, and the first version of this
    # assertion failed on that — reporting a converged screen as unconverged.
    row_literals = re.findall(r'innerHTML = `[^`]*`', text, re.S)
    offenders = [b for b in row_literals if 'item_price[]' in b]
    assert offenders == [], (
        f'{screen} still assembles a line-item row from a string literal')


@pytest.mark.parametrize('screen', DIFFERENT_BY_DESIGN)
def test_the_handover_rows_are_left_alone(screen):
    """Pinned so a later tidy-up does not fold a different schema into this."""
    text = _text(screen)
    assert 'item_delivered_qty[]' in text, (
        f'{screen} lost the delivered/accepted columns that make it a '
        'different row')
    assert 'item_row(' not in text, (
        f'{screen} was folded into the shared macro, which only fits by '
        'giving the macro a second shape')


def test_the_row_macro_offers_the_image_cell_both_ways():
    """A quotation row carries an image; a payment row does not."""
    macro = _text('_item_row.html')
    assert 'with_image' in macro


def test_the_vat_column_is_hidden_but_still_submitted():
    """Hidden must mean hidden, not absent.

    An empty `item_vat_rate[]` means "use the document's rate". An input that
    is not in the DOM at all sends nothing, and the parser cannot tell the
    two apart by position — the rates would land on the wrong lines.
    """
    css = io.open(
        pathlib.Path(__file__).resolve().parents[1] / 'app' / 'static' / 'css'
        / 'style.css', encoding='utf-8').read()
    rule = re.search(r'\.item-table\.vat-per-line-off\s+\.vat-cell\s*\{([^}]*)\}',
                     css)
    assert rule, 'nothing hides the VAT column, so every screen grew one'
    assert 'display' in rule.group(1)

    macro = _text('_item_row.html')
    assert 'name="item_vat_rate[]"' in macro, 'the row has no VAT input at all'
    assert 'type="hidden"' not in re.search(
        r'<input[^>]*item_vat_rate\[\][^>]*>', macro).group(0), (
        'the VAT input is type=hidden, so the user could never type in it')


@pytest.mark.parametrize('screen', CONVERGED)
def test_a_rejected_form_brings_the_line_items_back(screen):
    """What the user typed survives a refusal — rates included.

    Adding the payment screen to CONVERGED made this fail, and the failure was
    right: that screen kept ONLY the document number on a rejection and threw
    away every line item, date, note and fee. The defect was fixed for the
    quotation alone; contract and handover still have it, recorded in
    REFACTOR-2026Q3.md.

    A rate typed on a line and lost on a rejection is the same defect as the
    line items that used to vanish, one field later — so the two are asserted
    together rather than letting the rates be rebuilt into rows that are
    themselves gone.
    """
    text = _text(screen)
    assert "getlist('item_name[]')" in text, (
        f'{screen} throws away the line items the user typed when the server '
        'refuses the form')
    assert "getlist('item_vat_rate[]')" in text, (
        f'{screen} rebuilds the lines but drops the rates typed on them')


def test_the_create_page_renders_the_column_off(client, login, app, seed):
    """The markup checks above say what the source contains; this says what a
    user is served."""
    import datetime as dt

    from app.config import db
    from app.models import Order

    login('admin')
    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-ROW',
                      title='Sofa góc L')
        db.session.add(order)
        db.session.commit()
        order_id = str(order.id)

    body = client.get(f'/quotations/{order_id}/create').get_data(as_text=True)
    assert 'vat-per-line-off' in body, (
        'the VAT column is shown to every user on every document')
    assert 'name="item_vat_rate[]"' in body, 'the VAT input was not rendered'
    assert 'itemRowTemplate' in body, 'the add-row template was not rendered'
    assert body.count('name="item_price[]"') >= 2, (
        'the page should carry one row plus the template row')
