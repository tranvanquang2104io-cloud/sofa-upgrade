"""Open every screen and check every action has a way to be invoked.

Two questions the layout audit cannot answer, asked of the whole product rather
than of the screens somebody thought to look at:

1. **Does every screen open?** Every GET route is fetched with real demo data,
   with ids filled in from the database. A 500 is a defect; so is a redirect
   away from a screen that should have rendered.

2. **Can every action be reached?** Every POST route is matched against the
   forms in the templates. A POST route no form points at is either dead code
   or a missing button — the shape of the bug where the production plan told
   the user to press "Từ chối (làm lại)" and no such control existed.

Run with the app up:
    python scripts/walk_screens.py
"""
import io
import os
import pathlib
import re
import sqlite3
import sys
import urllib.parse

import requests

import os; APP = os.environ.get('SOFA_APP','http://127.0.0.1:5000')
LOGIN = ('demo@sofa.test', 'demo1234')
DB = os.environ.get('SOFA_DB','devdata.sqlite3')
TEMPLATES = pathlib.Path('app/templates')

# Routes that are not screens: downloads, images and the logout that would end
# the session we are walking with.
SKIP = {'/auth/logout', '/logout'}
BINARY = ('/download', '/uploads/', '/print')


def login():
    session = requests.Session()
    page = session.get(f'{APP}/auth/login').text
    token = re.search(r'name="csrf_token" value="([^"]+)"', page)
    session.post(f'{APP}/auth/login',
                 data={'email': LOGIN[0], 'password': LOGIN[1],
                       'csrf_token': token.group(1) if token else ''})
    return session


def sample_ids():
    """One real id per entity, from the demo company."""
    con = sqlite3.connect(DB)
    company = list(con.execute(
        "select id from companies where company_code='SOFADEMO'"))[0][0]

    def one(sql, *params):
        rows = list(con.execute(sql, params or (company,)))
        return rows[0][0] if rows else None

    ids = {
        'order_id': one('select id from orders where company_id=?'),
        'customer_id': one('select id from customers where store_id in '
                           '(select id from stores where company_id=?)'),
        'material_id': one('select id from materials where company_id=?'),
        'po_id': one('select id from purchase_orders where company_id=?'),
        'pr_id': one('select id from purchase_requisitions where company_id=?'),
        'gr_id': one('select id from goods_receipts where company_id=?'),
        'agreement_id': one('select id from master_agreements where company_id=?'),
        'invoice_id': one('select id from supplier_invoices where company_id=?'),
        'store_id': one('select id from stores where company_id=?'),
        'user_id': one('select id from users where company_id=?'),
        'plan_id': one('select id from production_plans where company_id=?'),
        'template_id': one('select id from document_templates where company_id=?'),
        'document_id': one('select id from documents where company_id=?'),
        # Added 2026-Q4: these tables did not exist when this map was written,
        # so their screens reported "no demo data" and were silently skipped —
        # a walker that cannot reach a screen says nothing about it, which is
        # the same blind spot this script exists to remove.
        'warehouse_id': one('select id from warehouses where company_id=?'),
        'request_id': one('select id from approval_requests where company_id=?'),
        'transfer_id': one('select id from stock_transfers where company_id=?'),
        'payment_id': one('select id from payment_reports where company_id=?'),
        'quotation_id': one('select id from quotations where company_id=?'),
        'contract_id': one('select id from contracts where company_id=?'),
    }
    for key, sql in [
        ('quotation_id', 'select q.id from quotations q join orders o on '
                         'o.id=q.order_id where o.company_id=?'),
        ('contract_id', 'select c.id from contracts c join orders o on '
                        'o.id=c.order_id where o.company_id=?'),
        ('handover_id', 'select h.id from handover_records h join orders o on '
                        'o.id=h.order_id where o.company_id=?'),
        ('payment_id', 'select p.id from payment_reports p join orders o on '
                       'o.id=p.order_id where o.company_id=?'),
    ]:
        ids[key] = one(sql)
    ids['doc_type'] = 'quotation'
    ids['entity'] = 'customer'
    ids['lang'] = 'vi'
    ids['action'] = 'approve'
    ids['filename'] = 'none.png'
    ids['line_id'] = one('select l.id from production_material_lines l '
                         'join production_plans p on p.id=l.plan_id '
                         'where p.company_id=?')
    ids['item_id'] = one('select i.id from production_plan_items i '
                         'join production_plans p on p.id=i.plan_id '
                         'where p.company_id=?')
    ids['ref_id'] = ids['quotation_id']
    con.close()
    return ids


def fill(rule, ids):
    """Substitute real ids into a Flask rule, or return None if we have none."""
    path = rule
    for name in re.findall(r'<(?:[^:<>]+:)?([^<>]+)>', rule):
        value = ids.get(name)
        if value is None:
            return None
        path = re.sub(r'<(?:[^:<>]+:)?%s>' % re.escape(name),
                      urllib.parse.quote(str(value)), path)
    return path


def post_targets_in_templates():
    """Every endpoint a template's form, fetch or JS actually points at.

    Three shapes, because the first version of this only knew the first and
    reported two false orphans: `url_for('...')`, `url_for("...")` — a fetch in
    a script block uses double quotes so the surrounding JS string can use
    single ones — and a path assembled by hand in JS, as the delete-document
    dialog does.
    """
    targets = set()
    literal_paths = []
    for path in TEMPLATES.rglob('*.html'):
        text = io.open(path, encoding='utf-8').read()
        targets.update(re.findall(
            r"""url_for\(\s*['"](dashboard\.[A-Za-z0-9_]+)['"]""", text))
        literal_paths.extend(re.findall(r"""['"](/[a-z0-9\-/]+/?)['"]""", text))
    for path in pathlib.Path('app/static').rglob('*.js'):
        text = io.open(path, encoding='utf-8').read()
        literal_paths.extend(re.findall(r"""['"](/[a-z0-9\-/]+/?)['"]""", text))
    return targets, set(literal_paths)


def main():
    os.chdir(pathlib.Path(__file__).resolve().parents[1])
    sys.path.insert(0, '.')
    os.environ.setdefault('DATABASE_URL', 'sqlite:///' + os.path.abspath(DB))
    import logging
    logging.disable(logging.CRITICAL)
    from app import create_app

    app = create_app('testing')
    ids = sample_ids()
    session = login()

    screens, actions = [], []
    for rule in app.url_map.iter_rules():
        if not rule.endpoint.startswith('dashboard.'):
            continue
        if 'GET' in rule.methods:
            screens.append((rule.endpoint, str(rule)))
        elif 'POST' in rule.methods:
            actions.append((rule.endpoint, str(rule)))

    print('=== screens ===')
    broken, skipped = [], []
    for endpoint, rule in sorted(screens, key=lambda r: r[1]):
        path = fill(rule, ids)
        if path is None:
            skipped.append(f'{rule}  (no demo data for its id)')
            continue
        if path in SKIP or any(b in path for b in BINARY):
            continue
        response = session.get(APP + path, allow_redirects=False)
        code = response.status_code
        if code == 200:
            continue
        broken.append(f'{code}  {path}  [{endpoint}]')

    for line in broken:
        print(' ', line)
    print(f'-- {len(screens) - len(broken) - len(skipped)} opened, '
          f'{len(broken)} did not, {len(skipped)} had no demo data')
    for line in skipped:
        print('   skipped:', line)

    print()
    print('=== actions with no control anywhere ===')
    reachable, literals = post_targets_in_templates()

    def unreachable(endpoint, rule):
        if endpoint in reachable:
            return False
        # A path built in JS: compare the fixed prefix before the first <id>.
        prefix = rule.split('<')[0].rstrip('/')
        return not any(l.rstrip('/').startswith(prefix) for l in literals
                       if prefix)

    orphans = [f'{endpoint}  {rule}' for endpoint, rule in sorted(actions)
               if unreachable(endpoint, rule)]
    for line in orphans:
        print(' ', line)
    print(f'-- {len(actions) - len(orphans)} of {len(actions)} POST actions '
          f'are reachable from a screen')


if __name__ == '__main__':
    main()
