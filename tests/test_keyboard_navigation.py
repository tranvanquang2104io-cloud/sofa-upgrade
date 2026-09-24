"""Two things that make the product unusable without a mouse.

**A filter that reloads on every arrow key.** `materials/list.html` submits its
form from the select's `onchange`. Opening that list with a keyboard and
arrowing down the categories fires `change` on each keystroke in browsers that
report it that way — and does so whenever assistive technology sets the value
directly — so the page reloads under the user before they reach the option they
want. The filter cannot be operated without a pointing device. WCAG 3.2.2.

**No skip link.** The navigation is the first focusable thing on all 47 screens:
five items plus three dropdowns, around twenty stops. A keyboard user pays that
on every single page load, and the flash message that confirms their save sits
*after* it. WCAG 2.4.1.

Neither is exotic. A workshop clerk with a trackpad that has stopped working,
or anyone who fills forms by keyboard because it is faster, hits both daily.
"""
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'


def test_no_filter_submits_itself_on_change():
    """A select that reloads the page cannot be arrowed through."""
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for match in re.finditer(r'<select[^>]*onchange="[^"]*submit\(\)', text):
            line = text[:match.start()].count('\n') + 1
            offenders.append(f"{'/'.join(path.relative_to(TEMPLATES).parts)}:{line}")

    assert offenders == [], (
        'these reload the page on every arrow key, so the filter cannot be '
        f'used from the keyboard: {offenders}')


def test_the_filter_still_has_a_way_to_apply_itself():
    """Removing the auto-submit must not remove the ability to filter."""
    text = io.open(TEMPLATES / 'materials' / 'list.html', encoding='utf-8').read()
    assert 'type="submit"' in text, (
        'the category filter can no longer be applied at all')


def test_there_is_a_skip_link():
    text = io.open(TEMPLATES / 'base.html', encoding='utf-8').read()
    assert 'skip-link' in text, (
        'a keyboard user re-tabs the whole navigation on every page')


def test_the_skip_link_is_the_first_focusable_thing():
    """A skip link after the navigation skips nothing."""
    text = io.open(TEMPLATES / 'base.html', encoding='utf-8').read()
    skip = text.find('skip-link')
    nav = text.find('<nav')
    assert skip != -1 and nav != -1
    assert skip < nav, 'the skip link comes after the navigation it skips'


def test_the_skip_link_points_at_the_content(app, client, login, seed):
    """And the target has to exist, or the link moves focus nowhere."""
    login('admin')
    body = client.get('/orders').get_data(as_text=True)

    link = re.search(r'class="skip-link"[^>]*href="#([^"]+)"', body)
    assert link, 'the skip link did not render'
    target = link.group(1)
    assert f'id="{target}"' in body, (
        f'the skip link points at #{target}, which is not on the page')
