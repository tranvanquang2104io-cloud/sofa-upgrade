"""Tables of the same kind must read the same way.

Two things had drifted across the list screens.

**The header row had three weights.** `table-light` on four screens, no class
on three, and `table-dark` on Users — the only dark table header in the product,
which makes that one screen look like it belongs somewhere else.

**The action column was labelled three ways**, one of which was nothing at all:
"Actions", "Action", and a bare `<th></th>` on agreements, payables and
production. Both words render as "Thao Tác" in Vietnamese, so two of the three
differed only in the source; the empty one is the real defect — a screen reader
announcing that table gives the column no name, so a user navigating by column
hears a blank where every other table says what is there.

Alignment follows the buttons: they sit at the end of the row, so the header
does too.
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

LIST_SCREENS = [
    'orders/list.html',
    'customers/list.html',
    'materials/list.html',
    'users/list.html',
    'stores/list.html',
    'agreements/list.html',
    'payables/list.html',
    'production/list.html',
    'procurement/po_list.html',
    'procurement/pr_list.html',
    'procurement/gr_list.html',
]


def _thead(text):
    match = re.search(r'<thead([^>]*)>', text)
    return match.group(1).strip() if match else None


@pytest.mark.parametrize('screen', LIST_SCREENS)
def test_every_list_uses_the_same_header_weight(screen):
    attrs = _thead(io.open(TEMPLATES / screen, encoding='utf-8').read())
    if attrs is None:
        pytest.skip(f'{screen} has no table header')
    assert 'table-light' in attrs, (
        f'{screen} has a header row of a different weight: {attrs or "(none)"}')


@pytest.mark.parametrize('screen', LIST_SCREENS)
def test_no_list_has_an_unnamed_action_column(screen):
    """An empty <th> leaves a column with no name to announce."""
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    head = re.search(r'<thead.*?</thead>', text, re.S)
    if not head:
        pytest.skip(f'{screen} has no table header')
    assert '<th></th>' not in head.group(0), (
        f'{screen} has a column with no name, so a screen reader announces a '
        'blank where the actions are')
