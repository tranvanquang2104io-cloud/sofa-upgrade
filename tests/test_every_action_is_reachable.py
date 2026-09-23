"""Every action must have a control, and no action may bypass its own gate.

Two failures share one shape, and a walk of all 71 routes found both:

* **A screen tells the user to press a button that does not exist.** The
  production plan's lock message named "Từ chối (làm lại)", which is on no
  screen and is not a legal move from production.
* **An action exists that no screen offers.** `create_pos_from_suggestions`
  created purchase orders straight from the suggestion list — with no
  requisition and no approval. The supported path refuses exactly that:
  "Chỉ tạo PO từ PR đã được duyệt." So the route was a door in the wall with
  no handle on the inside, open to anyone holding the `purchasing` permission
  who knew the URL.

An action with no control is either dead code or a missing button, and both
are worth knowing about. It may only stay by being named here with a reason.
"""
import io
import pathlib
import re

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'
STATIC = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'static'

# Actions with no control on any screen, each with why that is correct.
EXEMPT = {
    # Nothing yet. An entry here must say why the action exists at all.
}


def _referenced_endpoints():
    """Endpoints named by a url_for anywhere in the templates.

    Both quote styles: a fetch inside a script block uses double quotes so the
    JS string around it can use single ones. The first version of this scan
    knew only single quotes and reported two actions as orphans that were
    wired up perfectly well.
    """
    found = set()
    for path in TEMPLATES.rglob('*.html'):
        text = io.open(path, encoding='utf-8').read()
        found.update(re.findall(
            r"""url_for\(\s*['"](dashboard\.[A-Za-z0-9_]+)['"]""", text))
    return found


def _literal_paths():
    """URLs assembled by hand in JS, as the delete-document dialog does."""
    found = set()
    for folder, pattern in ((TEMPLATES, '*.html'), (STATIC, '*.js')):
        for path in folder.rglob(pattern):
            text = io.open(path, encoding='utf-8').read()
            found.update(re.findall(r"""['"](/[a-z0-9\-/]+/?)['"]""", text))
    return found


def test_every_post_action_can_be_reached_from_a_screen(app):
    referenced = _referenced_endpoints()
    literals = _literal_paths()

    orphans = []
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('dashboard.'):
            continue
        if 'POST' not in rule.methods or 'GET' in rule.methods:
            continue
        name = rule.endpoint.split('.', 1)[1]
        if name in EXEMPT or rule.endpoint in referenced:
            continue
        prefix = str(rule).split('<')[0].rstrip('/')
        if prefix and any(p.rstrip('/').startswith(prefix) for p in literals):
            continue
        orphans.append(f'{rule.endpoint}  {rule}')

    assert orphans == [], (
        'these actions have no control on any screen — each is either dead '
        f'code or a missing button: {sorted(orphans)}')
