"""Structural UI rules enforced as tests rather than as review comments.

These are the conventions that were being decided per-screen, which is how the
app drifted into looking like three separate products. A lint-style test keeps
a new screen from quietly opting out.
"""
import io
import pathlib
import re

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


STATUS_WORDS = {
    'draft', 'pending', 'sent', 'approved', 'signed', 'unsigned', 'confirmed',
    'unconfirmed', 'paid', 'partial', 'rejected', 'cancelled', 'canceled',
    'expired', 'new', 'completed', 'delivered', 'fully paid',
    'contract signed', 'quotation approved', 'advance paid', 'submitted',
    'ordered', 'received', 'converted', 'pending approval',
}

# `<span class="badge bg-success">{{ t('Signed') }}</span>` and friends.
_INLINE_BADGE = re.compile(
    r"""<span[^>]*class="[^"]*badge[^"]*bg-[a-z]+[^"]*"[^>]*>\s*"""
    # an icon may sit between the tag and the label — `<i class="bi bi-x"></i>`
    r"""(?:<i[^>]*></i>\s*)?"""
    r"""\{\{\s*t\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def test_no_template_paints_a_status_badge_by_hand():
    """The colour map catches `{% set colors %}`; this catches the other shape.

    Every offender found so far was an inline ``{% if %}/{% else %}`` chain
    with the colour written straight into the class, which is exactly why
    `payments/view` showed "Draft" amber while the token map calls draft
    neutral, and why `dashboard/index` had no "Advance Paid" branch at all —
    the chain was maintained by hand and fell behind the real lifecycle.

    A status word inside a hardcoded `badge bg-*` is therefore a lint failure:
    use `doc_badge()` / `order_badge()` / `status_badge()`.

    Labels that are not a document status ("3-way match: OK", "Paid in full")
    are deliberately not listed in STATUS_WORDS — they are prose, not state.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        if 'macros' in path.parts:
            continue                      # the macros ARE the one place
        text = io.open(path, encoding='utf-8').read()
        for label in _INLINE_BADGE.findall(text):
            if label.strip().lower() in STATUS_WORDS:
                offenders.append(f"{path.relative_to(TEMPLATES)}: {label}")

    assert offenders == [], (
        "these templates hardcode a status badge colour instead of going "
        f"through the shared token map: {offenders}"
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
    'payments/create.html', 'payments/edit.html',
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


# --- i18n -----------------------------------------------------------------

def test_procurement_templates_have_no_bare_vietnamese_headings():
    """Procurement/production were built outside the i18n discipline.

    This catches a LABEL left as raw Vietnamese — a heading, column header,
    button or field label that sits alone inside an element.

    Deliberately NOT covered: sentence FRAGMENTS, i.e. prose split across
    inline tags such as `... đơn mua đã gửi NCC <strong>và bấm</strong> ...`.
    Those cannot be translated piece by piece, because word order differs
    between the two languages — translating "và bấm" alone would produce
    nonsense in English. Fixing them means rewriting the sentence to hold a
    single t() call, which is a copy change, not a mechanical one. Tracked as
    T13-remainder.
    """
    import re

    diacritics = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ'
    # text that is the WHOLE content of an element and is short (a label)
    pattern = re.compile(r'>\s*([^<>{}]{1,24})\s*<')

    offenders = []
    for sub in ('procurement', 'production'):
        for path in sorted((TEMPLATES / sub).glob('*.html')):
            text = io.open(path, encoding='utf-8').read()
            for match in pattern.finditer(text):
                label = match.group(1).strip()
                if not label or '{{' in label:
                    continue
                if not any(ch in diacritics for ch in label):
                    continue
                # A fragment continues a sentence started outside this tag:
                # it begins lower-case and is not a standalone label.
                if label[0].islower():
                    continue
                offenders.append(f"{path.name}: {label!r}")

    assert offenders == [], (
        "these short labels are still hardcoded Vietnamese instead of going "
        f"through t(): {offenders}"
    )


def test_every_translation_key_used_in_procurement_templates_exists():
    """A t('...') call with no entry renders the English key to a VI user."""
    import re
    from app.utils.i18n import TRANSLATIONS

    vi = TRANSLATIONS['vi']
    missing = []
    for sub in ('procurement', 'production'):
        for path in sorted((TEMPLATES / sub).glob('*.html')):
            text = io.open(path, encoding='utf-8').read()
            # only Jinja calls, not JS like createElement('tr')
            for key in re.findall(r"\{\{-?\s*t\('([^']+)'\)", text):
                if key not in vi:
                    missing.append(f"{path.name}: {key!r}")

    assert missing == [], (
        f"these t() keys have no Vietnamese translation registered: {missing}"
    )


# --- template directory naming -------------------------------------------

def test_no_singular_plural_duplicate_template_directories():
    """`payment/` and `payments/` both existed for the same concept.

    Two directories for one thing means a developer has to guess which holds
    the screen they want, and screens for the same entity drift apart.
    Everything else here is plural (orders, quotations, contracts, customers),
    so plural is the convention.
    """
    dirs = {p.name for p in TEMPLATES.iterdir() if p.is_dir()}
    offenders = sorted(d for d in dirs if d + 's' in dirs)
    assert offenders == [], (
        "these template directories exist in both singular and plural form: "
        f"{offenders}"
    )


@pytest.mark.parametrize("template", [
    'payments/create.html', 'payments/edit.html', 'payments/view.html',
])
def test_payment_templates_live_together_and_parse(app, template):
    with app.app_context():
        app.jinja_env.get_template(template)


def test_no_bare_vietnamese_in_javascript_confirm_dialogs():
    """A confirm() message is UI text like any other.

    These were missed by the first i18n pass because they live inside an HTML
    attribute rather than in a text node, which is exactly the kind of place a
    language gap hides.
    """
    import re

    diacritics = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ'
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for msg in re.findall(r"confirm\('([^']*)'\)", text):
            if '{{' in msg:
                continue
            if any(ch in diacritics for ch in msg):
                offenders.append(f"{path.relative_to(TEMPLATES)}: {msg!r}")

    assert offenders == [], (
        f"these confirm() dialogs are hardcoded Vietnamese: {offenders}"
    )


def test_no_template_builds_its_own_status_label_dict():
    """Status LABELS belong to status_tokens.py, like status colours.

    Local `{% set labels = {'draft':'Nháp', ...} %}` dicts were the last place
    a status could be worded differently on one screen than another.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for marker in ('{% set labels', '{% set status_labels'):
            if marker in text:
                offenders.append(str(path.relative_to(TEMPLATES)))

    assert offenders == [], (
        "these templates define their own status->label map instead of using "
        f"status_meta(): {offenders}"
    )


# --- long forms must keep Save reachable ---------------------------------

LONG_FORM_MIN_LINES = 250


def test_long_forms_pin_their_save_button():
    """On a 400-line form the Save button ends up below the fold.

    A user who is not confident with computers scrolls, loses the button, and
    cannot tell whether the form was saved. `.sofa-form-actions` pins the
    action row to the bottom of the viewport while there is still form below.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        # Only data-entry screens. A view page's buttons sit next to the thing
        # they act on; pinning those would be wrong, not helpful.
        if path.name not in ('create.html', 'edit.html', 'company.html'):
            continue
        text = io.open(path, encoding='utf-8').read()
        if 'type="submit"' not in text:
            continue
        if len(text.splitlines()) < LONG_FORM_MIN_LINES:
            continue
        if 'sofa-form-actions' not in text:
            offenders.append(
                f'{path.relative_to(TEMPLATES)} ({len(text.splitlines())} lines)')

    assert offenders == [], (
        "these forms are long enough to push Save below the fold but do not "
        f"pin it: {offenders}"
    )


def test_the_sticky_action_style_exists():
    css = io.open(TEMPLATES.parent / 'static' / 'css' / 'style.css',
                  encoding='utf-8').read()
    assert '.sofa-form-actions' in css
    assert 'position: sticky' in css


@pytest.mark.parametrize("template", [
    'contracts/create.html', 'handover/create.html',
    'quotations/create.html', 'payments/create.html',
    'agreements/create.html', 'settings/company.html',
])
def test_forms_with_a_pinned_save_bar_still_parse(app, template):
    with app.app_context():
        app.jinja_env.get_template(template)


# Actions a non-technical user cannot undo by pressing the same button again.
# Deliberately NOT every POST: create/edit forms are the user's own deliberate
# submission, and confirming those would be the clutter the product is trying
# to avoid.
IRREVERSIBLE_ACTIONS = (
    'sign_contract', 'cancel_contract', 'cancel_handover', 'cancel_payment',
    'cancel_order', 'cancel_quotation', 'confirm_handover', 'confirm_payment',
    'approve_quotation', 'skip_advance_payment', 'activate_template',
    'deactivate_template', 'issue_plan_materials',
)


def _form_around(text, pos):
    start = text.rfind('<form', 0, pos)
    end = text.find('</form>', pos)
    return (text[start:end], text[:start]) if start >= 0 and end >= 0 else (None, None)


def test_every_irreversible_action_asks_first():
    """The product's own rule: a change the user cannot take back must confirm.

    Two ways count, and both are used in the app already — an onsubmit
    confirm(), or a form that lives inside a Bootstrap modal (the modal IS the
    confirmation, and is the better one because it can show what is about to
    change and collect a reason).

    This caught `activate_template`, whose twin `deactivate_template` asked but
    which did not — and activating silently decides which .docx every future
    document is printed from.
    """
    offenders = []
    for path in sorted(TEMPLATES.rglob('*.html')):
        text = io.open(path, encoding='utf-8').read()
        for action in IRREVERSIBLE_ACTIONS:
            for match in re.finditer(r"url_for\('[a-z_]+\.%s'" % action, text):
                form, before = _form_around(text, match.start())
                if form is None:
                    continue
                asks = ('confirm(' in form
                        or 'data-bs-dismiss="modal"' in form
                        or 'data-bs-toggle="modal"' in form
                        or 'modal' in before[-1200:])
                if not asks:
                    offenders.append(f"{path.relative_to(TEMPLATES)}: {action}")
                break

    assert offenders == [], (
        "these actions change something the user cannot undo without asking "
        f"first: {offenders}"
    )
