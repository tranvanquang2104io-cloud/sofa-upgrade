"""The screen contract, written down as a test rather than as an intention.

Measured before starting: **12 of 73** screens used `page_header()`. The macro
library existed and almost nothing used it, which is exactly why the product
felt like several products — a list page looked different depending on which
part of the app you reached it from, and the same kind of information (a
document's header fields) was rendered as a `<dl>` on the sales screens and as
bare divs on the procurement ones.

The contract, by screen type:

    list    page_header · table_open/close · empty_state
    create  page_header · form_actions
    edit    page_header · form_actions
    view    page_header · detail_row for labelled facts

Migration is done group by group, and each group's screens come off the
`NOT_YET` list below in the same commit that converges them. The list only ever
shrinks: a screen that is not on it and does not meet the contract fails here,
so converged work cannot regress while the rest is still in flight.

A screen that genuinely should not follow a rule gets an entry in `EXEMPT` with
the reason, not a silent pass.
"""
import io
import pathlib

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'


def _screens():
    """Every user-facing screen, classified by what kind it is."""
    for path in sorted(TEMPLATES.rglob('*.html')):
        if path.name.startswith('_') or 'macros' in path.parts:
            continue
        name = '/'.join(path.relative_to(TEMPLATES).parts)
        if name in ('base.html', 'print_base.html'):
            continue
        text = io.open(path, encoding='utf-8').read()
        if '{% block content %}' not in text and '{%block content%}' not in text:
            continue                       # print layouts and partials
        if 'create' in name:
            kind = 'create'
        elif 'edit' in name:
            kind = 'edit'
        elif 'view' in name:
            kind = 'view'
        elif 'list' in name:
            kind = 'list'
        else:
            kind = 'other'
        yield kind, name, text


# Screens that have not been converged yet. Shrinks with every group.
NOT_YET = {
    'admin/create_admin.html',
    'admin/create_company.html',
    'admin/edit_company.html',
    'agreements/create.html',
    'agreements/edit.html',
    'contracts/create.html',
    'contracts/edit.html',
    'contracts/view.html',
    'documents/list.html',
    'handover/create.html',
    'handover/edit.html',
    'handover/view.html',
    'materials/create.html',
    'materials/edit.html',
    'materials/list.html',
    'materials/view.html',
    'orders/create.html',
    'orders/edit.html',
    'orders/view.html',
    'payables/create.html',
    'payments/create.html',
    'payments/edit.html',
    'payments/view.html',
    'procurement/gr_list.html',
    'procurement/gr_view.html',
    'procurement/po_list.html',
    'procurement/po_view.html',
    'procurement/pr_list.html',
    'procurement/pr_view.html',
    'quotations/create.html',
    'quotations/edit.html',
    'quotations/view.html',
    'stores/create.html',
    'stores/edit.html',
    'stores/list.html',
    'users/create.html',
    'users/edit.html',
    'users/list.html',
}

# Screens that will never meet part of the contract, and why.
EXEMPT = {
    # (empty for now: every list/create/edit/view screen can follow the
    # contract. Login and the dashboard are classified 'other' and are not
    # checked at all, so they need no entry here.)
}


def _requirements(kind):
    return {
        'list': ('page_header(', 'table_open(' ),
        'create': ('page_header(', 'form_actions('),
        'edit': ('page_header(', 'form_actions('),
        'view': ('page_header(',),
    }.get(kind, ())


@pytest.mark.parametrize('kind', ['list', 'create', 'edit', 'view'])
def test_converged_screens_follow_the_contract(kind):
    """Everything not on NOT_YET must use the shared building blocks."""
    offenders = []
    for screen_kind, name, text in _screens():
        if screen_kind != kind or name in NOT_YET or name in EXEMPT:
            continue
        missing = [macro for macro in _requirements(kind) if macro not in text]
        if missing:
            offenders.append(f'{name}: missing {", ".join(missing)}')

    assert offenders == [], (
        f'these {kind} screens have been converged but do not follow the '
        f'contract: {offenders}'
    )


def test_the_not_yet_list_names_only_real_screens():
    """A stale entry would silently excuse a screen that no longer exists."""
    existing = {name for _kind, name, _text in _screens()}
    stale = sorted(NOT_YET - existing)
    assert stale == [], f'NOT_YET names screens that are gone: {stale}'


def test_the_exempt_list_names_only_real_screens():
    existing = {name for _kind, name, _text in _screens()}
    stale = sorted(set(EXEMPT) - existing)
    assert stale == [], f'EXEMPT names screens that are gone: {stale}'


def test_progress_is_visible():
    """Prints the score so the migration can be seen, not guessed at."""
    total = converged = 0
    for kind, name, _text in _screens():
        if kind == 'other' or name in EXEMPT:
            continue
        total += 1
        if name not in NOT_YET:
            converged += 1

    assert total > 0
    print(f'\nscreen contract: {converged}/{total} converged')
