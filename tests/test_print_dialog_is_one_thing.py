"""The same button must produce the same kind of file, wherever it is pressed.

The print dialog is copied nine times across five templates — six of them
inside `orders/view.html` alone — and the copies had drifted. The four document
screens list DOCX first, so DOCX is what you get. The order screen lists PDF
first.

So printing a quotation from the order screen gives a PDF, and printing the
same quotation from the quotation screen gives a Word file. The user then looks
for what they made in Generated Documents and finds the other one. Nothing on
either screen says the two buttons differ.

DOCX is the default the majority already used, and the one that matches how the
product works: the templates ARE .docx, and a Vietnamese business commonly
tweaks the wording before it prints.

Nine copies is also why this drifted at all, so the dialog becomes one macro.
A change to it now lands everywhere instead of on whichever copies somebody
remembered.
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

SCREENS = [
    'orders/view.html',
    'quotations/view.html',
    'contracts/view.html',
    'handover/view.html',
    'payments/view.html',
]


def _format_selects(text):
    """Every format dropdown in a template, with its options in order."""
    found = []
    for match in re.finditer(r'<select[^>]*name="format"[^>]*>(.*?)</select>',
                             text, re.S):
        found.append(re.findall(r'<option value="([a-z]+)"', match.group(1)))
    return found


@pytest.mark.parametrize('screen', SCREENS)
def test_every_print_dialog_defaults_to_the_same_format(screen):
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    for options in _format_selects(text):
        assert options and options[0] == 'docx', (
            f'{screen} offers {options[0]} first; every other screen offers '
            'docx, so the same button gives a different file here')


def test_the_dialog_is_defined_once():
    """Nine copies is why the default drifted in the first place."""
    copies = 0
    for path in sorted(TEMPLATES.rglob('*.html')):
        if 'macros' in path.parts:
            continue
        text = io.open(path, encoding='utf-8').read()
        copies += len(_format_selects(text))

    assert copies == 0, (
        f'{copies} hand-written format dropdowns remain outside the macro'
    )


def test_the_macro_exists_and_carries_the_default():
    text = io.open(TEMPLATES / 'macros' / 'ui.html', encoding='utf-8').read()
    assert 'macro generate_document_modal' in text
    options = _format_selects(text)
    assert options, 'the macro has no format dropdown'
    assert options[0][0] == 'docx'
