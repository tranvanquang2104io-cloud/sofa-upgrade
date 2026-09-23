"""A translation key must be a constant.

`t(f'Error: {e}')` builds a different key on every call, so it can never match
an entry in the dictionary — `t()` falls through and returns the f-string. The
call *looks* translated, which is why sixteen of these survived: nine wrapping
an English `Error: ...` prefix around an already-Vietnamese validation message,
four telling a Vietnamese user in English that a document number was taken.

The same trap has a second form, `t(variable)`, which put the workflow settings
screen into English — that one is caught by tests/test_settings_labels.py,
which reads the rendered page.

The fix in both cases is the same: keep the sentence constant and pass the
value in, `t('... %(number)s ...') % {'number': n}`.
"""
import io
import pathlib
import re

APP = pathlib.Path(__file__).resolve().parents[1] / 'app'

# `get(f'...')` ends with `t(`, so a naive search matches it. This bit me while
# writing the very sweep that produced this test.
DYNAMIC_KEY = re.compile(r"(?<![A-Za-z0-9_])t\(\s*f['\"]")


def test_no_translation_key_is_built_with_an_f_string():
    offenders = []
    for path in sorted(APP.rglob('*.py')):
        text = io.open(path, encoding='utf-8').read()
        for match in DYNAMIC_KEY.finditer(text):
            line = text[:match.start()].count('\n') + 1
            offenders.append(f"{path.relative_to(APP)}:{line}")

    assert offenders == [], (
        'an f-string is a new key every call, so these can never be '
        f'translated — use a placeholder and %: {offenders}')


def test_no_flash_message_shows_a_raw_exception_to_the_user():
    """`str(e)` on a bare `except Exception` is a stack-trace fragment.

    A deliberate `except ValueError` is different: the service raises those
    with a sentence meant for the person reading it, which is why the ones
    this product flashes are Vietnamese. It is the unfiltered catch-all that
    must not reach the screen — "(sqlite3.IntegrityError) UNIQUE constraint
    failed" tells the user nothing they can act on.
    """
    offenders = []
    for path in sorted(APP.rglob('*.py')):
        text = io.open(path, encoding='utf-8').read()
        lines = text.split('\n')
        broad = None
        for number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if re.match(r'except\s+(Exception|BaseException)\b', stripped):
                broad = len(line) - len(line.lstrip())
                continue
            if broad is not None:
                indent = len(line) - len(line.lstrip())
                if stripped and indent <= broad:
                    broad = None
                elif 'flash(' in stripped and re.search(r'\bstr\(\s*e\s*\)|%.*\be\b', stripped):
                    offenders.append(f"{path.relative_to(APP)}:{number}")

    assert offenders == [], (
        'these flash the text of an unexpected exception straight to a user '
        f'who cannot act on it: {offenders}')
