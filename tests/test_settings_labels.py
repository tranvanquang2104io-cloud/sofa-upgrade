"""The settings screens must speak Vietnamese, and every control must be named.

Two defects found by reading the live DOM rather than the templates, both of
which the template lints cannot catch by construction:

1. The workflow screen built its column headers with `{{ t(label) }}` — the key
   is a *variable*, so a scan for `t('...')` literals never sees it, and none
   of the seven values had a Vietnamese entry. The screen was showing "the
   contract has been signed" to a Vietnamese user. The English map is still
   correct where it is used: it composes the block messages. It was simply the
   wrong map to render.

2. Every cell in the rules grid was an unnamed dropdown. In a grid, position is
   the only thing that says what a cell controls, and position is exactly what
   a screen reader does not convey — and what a person loses too when a row
   scrolls under the header.

These assert against the rendered page, because that is where both defects were
visible and where neither was findable from the source alone.
"""
import re


def test_the_workflow_screen_is_in_vietnamese(client, login, seed):
    """No English prerequisite label may reach the page."""
    from app.services.workflow_service import PREREQUISITE_LABELS

    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)
    assert body

    leaked = [label for label in PREREQUISITE_LABELS.values() if label in body]
    assert leaked == [], (
        'these English labels are only meant for the block messages, not for '
        f'the screen: {leaked}')


def test_every_workflow_grid_cell_says_what_it_controls(client, login, seed):
    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)

    cells = re.findall(r'<select[^>]*name="cell_[^"]*"[^>]*>', body)
    assert cells, 'the rules grid did not render'

    unnamed = [cell for cell in cells if 'aria-label=' not in cell]
    assert unnamed == [], (
        'a dropdown in a grid has no meaning without its row and column: '
        f'{len(unnamed)} of {len(cells)} cells are unnamed')


def test_the_steps_are_named_not_only_coded(client, login, seed):
    """`payment.advance` is a key, not a name someone can act on."""
    from app.services.workflow_service import ACTION_LABELS_VI

    login('admin')
    body = client.get('/settings/workflow').get_data(as_text=True)

    missing = [name for name in ACTION_LABELS_VI.values() if name not in body]
    assert missing == [], f'these steps show only their code: {missing}'
