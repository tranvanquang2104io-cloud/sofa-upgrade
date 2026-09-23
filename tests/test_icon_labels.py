"""A button that is only an icon must still say what it does.

Found by reading the rendered DOM: 68 controls across the product were nothing
but an `<i class="bi-...">`. On screen they are a pencil or a bin with no
words; to a screen reader they are an empty button, and on hover they say
nothing at all. For an audience that is not technically minded, "the small red
icon" is the entire label — and the icon alone does not distinguish "remove
this line from the form I am filling in" from "delete this record".

`title` gives the hover tooltip, `aria-label` gives the accessible name. Both,
because neither substitutes for the other.

This closes the class rather than the 68 instances. Adding a new icon-only
control is fine; leaving it unnamed is not.
"""
import io
import pathlib
import re

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

# An <a> or <button> whose entire body is a single icon element.
ICON_ONLY = re.compile(r'<(a|button)\b([^>]*)>\s*<i\b[^>]*></i>\s*</\1>')
CLOSE_BUTTON = re.compile(r'<button[^>]*\bclass="[^"]*\bbtn-close\b[^"]*"[^>]*>')


def _offenders(pattern, attribute):
    found = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for match in pattern.finditer(text):
            if attribute in match.group(0):
                continue
            line = text[:match.start()].count('\n') + 1
            found.append(f"{'/'.join(path.relative_to(TEMPLATES).parts)}:{line}")
    return found


def test_every_icon_only_control_has_an_accessible_name():
    offenders = _offenders(ICON_ONLY, 'aria-label')
    assert offenders == [], (
        'these controls are an icon and nothing else, so a screen reader '
        f'announces an empty button: {offenders}')


def test_every_icon_only_control_has_a_hover_tooltip():
    """Sighted users get no words either until they click and find out."""
    offenders = _offenders(ICON_ONLY, 'title=')
    assert offenders == [], (
        f'these icon-only controls have no hover tooltip: {offenders}')


def test_every_modal_close_button_is_named():
    """`btn-close` renders as a bare X with no text node at all."""
    offenders = _offenders(CLOSE_BUTTON, 'aria-label')
    assert offenders == [], (
        f'these close buttons have no accessible name: {offenders}')
