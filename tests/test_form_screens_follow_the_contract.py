"""A screen named `_form` is still a create screen.

`tests/test_screen_contract.py` classifies screens by FILENAME: a name holding
"create" is a create screen, "edit" an edit screen. `po_form.html` and
`pr_form.html` hold neither — one template serves both, switching on whether a
record was passed — so the two procurement forms were never in the contract at
all. The 44/44 that file reports was 44 of the screens it could see.

That matters because of what they were missing. Neither uses `form_actions()`,
so neither gets `.sofa-form-actions` — the rule that pins the save bar to the
bottom of the viewport. A purchase order with fifteen material lines pushes
Save off the screen, and a user who scrolls and loses the button cannot tell
whether their work was saved. That is the exact failure the sticky bar exists
to prevent, on the two screens the lint could not reach.

Same shape as the layout audit's screen list missing six screens, and as the
reachability check counting a form's own action as a link: a checker that
selects by name misses whatever is named differently.
"""
import io
import pathlib

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

# One template serving both create and edit. They are screens; the contract
# applies whatever they are called.
FORM_SCREENS = [
    'procurement/po_form.html',
    'procurement/pr_form.html',
]


@pytest.mark.parametrize('name', FORM_SCREENS)
def test_it_uses_the_shared_page_header(name):
    text = io.open(TEMPLATES / name, encoding='utf-8').read()
    assert 'page_header(' in text, (
        f'{name} hand-rolls its title, so it has no breadcrumb and puts a '
        'secondary action where every other screen puts the primary one')


@pytest.mark.parametrize('name', FORM_SCREENS)
def test_its_save_bar_is_pinned(name):
    """These forms grow a row per material line."""
    text = io.open(TEMPLATES / name, encoding='utf-8').read()
    assert 'form_actions(' in text, (
        f'{name} builds its own action row, so Save scrolls out of sight on a '
        'long order and the user cannot tell whether it saved')


def test_the_screen_contract_can_see_a_form_template():
    """Close the blind spot, not just the two screens behind it."""
    from tests.test_screen_contract import _screens

    seen = {name: kind for kind, name, _text in _screens()}
    for name in FORM_SCREENS:
        assert seen.get(name) in ('create', 'edit'), (
            f'{name} is classified as {seen.get(name)!r}, so the contract '
            'still does not apply to it')
