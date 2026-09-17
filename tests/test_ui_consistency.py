"""Structural UI rules enforced as tests rather than as review comments.

These are the conventions that were being decided per-screen, which is how the
app drifted into looking like three separate products. A lint-style test keeps
a new screen from quietly opting out.
"""
import io
import pathlib

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'


def _templates_with_tables():
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        if '<table' in text:
            yield path, text


def test_every_table_is_inside_a_responsive_wrapper():
    """A table that can overflow must scroll, not break the page on a phone.

    Bootstrap requires an explicit `.table-responsive` wrapper; it is not a
    per-page judgement call.
    """
    offenders = [
        str(path.relative_to(TEMPLATES))
        for path, text in _templates_with_tables()
        if 'table-responsive' not in text
    ]
    assert offenders == [], (
        "these templates render a table with no .table-responsive wrapper, so "
        f"they will overflow horizontally on small screens: {offenders}"
    )


def test_no_template_reintroduces_a_local_status_colour_map():
    """Status colour belongs to app/utils/status_tokens.py, nowhere else.

    Before the shared vocabulary, `bg-warning` meant "delivered" on one screen
    and "unsigned" on another. Local `{'draft':'secondary', ...}` maps in a
    template are how that drift started.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        # A colour map is a dict literal mapping a status to a bootstrap colour.
        if "{% set colors" in text or "{%set colors" in text:
            offenders.append(str(path.relative_to(TEMPLATES)))

    assert offenders == [], (
        "these templates define their own status->colour map instead of using "
        f"status_badge()/status_meta(): {offenders}"
    )


@pytest.mark.parametrize("url", [
    '/orders',
    '/customers',
    '/materials/',
    '/purchase-orders',
    '/requisitions',
])
def test_core_list_pages_still_render(client, login, url):
    """Cheap smoke test that the structural edits did not break a page."""
    login("admin")
    resp = client.get(url)
    assert resp.status_code in (200, 302, 308), f"{url} returned {resp.status_code}"
