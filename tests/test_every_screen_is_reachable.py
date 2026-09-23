"""A screen a user cannot navigate to does not exist, however well it works.

Reported by the owner as "Hóa đơn thì lại không được tạo". The form for
recording a supplier's hóa đơn GTGT works perfectly — it just had no way in.
The supplier-invoice list even says *"Record one from a purchase order"*, and
the purchase-order screen offered Edit, Print and Nhận hàng, and no invoice
button. The only reference to that route anywhere was the form's own `action`,
posting back to itself.

That self-reference is why a plain "is this endpoint referenced?" scan reports
it as fine. The question that matters is whether a user can GET there from
somewhere they already are — so the template that renders a screen does not
count as a link to it.

Same shape as the production plan telling people to press a button that is not
on the screen: the product describes a route through itself that it does not
actually provide.
"""
import io
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
ROUTES = ROOT / 'app' / 'routes' / 'dashboard_routes.py'

# Endpoints reached by JavaScript rather than by a link, with why.
EXEMPT = {
    'get_contract_api': 'JSON read, fetched by the contract picker',
    'get_quotation_detail': 'JSON read, fetched by the quotation picker',
    'check_code': 'JSON read, fetched by the create forms',
    'get_next_code': 'JSON read, fetched by the create forms',
    'serve_item_image': 'an <img> src, not a page',
    'set_language': 'the language switch in the navbar posts to it',
    'index': 'the landing page after login',
}


def _templates_each_view_renders():
    """view function -> the templates it renders, so self-links can be ignored."""
    source = io.open(ROUTES, encoding='utf-8').read()
    owns = {}
    for match in re.finditer(r'^def ([a-z_0-9]+)\(', source, re.M):
        name = match.group(1)
        body = source[match.end():match.end() + 8000]
        following = re.search(r'^def [a-z_0-9]+\(', body, re.M)
        if following:
            body = body[:following.start()]
        owns[name] = set(re.findall(r"render_template\(\s*'([^']+)'", body))
    return owns


def _references():
    """endpoint -> the templates that name it in a url_for."""
    found = {}
    for path in TEMPLATES.rglob('*.html'):
        relative = '/'.join(path.relative_to(TEMPLATES).parts)
        text = io.open(path, encoding='utf-8').read()
        for endpoint in re.findall(
                r"""url_for\(\s*['"]dashboard\.([A-Za-z0-9_]+)['"]""", text):
            found.setdefault(endpoint, set()).add(relative)
    return found


def test_every_screen_can_be_reached_from_another_screen(app):
    owns = _templates_each_view_renders()
    references = _references()

    unreachable = []
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('dashboard.'):
            continue
        if 'GET' not in rule.methods:
            continue
        name = rule.endpoint.split('.', 1)[1]
        if name in EXEMPT:
            continue
        # A template linking to the screen it IS does not get a user there.
        elsewhere = references.get(name, set()) - owns.get(name, set())
        if not elsewhere:
            unreachable.append(f'{name}  {rule}')

    assert unreachable == [], (
        'no screen links to these, so the only way in is to type the URL: '
        f'{sorted(unreachable)}')
