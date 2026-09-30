"""Three actions on the order screen ask twice, with two different sentences.

Approving a quotation, signing a contract and confirming a handover each carry
a `confirm()` on the FORM and another on the BUTTON inside it. One click, two
dialogs, and the two do not say the same thing:

    form:   "Approve this quotation? After approval it can no longer be edited."
    button: "Approve this quotation?"

The fuller sentence is the one worth reading, and it is the one that appears
SECOND — after the person has already dismissed a vaguer version of the same
question. By then they are clicking OK to make dialogs go away, which is
exactly the habit a confirmation exists to prevent.

For users who are not technical this is worse than an annoyance. Being asked
twice teaches that the first question did not count, and a person who learns
that stops reading the second one too.

What is kept: the form-level confirmation, because it carries the consequence
("...can no longer be edited"), which is the part that helps somebody decide.
"""
import io
import pathlib
import re

import pytest

ORDER_SCREEN = (pathlib.Path(__file__).resolve().parents[1] / 'app'
                / 'templates' / 'orders' / 'view.html')


def _text():
    return io.open(ORDER_SCREEN, encoding='utf-8').read()


def test_no_submit_button_confirms_on_top_of_its_own_form():
    """A form that confirms and a button that confirms is one click, two asks."""
    text = _text()

    offenders = []
    for match in re.finditer(r'<form\b.*?</form>', text, re.S):
        block = match.group(0)
        if 'onsubmit="return confirm(' not in block:
            continue
        if 'onclick="return confirm(' in block:
            line = text[:match.start()].count('\n') + 1
            offenders.append(line)

    assert not offenders, (
        f'forms starting at these lines confirm twice for one click: '
        f'{offenders}. The second dialog trains people to dismiss the first.')


def test_the_kept_sentence_is_the_one_that_names_the_consequence():
    """Asking once is only better if the surviving question is the useful one."""
    text = _text()

    assert 'After approval it can no longer be edited' in text, (
        'the quotation confirmation lost the sentence explaining what '
        'approving costs')
    assert 'A signed contract can no longer be edited' in text, (
        'the contract confirmation lost its consequence')


@pytest.mark.parametrize('action', ['approve', 'sign', 'confirm'])
def test_the_actions_still_work_after_the_dialogs_were_tidied(action):
    """The buttons must still submit; only the duplicate ask is removed."""
    text = _text()
    # The tooltip now goes through t() (it was English on Vietnamese screens).
    assert f"title=\"{{{{ t('{action.capitalize()}') }}}}\"" in text, (
        f'the {action} button disappeared along with its duplicate dialog')
