"""Printing looks and works the same on every screen that prints.

The owner: *"mọi loại form in hay chứng từ được in đều phải dùng loại A, nó là
quy chuẩn của app ngay từ đầu rồi, nên mới nói phải làm đồng bộ tất cả các
feature xung quanh cái chức năng in này giống nhau ở mọi loại màn hình (nút
nhấn in, màn hình lịch sử file đã in, popup, ...)"*.

Measured before changing anything — there were THREE shapes, not two:

1. the shared `generate_document_modal` macro, a format choice, and the
   "Tài liệu đã tạo" history block — quotation, contract, handover, payment;
2. a hand-written link straight to `generate_document`, no format choice and
   no history — framework agreement (HĐNT) and order confirmation (ĐĐH);
3. a hand-written link to a hardcoded builder that streams a file and records
   nothing at all — purchase order and production plan.

Shape 3 is not a variation on printing, it is a different feature wearing the
same word. Nothing is stored, so there is no history to show, no version to
record, and nowhere for a signature to attach later. Shape 2 is the same
feature with two of its parts missing, which is how a user learns that the
product behaves differently depending on which document they are looking at.

What is pinned:

* every screen that prints uses the shared macro, so the button, the popup and
  the format choice cannot drift apart;
* every screen that prints shows what has already been printed from it. A
  document with no history is one where nobody can answer "which version did
  we send them?";
* the hardcoded builders are gone, or listed here as known exceptions with the
  reason — never simply absent, because absence is what let them sit unnoticed.

`MIGRATING` is the honest part of this file: the screens not converged yet are
named, so the gap is a number somebody can watch go down rather than a
discovery somebody makes later.
"""
import io
import pathlib

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'

#: Screens that print, and print the one way.
CONVERGED = [
    'quotations/view.html',
    'contracts/view.html',
    'handover/view.html',
    'payments/view.html',
    'agreements/view.html',
]

#: Screens that print and have not been converged yet. Each line is a debt,
#: and removing a line is the definition of done for that screen.
MIGRATING = {
    'procurement/po_view.html': 'PO: hardcoded builder, stores nothing',
    'production/plan.html': 'Lệnh sản xuất: hardcoded builder, stores nothing',
}

#: Print controls that live INSIDE a screen listed above rather than being the
#: screen's own. `orders/view.html` uses the shared macro six times and then
#: hand-wrote a seventh control for the ĐĐH — in the same file. It was in
#: neither list, so nothing watched it, which is the same blind spot this file
#: exists to close one level down.
EMBEDDED_CONTROLS = {
    'orders/view.html': 'order_confirmation',
}


def _text(screen):
    return io.open(TEMPLATES / screen, encoding='utf-8').read()


@pytest.mark.parametrize('screen', CONVERGED)
def test_the_print_control_comes_from_the_shared_macro(screen):
    text = _text(screen)
    assert 'generate_document_modal' in text, (
        f'{screen} builds its own print control, so the button and the popup '
        'can drift from every other screen')


@pytest.mark.parametrize('screen', CONVERGED)
def test_the_screen_shows_what_has_already_been_printed(screen):
    text = _text(screen)
    assert '_generated_documents.html' in text, (
        f'{screen} prints and shows no history, so nobody can answer "which '
        'version did we send them?"')


@pytest.mark.parametrize('screen', CONVERGED)
def test_no_converged_screen_links_to_a_hardcoded_builder(screen):
    text = _text(screen)
    for builder in ('print_purchase_order', 'print_production_plan'):
        assert builder not in text, (
            f'{screen} reaches a hardcoded builder, which stores nothing and '
            'can carry neither a version nor a signature')


def test_the_unconverged_screens_are_named_not_forgotten():
    """A debt nobody wrote down is a debt nobody pays.

    This fails when a screen is converged and the line is left behind, which
    keeps the list honest in both directions.
    """
    for screen, why in MIGRATING.items():
        text = _text(screen)
        converged = ('generate_document_modal' in text
                     and '_generated_documents.html' in text)
        assert not converged, (
            f'{screen} now prints the standard way — remove it from MIGRATING '
            f'and add it to CONVERGED. Recorded reason was: {why}')


def test_the_shared_macro_offers_both_formats():
    """One popup, and it must not quietly become docx-only.

    An earlier pass removed a dead `pdf` option from four hand-written copies
    of this dialog; the macro exists so that cannot happen unevenly again.
    """
    macro = _text('macros/ui.html')
    start = macro.index('{% macro generate_document_modal(')
    body = macro[start:macro.index('{% endmacro %}', start)]
    assert 'docx' in body
    assert 'pdf' in body, (
        'the shared dialog no longer offers PDF, so every screen lost it at '
        'once')


@pytest.mark.parametrize('screen', sorted(EMBEDDED_CONTROLS))
def test_a_control_inside_another_screen_uses_the_macro_too(screen):
    """A hand-written form in a file that otherwise uses the macro.

    `orders/view.html` calls `generate_document_modal` six times and then
    posts to `generate_document` directly for the ĐĐH, with the format
    hardcoded. Being inside a converged screen is what hid it: the file passes
    every check above while one of its seven print controls is not the
    standard one.
    """
    text = _text(screen)
    doc_type = EMBEDDED_CONTROLS[screen]

    assert f"doc_type='{doc_type}'" not in text, (
        f'{screen} still posts straight to generate_document for '
        f'{doc_type}, so that one control has no format choice and cannot '
        f'pick up any change made to the shared popup')


def test_every_screen_that_prints_is_accounted_for():
    """No screen prints without appearing in one of these three lists.

    The lists are hand-written, which is the failure mode this repo keeps
    hitting, so this is the third thing that checks them: it finds every
    template that posts to `generate_document` or links to a print route and
    asserts it is named somewhere here.
    """
    known = set(CONVERGED) | set(MIGRATING) | set(EMBEDDED_CONTROLS)

    prints = set()
    for path in TEMPLATES.rglob('*.html'):
        text = io.open(path, encoding='utf-8').read()
        if ('generate_document' in text or 'print_purchase_order' in text
                or 'print_production_plan' in text):
            prints.add(path.relative_to(TEMPLATES).as_posix())

    # The macro's own definition and the shared history partial are machinery,
    # not screens.
    prints -= {'macros/ui.html', '_generated_documents.html',
               'documents/list.html'}

    unaccounted = sorted(prints - known)
    assert not unaccounted, (
        f'these templates print but are named in none of CONVERGED, '
        f'MIGRATING or EMBEDDED_CONTROLS: {unaccounted}. An unlisted screen '
        f'is one no check in this file applies to.')
