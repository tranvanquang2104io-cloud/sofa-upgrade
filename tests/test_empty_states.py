"""An empty screen must say the same thing everywhere it means the same thing.

Three procurement lists drew a blue `alert alert-info` strip for "chưa có đơn
mua nào" while orders, customers, materials and the rest use `empty_state()` —
a centred icon, the message, and a button that starts the thing you came to
make. All three templates already IMPORTED the macro and did not call it.

What this is NOT is a rule that every empty screen looks alike. Low Stock and
Purchase Suggestions show a GREEN banner when they have nothing, and that is
correct: "mọi vật tư đều trên mức tối thiểu" is good news, not an empty
cupboard. Making those match an empty order list would turn a reassurance into
a prompt to go and create something, which is the opposite of what they mean.

So the rule enforced here is narrower and truer: a screen that is empty because
the user has not made anything yet uses the shared empty state. A screen that is
empty because everything is fine says so in its own way.
"""
import io
import pathlib

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

# Empty because nothing has been created yet.
NOTHING_YET = [
    'procurement/po_list.html',
    'procurement/pr_list.html',
    'procurement/gr_list.html',
    'orders/list.html',
    'customers/list.html',
    'materials/list.html',
    'agreements/list.html',
    'payables/list.html',
    'production/list.html',
]

# Empty because there is nothing to worry about. Deliberately different.
NOTHING_WRONG = [
    'materials/purchase_suggestions.html',
]


@pytest.mark.parametrize('screen', NOTHING_YET)
def test_a_nothing_yet_screen_uses_the_shared_empty_state(screen):
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    assert 'empty_state(' in text, (
        f'{screen} draws its own "nothing here" instead of the shared one')


@pytest.mark.parametrize('screen', NOTHING_YET)
def test_a_nothing_yet_screen_does_not_also_hand_roll_one(screen):
    """Importing the macro and then not calling it is how these drifted."""
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    assert 'alert alert-info"><i class="bi bi-info-circle"></i> Chưa có' not in text, (
        f'{screen} still has its hand-written info strip')


@pytest.mark.parametrize('screen', NOTHING_WRONG)
def test_a_nothing_wrong_screen_stays_reassuring(screen):
    """Good news must not be dressed as a prompt to create something."""
    text = io.open(TEMPLATES / screen, encoding='utf-8').read()
    assert 'alert-success' in text, (
        f'{screen} no longer reads as "everything is fine"')
    assert 'empty_state(' not in text, (
        f'{screen} was made to look like an empty list, which inverts what it '
        'is telling the user')
