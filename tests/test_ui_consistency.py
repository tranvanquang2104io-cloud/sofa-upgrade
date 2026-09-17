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


# --- shared document-form helpers ----------------------------------------

SHARED_JS_FUNCS = ('fmtNum', 'parseRawFee', 'numberToWordsVi')


def test_shared_doc_utils_is_loaded_globally():
    base = io.open(TEMPLATES / 'base.html', encoding='utf-8').read()
    assert 'sofa-doc-utils.js' in base, (
        "the shared helpers must be loaded from base.html, before any inline "
        "page script that calls them"
    )


def test_shared_helpers_are_defined_exactly_once_in_the_codebase():
    """They used to be copy-pasted: fmtNum x7, numberToWordsVi x4.

    A fix to the Vietnamese number-to-words rules must land in one place.
    """
    static_js = (TEMPLATES.parent / 'static' / 'js' / 'sofa-doc-utils.js')
    shared = io.open(static_js, encoding='utf-8').read()

    for func in SHARED_JS_FUNCS:
        assert f'function {func}' in shared, f"{func} missing from the shared module"

    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for func in SHARED_JS_FUNCS:
            if f'function {func}' in text:
                offenders.append(f"{path.relative_to(TEMPLATES)}:{func}")

    assert offenders == [], (
        "these templates redefine a helper that now lives in "
        f"static/js/sofa-doc-utils.js: {offenders}"
    )


@pytest.mark.parametrize("template", [
    'quotations/create.html', 'quotations/edit.html',
    'contracts/create.html', 'contracts/edit.html',
    'handover/create.html', 'handover/edit.html',
    'payment/create.html', 'payments/edit.html',
])
def test_document_templates_still_parse(app, template):
    """Removing inline JS must not have broken the Jinja syntax."""
    with app.app_context():
        app.jinja_env.get_template(template)


def test_shared_helpers_load_before_the_content_block():
    """Ordering hazard guard.

    Every document template puts its inline <script> inside {% block content %},
    so a helper loaded at the end of <body> would be parsed AFTER it. That works
    only while no template calls a helper at top level. Keeping the script above
    the content block removes the hazard.
    """
    base = io.open(TEMPLATES / 'base.html', encoding='utf-8').read()
    content_block = '{%' + ' block content ' + '%}'
    assert base.index('sofa-doc-utils.js') < base.index(content_block), (
        "sofa-doc-utils.js must be loaded before {% block content %}, since "
        "templates put their inline scripts inside that block"
    )


UI_MACROS = ('page_header', 'status_badge', 'order_badge', 'process_stepper',
             'search_bar', 'empty_state', 'table_open', 'table_close')


def test_templates_import_every_ui_macro_they_call():
    """Calling a macro without importing it is a render-time crash.

    Jinja resolves macro names lazily, so a missing `{% from ... import %}`
    only shows up when a user opens that exact page. This catches it at build
    time instead.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        if 'macros' in path.parts:      # the macro library defines them
            continue
        import_lines = '\n'.join(
            l for l in text.splitlines() if 'macros/ui.html' in l)
        for macro in UI_MACROS:
            if f'{macro}(' in text and macro not in import_lines:
                offenders.append(f"{path.relative_to(TEMPLATES)}:{macro}")

    assert offenders == [], (
        "these templates call a UI macro they never imported, so the page "
        f"crashes when opened: {offenders}"
    )


def test_ui_macros_are_imported_with_context():
    """`with context` is required: the macros use context-injected helpers."""
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for line in text.splitlines():
            if 'macros/ui.html' in line and 'import' in line \
                    and 'with context' not in line:
                offenders.append(str(path.relative_to(TEMPLATES)))
    assert offenders == [], (
        "macros/ui.html must be imported `with context`, or the helpers it "
        f"calls (t, status_meta, token_class) are undefined: {offenders}"
    )
