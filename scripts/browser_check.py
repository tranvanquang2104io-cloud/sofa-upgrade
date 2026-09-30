"""Use the product in real Chrome and report what a person would run into.

`walk_screens.py` and `walk_processes.py` speak HTTP. They cannot see what only
exists in the browser, and the 2026-09-30 pass found exactly that kind of defect
while 1,400 tests were green:

* the first quotation line never calculated — 2 × 12.500.000 showed 0 and
  "Không đồng", and "Không đồng" was saved next to 27.000.000;
* the payment form opened with an empty line table, and saving it as it opened
  recorded a 0 đ advance that could then be confirmed;
* a supplier with no tax code pre-filled the invoice's tax code with "None";
* the top bar wrapped every label onto two lines at 1366px, and pushed the page
  sideways at 1024px;
* nineteen English labels on Vietnamese screens, and a wordless Save button.

So this drives Chrome over the DevTools protocol (no Playwright or Selenium on
this machine): it types with real keystrokes, clicks the real buttons, answers
confirm() like a user pressing OK, and after every business step checks both
what the screen says and what the database recorded.

    python scripts/browser_check.py [screens] [english] [journeys]

With no argument it runs all three. It needs the app running against the demo
database (`scripts/seed_demo.py`), and starts a headless Chrome itself unless one
is already listening on SOFA_CHROME_PORT:

    SOFA_APP=http://127.0.0.1:5055 SOFA_DB=path/to/demo.sqlite3 \\
        python scripts/browser_check.py

Screenshots of every screen and every journey step go to SOFA_SHOTS (default: a
temp folder, printed at the end). Exit code is non-zero if anything failed.
"""
import base64
import collections
import itertools
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time

import requests
import websocket

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import walk_screens as W  # noqa: E402  — reuse its id map and route filling

APP = os.environ.get('SOFA_APP', 'http://127.0.0.1:5000')
DB = os.environ.get('SOFA_DB', 'devdata.sqlite3')
W.DB = DB
LOGIN = (os.environ.get('SOFA_USER', 'demo@sofa.test'), os.environ.get('SOFA_PASS', 'demo1234'))
PORT = int(os.environ.get('SOFA_CHROME_PORT', '9333'))
SHOTS = pathlib.Path(os.environ.get('SOFA_SHOTS') or tempfile.mkdtemp(prefix='sofa-browser-'))
CHROME = next((p for p in (
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/usr/bin/google-chrome', '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
) if os.path.exists(p)), 'chrome')

failures = []


def fail(where, what):
    failures.append((where, what))
    print(f'  [FAIL] {where}: {what}')


# ---------------------------------------------------------------- Chrome ---

def ensure_chrome():
    try:
        requests.get(f'http://127.0.0.1:{PORT}/json/version', timeout=1)
        return None
    except requests.RequestException:
        pass
    profile = tempfile.mkdtemp(prefix='sofa-chrome-')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             f'--user-data-dir={profile}', '--no-first-run',
                             '--no-default-browser-check', '--disable-extensions', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(50):
        try:
            requests.get(f'http://127.0.0.1:{PORT}/json/version', timeout=1)
            return proc
        except requests.RequestException:
            time.sleep(0.2)
    raise SystemExit(f'Chrome did not start on port {PORT} ({CHROME})')


class Page:
    """One tab. Collects what the browser reports while you drive it."""

    def __init__(self):
        target = requests.put(f'http://127.0.0.1:{PORT}/json/new?about:blank').json()
        self.target_id = target['id']
        self.ws = websocket.create_connection(target['webSocketDebuggerUrl'],
                                              suppress_origin=True, timeout=60)
        self._ids = itertools.count(1)
        self.events, self.dialogs, self.problems = [], [], []
        for domain in ('Page', 'Runtime', 'Network', 'Log'):
            self.send(f'{domain}.enable')

    def send(self, method, **params):
        msg_id = next(self._ids)
        self.ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == msg_id:
                if 'error' in msg:
                    raise RuntimeError(f'{method}: {msg["error"]}')
                return msg.get('result', {})
            self._event(msg)

    def _event(self, msg):
        method, p = msg.get('method'), msg.get('params', {})
        self.events.append(method)
        if method == 'Page.javascriptDialogOpening':
            # A confirm() blocks the page: answer OK like a user, keep the words.
            self.dialogs.append(p.get('message'))
            self.ws.send(json.dumps({'id': next(self._ids), 'method': 'Page.handleJavaScriptDialog',
                                     'params': {'accept': True}}))
        elif method == 'Runtime.exceptionThrown':
            d = p['exceptionDetails']
            self.problems.append('JS: ' + ((d.get('exception') or {}).get('description') or d.get('text') or '')[:200])
        elif method == 'Runtime.consoleAPICalled' and p.get('type') in ('error', 'assert'):
            self.problems.append('console: ' + ' '.join(str(a.get('value', a.get('description', ''))) for a in p.get('args', []))[:200])
        elif method == 'Network.responseReceived' and p['response'].get('status', 0) >= 400 \
                and not p['response']['url'].endswith('favicon.ico'):
            self.problems.append(f"HTTP {p['response']['status']} {p['response']['url']}")
        elif method == 'Network.loadingFailed' and not p.get('canceled'):
            self.problems.append('network: ' + p.get('errorText', ''))

    def pump(self, seconds):
        end = time.time() + seconds
        self.ws.settimeout(0.1)
        try:
            while time.time() < end:
                try:
                    self._event(json.loads(self.ws.recv()))
                except websocket.WebSocketTimeoutException:
                    pass
        finally:
            self.ws.settimeout(60)

    def wait_load(self, timeout=20):
        end = time.time() + timeout
        while 'Page.loadEventFired' not in self.events:
            if time.time() > end:
                self.problems.append('the page never finished loading (did the browser refuse the form?)')
                return
            self.pump(0.1)

    def viewport(self, width, height=900):
        self.send('Emulation.setDeviceMetricsOverride', width=width, height=height,
                  deviceScaleFactor=1, mobile=width < 500)

    def goto(self, url):
        self.events.clear()
        self.send('Page.navigate', url=url)
        self.wait_load()
        self.pump(0.4)

    def js(self, expression):
        r = self.send('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in r:
            raise RuntimeError((r['exceptionDetails'].get('exception') or {}).get('description'))
        return r['result'].get('value')

    def navigate_by(self, script):
        """Run a click that should load a new page, and wait for it."""
        self.events.clear()
        result = self.js(script)
        self.wait_load()
        self.pump(0.5)
        return result

    def type_text(self, selector, text):
        """Real keystrokes: focus, select what is there, type, Tab away."""
        if not self.js(f'(() => {{ const el = document.querySelector({json.dumps(selector)}); if (!el) return false;'
                       ' el.scrollIntoView({block:"center"}); el.focus(); if (el.select) el.select(); return true; })()'):
            raise RuntimeError(f'no field {selector}')
        self._key('Backspace', 8)
        for ch in text:
            self.send('Input.dispatchKeyEvent', type='keyDown', key=ch, text=ch, unmodifiedText=ch)
            self.send('Input.dispatchKeyEvent', type='keyUp', key=ch)
        self._key('Tab', 9)
        self.pump(0.2)

    def _key(self, key, code):
        for kind in ('keyDown', 'keyUp'):
            self.send('Input.dispatchKeyEvent', type=kind, key=key, code=key, windowsVirtualKeyCode=code)

    def choose(self, selector, index=1):
        return self.js(f'(() => {{ const s = document.querySelector({json.dumps(selector)}); s.value = s.options[{index}].value;'
                       ' s.dispatchEvent(new Event("change", {bubbles: true})); return s.options[s.selectedIndex].text; })()')

    def screenshot(self, path, full=True):
        params = {'format': 'png'}
        if full:
            params.update(captureBeyondViewport=True, clip={
                'x': 0, 'y': 0, 'scale': 1, 'width': self.js('window.innerWidth'),
                'height': self.js('Math.min(document.documentElement.scrollHeight, 6000)')})
        path.write_bytes(base64.b64decode(self.send('Page.captureScreenshot', **params)['data']))

    def close(self):
        requests.get(f'http://127.0.0.1:{PORT}/json/close/{self.target_id}')
        self.ws.close()


def login(page):
    page.goto(f'{APP}/auth/login')
    page.js(f'document.querySelector("input[name=email]").value = {json.dumps(LOGIN[0])};'
            f'document.querySelector("input[name=password]").value = {json.dumps(LOGIN[1])};')
    page.navigate_by('document.querySelector("form button[type=submit]").click()')
    if '/auth/login' in page.js('location.pathname'):
        raise SystemExit(f'could not log in as {LOGIN[0]} — is the demo company seeded?')


def screens():
    """(name, path) for every dashboard GET screen, with demo ids filled in."""
    from app import create_app
    import logging
    logging.disable(logging.CRITICAL)
    rules = create_app('testing').url_map.iter_rules()
    ids = W.sample_ids()
    out = []
    for rule in sorted(rules, key=lambda r: r.rule):
        if ('GET' not in rule.methods or not rule.endpoint.startswith('dashboard.')
                or any(b in rule.rule for b in W.BINARY) or '/api/' in rule.rule
                or rule.endpoint in ('dashboard.set_language', 'dashboard.serve_item_image')):
            continue
        path = W.fill(rule.rule, ids)
        if path:
            out.append((rule.endpoint.split('.', 1)[1], path))
    return out


def db(sql, *args):
    con = W.connect(DB)
    try:
        return con.execute(sql, args).fetchone()
    finally:
        con.close()


# ------------------------------------------------------------ 1. screens ---

INSPECT = r'''(() => {
  const vw = window.innerWidth, vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length), out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push('the page scrolls sideways');
  const text = document.body.innerText;
  for (const pat of [/\{\{|\}\}|\{%/, /(^|[\s>:(])None([\s<).,]|$)/, /\bundefined\b/, /\bNaN\b/, /\[object Object\]/, /Traceback/]) {
    const m = text.match(pat); if (m) out.push('shows "' + text.slice(Math.max(0, m.index - 25), m.index + 25).replace(/\s+/g, ' ') + '"'); }
  for (const f of document.querySelectorAll('input:not([type=hidden]), textarea'))
    if (vis(f) && /^(None|undefined|NaN)$/.test(f.value)) out.push('field ' + (f.name || f.id) + ' is pre-filled with "' + f.value + '"');
  for (const i of document.images) if (vis(i) && i.getAttribute('src') && i.complete && !i.naturalWidth) out.push('broken image ' + i.src);
  for (const b of document.querySelectorAll('button, a.btn')) if (vis(b) && !b.innerText.trim() && !b.getAttribute('aria-label') && !b.getAttribute('title'))
    out.push('a button with no words: ' + b.outerHTML.slice(0, 90));
  const nav = document.querySelector('nav.navbar');
  if (nav && vw >= 1200 && nav.getBoundingClientRect().height > 70) out.push('the top bar wraps onto a second line (' + Math.round(nav.getBoundingClientRect().height) + 'px)');
  return {findings: out, modals: [...new Set([...document.querySelectorAll('[data-bs-toggle=modal]')].filter(vis).map(b => b.getAttribute('data-bs-target')))].filter(Boolean)};
})()'''

OPEN_MODAL = r'''(async target => {
  const t = [...document.querySelectorAll('[data-bs-toggle=modal]')].find(b => b.getAttribute('data-bs-target') === target && (b.offsetWidth || b.offsetHeight));
  t.click(); await new Promise(r => setTimeout(r, 450));
  const m = document.querySelector(target), shown = !!(m && m.classList.contains('show'));
  const r = m && m.querySelector('.modal-dialog') && m.querySelector('.modal-dialog').getBoundingClientRect();
  if (m && window.bootstrap) { bootstrap.Modal.getOrCreateInstance(m).hide(); await new Promise(r => setTimeout(r, 350)); }
  return !shown ? 'did not open' : (r && (r.right > innerWidth + 1 || r.left < -1)) ? 'opens off-screen' : '';
})'''


def check_screens(page):
    print('== screens: every screen at 1366px and 390px, and every dialog on it')
    count = 0
    for width in (1366, 390):
        page.viewport(width)
        for name, path in screens():
            page.problems.clear()
            page.goto(APP + path)
            info = page.js(INSPECT)
            for target in info['modals']:
                verdict = page.js(OPEN_MODAL + f'({json.dumps(target)})')
                if verdict:
                    info['findings'].append(f'dialog {target} {verdict}')
            if width == 1366:
                page.screenshot(SHOTS / f'screen-{name}.png')
            for finding in info['findings'] + sorted(set(page.problems)):
                fail(f'[{width}] {name}', finding)
            count += 1
    print(f'   {count} screen renders checked')


def check_home_cards(page):
    """Every home card must open exactly the rows it counted."""
    print('== home: each work-queue card against the list it opens')
    page.viewport(1366)
    page.goto(APP + '/')
    cards = page.js("""[...document.querySelectorAll('[data-testid^=queue-]')].map(a => ({
        key: a.dataset.testid.slice(6), count: +a.querySelector('.sf-queue__count').innerText,
        href: a.getAttribute('href')}))""")
    checked = 0
    for card in cards:
        if not card['count'] or 'queue=' not in card['href']:
            continue
        page.goto(APP + card['href'])
        shown = page.js("(() => { const b = document.querySelector('[data-testid=queue-banner]');"
                        " const m = b && b.innerText.match(/— (\\d+)/); return m ? +m[1] : null; })()")
        if shown != card['count']:
            fail(f'home card {card["key"]}', f'says {card["count"]}, its list shows {shown}')
        checked += 1
    print(f'   {checked} cards opened, {len(cards)} on the page')


# ------------------------------------------------------------ 2. english ---

ENGLISH = r'''(() => {
  const EN = /\b(the|to|of|and|for|with|your|this|Click|Add|Load|Amount|Payment|Summary|Reference|Information|Items?|Goods|Total|Value|Select|Edit|Approve|Remove|Delete|View|Save|Cancel|Close|Create|Search|Status|Date|Name|Number|Upload|Download|Print|Details?|Notes?|Order|Customer|Contract|Quotation|Handover|Supplier|Material|Price|Quantity|Unit|Method|Account|Bank|Type|Required|Enter|Choose|Record|Report|Rep|Validity|Start|Sign|No|e\.g\.|E\.g\.)\b/;
  const VI = /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;
  const OK = /^(SofaFlow|EN|VI|VAT|PDF|DOCX|OK|Switch to English|[A-Z0-9_\-\/.: ]+)$/;
  const vis = el => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length), out = new Set();
  const see = (s, where) => { s = (s || '').replace(/\s+/g, ' ').trim(); if (s.length > 2 && !VI.test(s) && !OK.test(s) && EN.test(s)) out.add(where + ' "' + s.slice(0, 80) + '"'); };
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode());) { const el = n.parentElement; if (el && !['SCRIPT', 'STYLE'].includes(el.tagName) && vis(el)) see(n.textContent, 'text'); }
  document.querySelectorAll('[placeholder]').forEach(e => vis(e) && see(e.placeholder, 'placeholder'));
  document.querySelectorAll('[title]').forEach(e => vis(e) && see(e.title, 'tooltip'));
  document.querySelectorAll('select option').forEach(o => see(o.textContent, 'option'));
  return [...out];
})()'''


def check_english(page):
    print('== english: every screen in Vietnamese — English a Vietnamese user still reads')
    page.viewport(1366)
    page.goto(APP + '/set-language/vi')
    seen = collections.defaultdict(list)
    for name, path in screens():
        page.goto(APP + path)
        for s in page.js(ENGLISH):
            seen[s].append(name)
    for s, names in sorted(seen.items()):
        fail(names[0] + (f' (+{len(names) - 1} more)' if len(names) > 1 else ''), 'English on a Vietnamese screen: ' + s)
    print(f'   {len(seen)} distinct English strings')


# ----------------------------------------------------------- 3. journeys ---

def step(page, journey, name, ok, detail=''):
    page.screenshot(SHOTS / f'{journey}-{len([f for f in os.listdir(SHOTS) if f.startswith(journey)]) + 1:02d}.png')
    problems = sorted(set(page.problems))
    page.problems.clear()
    if ok and not problems:
        print(f'  [PASS] {name}  {detail}')
    else:
        fail(f'{journey}: {name}', f'{detail} {problems if problems else ""}')
    return ok and not problems


def click_link(page, href_part):
    # Built outside the f-string: Python 3.11 (the production image) rejects a
    # backslash inside an f-string expression.
    selector = f'main a[href*="{href_part}"], #main-content a[href*="{href_part}"]'
    page.navigate_by(f'document.querySelector({json.dumps(selector)}).click()')


def press(page, text):
    """Click the visible submit button labelled `text`."""
    page.navigate_by(f'''[...document.querySelectorAll('button[type=submit], button:not([type])')]
        .find(b => b.offsetParent && b.innerText.includes({json.dumps(text)})).click()''')


def press_form(page, action_part):
    """Press the button of the form posting to `action_part` (opening its dialog if it lives in one)."""
    page.events.clear()
    page.js(f'''(async () => {{
        const f = [...document.querySelectorAll('form')].find(f => (f.getAttribute('action') || '').includes({json.dumps(action_part)}));
        const modal = f.closest('.modal');
        if (modal && !modal.classList.contains('show')) {{
            document.querySelector('[data-bs-target="#' + modal.id + '"]').click(); await new Promise(r => setTimeout(r, 500)); }}
        [...f.querySelectorAll('button')].find(b => b.type === 'submit').click(); }})()''')
    page.wait_load()
    page.pump(0.5)


def flash(page):
    return page.js("[...document.querySelectorAll('.alert')].filter(a => a.offsetParent).map(a => a.innerText.trim()).join(' | ')")[:70]


def journey_sales(page):
    print('== journey: a sale, from new order to closed — as staff do it')
    page.viewport(1366)
    page.goto(APP + '/orders')
    click_link(page, '/orders/create')
    page.choose('select[name=customer_id]')
    page.type_text('input[name=title]', 'Bọc lại sofa góc L — kiểm tra trình duyệt')
    press(page, 'Tạo Đơn Hàng')
    m = re.search(r'/orders/([0-9a-f-]{36})', page.js('location.pathname'))
    if not step(page, 'sales', 'tạo đơn hàng', m, flash(page)):
        return
    order = m.group(1)

    click_link(page, f'/quotations/{order}/create')
    page.type_text('input[name="item_name[]"]', 'Đóng mới ghế sofa góc L, vải nhung')
    page.type_text('input[name="item_quantity[]"]', '2')
    page.type_text('input[name="item_price[]"]', '12500000')
    shown = page.js("({total: document.getElementById('total_amount_display').value, words: document.getElementById('amount_in_words').value})")
    press(page, 'Tạo Báo Giá')
    q = db('select total_amount, amount_in_words from quotations where order_id=?', order)
    step(page, 'sales', 'báo giá tính ngay khi gõ, và lưu đúng',
         shown == {'total': '27.000.000', 'words': 'Hai mươi bảy triệu đồng'} and q == (27000000, 'Hai mươi bảy triệu đồng'),
         f'màn hình {shown} · lưu {q}')

    page.goto(f'{APP}/orders/{order}')
    press_form(page, '/approve')
    step(page, 'sales', 'duyệt báo giá', db('select is_approved from quotations where order_id=?', order) == (1,), str(page.dialogs[-1:]))

    page.goto(f'{APP}/orders/{order}')
    click_link(page, f'/contracts/{order}/create')
    page.pump(0.6)
    press(page, 'Tạo Hợp Đồng')
    step(page, 'sales', 'hợp đồng lấy từ báo giá', db('select contract_value from contracts where order_id=?', order) == (27000000,), flash(page))

    page.goto(f'{APP}/orders/{order}')
    press_form(page, '/sign')
    step(page, 'sales', 'ký hợp đồng', db('select is_signed from contracts where order_id=?', order) == (1,), str(page.dialogs[-1:]))

    page.goto(f'{APP}/orders/{order}')
    click_link(page, f'/payment/{order}/create')
    page.pump(1.0)
    press(page, 'Tạo Biên Bản')
    adv = db("select advance_amount, amount_in_words from payment_reports where order_id=? and payment_type='advance'", order)
    step(page, 'sales', 'phiếu tạm ứng mở ra đã có số tiền (30%)', adv == (8100000, 'Tám triệu một trăm nghìn đồng'), f'lưu {adv}')

    page.goto(f'{APP}/orders/{order}')
    press_form(page, '/confirm')
    step(page, 'sales', 'xác nhận đã thu tạm ứng', db('select advance_paid from lifecycle_statuses where order_id=?', order) == (1,), flash(page))

    page.goto(f'{APP}/orders/{order}')
    click_link(page, f'/handover/{order}/create')
    page.type_text('input[name=company_representative]', 'Trần Văn Quang')
    page.type_text('input[name=customer_representative]', 'Nguyễn Thị Lan')
    page.type_text('textarea[name=product_condition]', 'Hàng đúng mẫu, khách đã kiểm và nhận.')
    press(page, 'Tạo Biên Bản')
    page.goto(f'{APP}/orders/{order}')
    press_form(page, '/handover/')
    step(page, 'sales', 'lập và xác nhận bàn giao', db('select is_confirmed from handover_records where order_id=?', order) == (1,), str(page.dialogs[-1:]))

    page.goto(f'{APP}/orders/{order}')
    click_link(page, f'/payment/{order}/create?type=final')
    page.pump(1.0)
    press(page, 'Tạo Biên Bản')
    page.goto(f'{APP}/orders/{order}')
    press_form(page, '/confirm')
    life = db('select fully_paid, completed from lifecycle_statuses where order_id=?', order)
    step(page, 'sales', 'thu nốt và đóng đơn', life == (1, 1), f'lifecycle {life}')


def journey_purchase(page):
    print('== journey: buying material, from requisition to paying the supplier')
    page.viewport(1366)
    page.goto(APP + '/requisitions')
    click_link(page, '/requisitions/create')
    page.type_text('input[name=title]', 'Mua vật tư cho đơn sofa góc L')
    page.choose('select[name=store_id]')
    page.choose('select[name="line_material_id[]"]')
    page.type_text('input[name="line_quantity[]"]', '20')
    press(page, 'Lưu')
    m = re.search(r'/requisitions/([0-9a-f-]{36})', page.js('location.pathname'))
    if not step(page, 'purchase', 'lập đề nghị mua', m, flash(page)):
        return
    pr = m.group(1)
    press_form(page, '/status/submit')
    press_form(page, '/status/approve')
    press_form(page, '/convert')
    m = re.search(r'/purchase-orders/([0-9a-f-]{36})', page.js('location.pathname'))
    if not step(page, 'purchase', 'gửi duyệt → duyệt → tạo đơn mua',
                m and db('select status from purchase_requisitions where id=?', pr) == ('converted',), flash(page)):
        return
    po = m.group(1)

    press_form(page, '/status/submit')
    step(page, 'purchase', 'gửi nhà cung cấp', db('select status from purchase_orders where id=?', po) == ('ordered',), str(page.dialogs[-1:]))

    material = db('select material_id from purchase_order_lines where po_id=?', po)[0]
    before = db('select coalesce(sum(current_quantity), 0) from material_stock where material_id=?', material)[0]
    starts_empty = page.js("document.querySelector('form[action*=receive] input[type=number]').value") == ''
    page.type_text('form[action*=receive] input[type=number]', '20')
    press_form(page, '/receive')
    after = db('select coalesce(sum(current_quantity), 0) from material_stock where material_id=?', material)[0]
    step(page, 'purchase', 'nhận hàng làm tồn kho tăng đúng 20', starts_empty and after - before == 20,
         f'ô số lượng để trống lúc mở={starts_empty} · tồn {before} → {after}')

    page.goto(f'{APP}/purchase-orders/{po}')
    click_link(page, f'/purchase-orders/{po}/invoice')
    tax_code = page.js("(document.querySelector('[name=seller_tax_code]') || {}).value")
    # A fresh number each run: the app rightly refuses a supplier invoice number twice.
    page.type_text('input[name=invoice_number]', time.strftime('%H%M%S'))
    page.js("document.querySelector('input[name=invoice_date]').value = new Date().toISOString().slice(0, 10)")
    press(page, 'Ghi nhận hóa đơn')
    inv = db('select id from supplier_invoices where po_id=?', po)
    step(page, 'purchase', 'ghi nhận hóa đơn NCC', inv and tax_code != 'None', f'mã số thuế điền sẵn {tax_code!r}')
    if not inv:
        return
    press_form(page, '/confirm')
    suggested = page.js("({number: document.querySelector('[name=payment_number]').value, date: document.querySelector('[name=payment_date]').value})")
    press_form(page, '/pay')
    # Paid-ness is not a status: it is the confirmed payments allocated to the invoice.
    paid = db('select coalesce(sum(a.allocated_amount), 0), i.total_amount from supplier_invoices i '
              'left join supplier_payment_allocations a on a.invoice_id = i.id where i.id=? '
              'group by i.total_amount', inv[0])
    step(page, 'purchase', 'xác nhận hóa đơn và trả tiền NCC', paid[0] == paid[1] and all(suggested.values()),
         f'phiếu chi gợi ý {suggested} · đã trả {paid[0]} / {paid[1]}')


def main():
    wanted = set(sys.argv[1:]) or {'screens', 'english', 'journeys'}
    chrome = ensure_chrome()
    page = Page()
    try:
        page.viewport(1366)
        login(page)
        if 'screens' in wanted:
            check_screens(page)
            check_home_cards(page)
        if 'english' in wanted:
            check_english(page)
        if 'journeys' in wanted:
            journey_sales(page)
            journey_purchase(page)
    finally:
        page.close()
        if chrome:
            chrome.terminate()
    print(f'\nscreenshots: {SHOTS}')
    print(f'{len(failures)} finding(s)' if failures else 'nothing found')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
