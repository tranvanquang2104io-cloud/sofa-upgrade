"""The same row action must look the same on every list.

The owner's requirement from the start: cùng một loại chức năng phải hiển thị
giống nhau ở mọi nơi. Five treatments were live:

    orders       solid btn-info (View) + solid btn-danger (Cancel)
    materials    solid btn-info + solid btn-warning (Edit)
    customers    btn-outline-primary / btn-outline-secondary, icon only
    stores       btn-outline-primary / btn-outline-danger
    users        a btn-group
    agreements, payables, production   btn-outline-secondary with the word View

Two things go wrong with the solid ones. A user learns on Orders that "the
coloured button in the row opens it", then on Agreements looks for a colour
that is not there. And two solid buttons per row compete with the page's own
primary action — the thing the header exists to make obvious.

The convergence is on what the majority already does: an outline button for a
row action. Destructive actions keep `btn-outline-danger`, because flattening
"open" and "cancel" into one appearance would be the opposite of the point.
Colour still means something; it just stops being the thing that says "this is
a button".
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

LIST_SCREENS = [
    'orders/list.html',
    'materials/list.html',
    'customers/list.html',
    'stores/list.html',
    'agreements/list.html',
    'payables/list.html',
    'production/list.html',
    'procurement/po_list.html',
    'procurement/pr_list.html',
    'procurement/gr_list.html',
]

# A row action is an outline button. Solid colour belongs to the page's one
# primary action, in the header.
SOLID = re.compile(r'class="[^"]*\bbtn-(info|warning|success|primary|danger)\b[^"]*"')


def _rows_section(text):
    """Only what is inside the table body — the header's button is allowed."""
    match = re.search(r'<tbody>(.*?)</tbody>', text, re.S)
    return match.group(1) if match else ''


@pytest.mark.parametrize('screen', LIST_SCREENS)
def test_row_actions_are_outline_buttons(screen):
    body = _rows_section(io.open(TEMPLATES / screen, encoding='utf-8').read())
    if not body:
        pytest.skip(f'{screen} has no table body to check')

    offenders = []
    for match in re.finditer(r'class="([^"]*\bbtn\b[^"]*)"', body):
        classes = match.group(1)
        if 'btn-outline-' in classes or 'btn-close' in classes:
            continue
        if SOLID.search('class="%s"' % classes):
            offenders.append(classes.strip())

    assert offenders == [], (
        f'{screen} uses a solid button for a row action, which competes with '
        f'the page\'s primary action: {sorted(set(offenders))}')


def test_a_destructive_row_action_is_still_distinguishable():
    """Converging appearance must not flatten meaning."""
    body = _rows_section(
        io.open(TEMPLATES / 'orders/list.html', encoding='utf-8').read())
    assert 'btn-outline-danger' in body, (
        'cancelling an order now looks the same as opening it')
