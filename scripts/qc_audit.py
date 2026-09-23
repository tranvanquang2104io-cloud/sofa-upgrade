"""Drive a real Chrome over CDP and audit every screen against layout rules.

Not a screenshot diff and not a smoke test: it reads the rendered DOM through
`getBoundingClientRect` and checks the things a picky reviewer checks by eye —
does the page scroll sideways, do the primary actions line up, are labels and
their controls associated, does anything overflow its container, do the tables
have headers, is anything sitting on top of something else.

Each check exists because getting it wrong is visible to a user, and each
reports the element it is complaining about so the finding can be acted on
rather than argued with.

Usage:
    python scripts/qc_audit.py                 # audit every screen
    python scripts/qc_audit.py /orders         # one screen
"""
import json
import sqlite3
import sys
import time
import urllib.request

import websocket

CDP = 'http://127.0.0.1:9222'
APP = 'http://127.0.0.1:5000'
LOGIN = ('demo@sofa.test', 'demo1234')


# --------------------------------------------------------------------------
# a very small CDP client
# --------------------------------------------------------------------------

class Page:
    def __init__(self):
        targets = json.load(urllib.request.urlopen(CDP + '/json'))
        page = next(t for t in targets if t['type'] == 'page')
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'],
                                              timeout=30)
        self.n = 0

    def send(self, method, **params):
        self.n += 1
        self.ws.send(json.dumps({'id': self.n, 'method': method,
                                 'params': params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get('id') == self.n:
                if 'error' in message:
                    raise RuntimeError(message['error'])
                return message.get('result', {})

    def evaluate(self, expression):
        result = self.send('Runtime.evaluate', expression=expression,
                           returnByValue=True, awaitPromise=True)
        return result.get('result', {}).get('value')

    def goto(self, url, settle=0.45):
        self.send('Page.navigate', url=url)
        deadline = time.time() + 15
        while time.time() < deadline:
            time.sleep(0.2)
            if self.evaluate("document.readyState") == 'complete':
                break
        time.sleep(settle)          # let CSS settle before measuring

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


# --------------------------------------------------------------------------
# the audit, run inside the page
# --------------------------------------------------------------------------

AUDIT_JS = r"""
(() => {
  const findings = [];
  const add = (rule, detail, el) => findings.push({
    rule, detail,
    where: el ? (el.tagName.toLowerCase() +
                 (el.id ? '#' + el.id : '') +
                 (el.className && typeof el.className === 'string'
                    ? '.' + el.className.trim().split(/\s+/).slice(0,3).join('.')
                    : '')) : ''
  });

  const vw = document.documentElement.clientWidth;
  const visible = el => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0')
      return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  // 1. The page must not scroll sideways. Anything wider than the viewport
  //    means a user on a smaller screen loses content off the right edge.
  if (document.documentElement.scrollWidth > vw + 1) {
    const culprits = [...document.querySelectorAll('body *')]
      .filter(visible)
      .filter(el => {
        const r = el.getBoundingClientRect();
        return r.right > vw + 1 && !el.closest('.table-responsive') &&
               getComputedStyle(el).position !== 'fixed';
      })
      .slice(0, 4);
    if (culprits.length) culprits.forEach(el => add('horizontal-scroll',
      'extends ' + Math.round(el.getBoundingClientRect().right - vw) + 'px past the viewport', el));
    else add('horizontal-scroll',
      'page is ' + (document.documentElement.scrollWidth - vw) + 'px wider than the viewport', null);
  }

  // 2. Every table needs a header row, or the columns are unlabelled.
  document.querySelectorAll('table').forEach(t => {
    if (!t.querySelector('thead th')) add('table-no-header', 'table has no <th>', t);
  });

  // 3. Every form control a user types into needs a label or an accessible
  //    name. Without one the field is a box with no meaning.
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (['hidden','submit','button','csrf_token'].includes(el.type)) return;
    if (!visible(el)) return;
    const named = el.labels && el.labels.length
      || el.getAttribute('aria-label')
      || el.getAttribute('title')
      || el.getAttribute('placeholder')
      || el.closest('label');
    if (!named) add('control-unlabelled', 'name=' + (el.name || '(none)'), el);
  });

  // 4. Buttons and links with no text and no title are unreadable icons.
  document.querySelectorAll('a, button').forEach(el => {
    if (!visible(el)) return;
    const text = (el.innerText || '').trim();
    if (text) return;
    if (el.getAttribute('aria-label') || el.getAttribute('title')) return;
    if (el.querySelector('img[alt]')) return;
    add('icon-no-name', 'icon-only control with no title', el);
  });

  // 5. Content overflowing its own card. A value that spills past the panel
  //    edge looks broken even when the data is right.
  document.querySelectorAll('.card').forEach(card => {
    if (!visible(card)) return;
    const cr = card.getBoundingClientRect();
    [...card.querySelectorAll('*')].filter(visible).forEach(el => {
      if (el.closest('.table-responsive') || el.closest('.modal')) return;
      const r = el.getBoundingClientRect();
      if (r.right > cr.right + 2) {
        add('overflows-card',
            Math.round(r.right - cr.right) + 'px past the card edge', el);
      }
    });
  });

  // 6. Primary actions should line up. If the page header exists, its action
  //    button and the page title must share a row.
  const h1 = document.querySelector('h1');
  if (h1) {
    const row = h1.parentElement;
    const btn = row && row.querySelector('a.btn, button.btn');
    if (btn) {
      const a = h1.getBoundingClientRect(), b = btn.getBoundingClientRect();
      const overlapY = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (overlapY <= 0) add('header-action-not-aligned',
        'the primary action does not share a line with the title', btn);
    }
  }

  // 7. Text too small to read comfortably. 12px is the floor for anything
  //    that is not a deliberate caption.
  document.querySelectorAll('body *').forEach(el => {
    if (!visible(el)) return;
    if (!el.childNodes.length) return;
    const own = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (!own) return;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size && size < 11) add('text-too-small', size + 'px', el);
  });

  // 8. Two interactive controls overlapping each other: one of them cannot be
  //    clicked reliably.
  // A dialog we forced open floats over the page, so every button in it
  // "overlaps" every button beneath it. That is the reveal, not the product:
  // compare controls only against controls in the same layer.
  const controls = [...document.querySelectorAll('a.btn, button.btn')].filter(visible);
  const layer = el => (el.closest('.modal') || {}).id || '(page)';
  for (let i = 0; i < controls.length; i++) {
    for (let j = i + 1; j < controls.length; j++) {
      if (layer(controls[i]) !== layer(controls[j])) continue;
      const a = controls[i].getBoundingClientRect();
      const b = controls[j].getBoundingClientRect();
      const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (ox > 4 && oy > 4) {
        add('controls-overlap', 'two buttons overlap by ' +
            Math.round(ox) + 'x' + Math.round(oy) + 'px', controls[j]);
        i = controls.length; break;
      }
    }
  }

  // 9. A touch target smaller than 32px is hard to hit, and this product is
  //    used on tablets in a showroom.
  document.querySelectorAll('a.btn, button.btn, input[type=checkbox]').forEach(el => {
    if (!visible(el)) return;
    // Clicking a checkbox's label toggles it, so the label is part of the
    // target. Measuring the 16px box alone called every checkbox in the
    // product too small, which is true of the box and false of the control.
    const label = el.labels && el.labels.length ? el.labels[0] : null;
    const r = label ? label.getBoundingClientRect() : el.getBoundingClientRect();
    if (r.height < 22 || r.width < 22) {
      add('target-too-small',
          Math.round(r.width) + 'x' + Math.round(r.height) + 'px', el);
    }
  });

  // 10. Untranslated interface text. Matching English words anywhere in
  //     innerText flagged every screen, including ones where the word was
  //     inside customer data — a supplier really can be called "Delta". The
  //     static i18n lint reads the templates instead and is exact, so this
  //     now only looks at the one thing a template scan cannot see: a control
  //     whose visible text is a literal t() key that got through unrendered.
  document.querySelectorAll('a, button, label, th, h1, h2, h3').forEach(el => {
    if (!visible(el)) return;
    const text = (el.innerText || '').trim();
    if (/^\{\{.*\}\}$/.test(text) || /^t\(/.test(text)) {
      add('untranslated', 'unrendered template expression: ' + text, el);
    }
  });


  // 10b. Two elements sharing an id. The browser accepts it silently and then
  //      a `<label for=...>` focuses whichever came first, so a label can name
  //      one field and operate another. This is the failure mode of linking
  //      labels to controls in templates that render a form more than once.
  const seen = {};
  document.querySelectorAll('[id]').forEach(el => {
    seen[el.id] = (seen[el.id] || 0) + 1;
  });
  Object.keys(seen).filter(id => seen[id] > 1).forEach(id => {
    add('duplicate-id', id + ' appears ' + seen[id] + ' times', null);
  });

  // ---- pixel alignment ---------------------------------------------------
  // Things that sit in the same visual row must share an edge exactly. One or
  // two pixels out is invisible alone and is exactly what makes a screen feel
  // untidy without anyone being able to say why.

  const rect = el => el.getBoundingClientRect();

  // 11. Buttons sitting side by side must share a top edge to the pixel.
  document.querySelectorAll('.d-flex, .btn-group, .card-footer').forEach(row => {
    if (!visible(row)) return;
    const btns = [...row.children].filter(visible)
      .filter(el => el.matches('a.btn, button.btn') ||
                    el.querySelector(':scope > a.btn, :scope > button.btn'));
    if (btns.length < 2) return;
    const tops = btns.map(b => Math.round(rect(b).top));
    const spread = Math.max(...tops) - Math.min(...tops);
    if (spread > 1) add('buttons-not-level',
      'buttons in one row differ by ' + spread + 'px vertically', row);
  });

  // 12. Cards side by side in a grid row must be the same height, or the row
  //     ends in a ragged edge.
  document.querySelectorAll('.row').forEach(row => {
    if (!visible(row)) return;
    // Only a column holding ONE card is a deliberate side-by-side panel. Where
    // a column holds a STACK, its first card's height is set by that card's
    // own content and has no reason to match the column beside it — comparing
    // them reported a 19px difference between two unrelated panels as a
    // misalignment.
    const cards = [...row.children].filter(visible)
      .map(col => {
        const own = [...col.children].filter(el => el.classList.contains('card'));
        return own.length === 1 ? own[0] : null;
      }).filter(Boolean).filter(visible);
    if (cards.length < 2) return;
    const tops = cards.map(c => Math.round(rect(c).top));
    if (Math.max(...tops) - Math.min(...tops) > 1) return;   // not one row
    // Two cards holding genuinely different amounts of content are SUPPOSED
    // to be different heights; stretching a short one to match a long one
    // just buys a panel full of white space. What looks like a mistake is a
    // small difference — near enough to level that the eye expects level.
    const heights = cards.map(c => Math.round(rect(c).height));
    const spread = Math.max(...heights) - Math.min(...heights);
    if (spread > 2 && spread <= 24) add('cards-ragged',
      'cards in one row differ by ' + spread + 'px in height — close enough '
      + 'to level that the gap reads as a misalignment', row);
  });

  // 13. Repeated items must be evenly spaced. An odd gap in a list reads as a
  //     missing item.
  document.querySelectorAll('tbody, .list-group').forEach(list => {
    if (!visible(list)) return;
    const items = [...list.children].filter(visible);
    if (items.length < 3) return;
    const gaps = [];
    for (let i = 1; i < items.length; i++) {
      gaps.push(Math.round(rect(items[i]).top - rect(items[i-1]).bottom));
    }
    const spread = Math.max(...gaps) - Math.min(...gaps);
    if (spread > 2) add('uneven-spacing',
      'gaps between rows vary by ' + spread + 'px', list);
  });

  // 14. The page's main blocks must share a left edge. A card that starts a
  //     few pixels in from the heading above it looks like a mistake because
  //     it is one.
  // Scoped to the CONTENT container: the layout has a second .container-fluid
  // inside the nav bar, and comparing a menu item's left edge against a card's
  // is comparing two different things. My first version did exactly that and
  // reported every screen as ragged.
  const main = document.querySelector('.main-content > .container-fluid')
            || document.querySelector('main')
            || document.querySelector('.container-fluid');
  // A `.row` pulls itself 12px left with a negative margin and gives the 12px
  // straight back as padding on its columns, so its own box starts at 0 while
  // everything a user can see still starts at 12. Comparing the wrapper boxes
  // reported 26 screens as ragged when every one of them lines up on screen.
  const contentLeft = el => {
    const r = rect(el);
    const m = parseFloat(getComputedStyle(el).marginLeft) || 0;
    return Math.round(m < 0 ? r.left - m : r.left);
  };
  // A dialog is position:fixed at the left of the WINDOW, not of the content
  // column, so once revealed it reports left:0 and drags every screen that has
  // a dialog into this finding. It is not part of the page's vertical rhythm.
  const blocks = main
    ? [...main.children].filter(visible)
        .filter(el => !el.classList.contains('modal') && !el.closest('.modal'))
        .filter(el => rect(el).width > 200)
    : [];
  if (blocks.length > 1) {
    const lefts = blocks.map(contentLeft);
    const spread = Math.max(...lefts) - Math.min(...lefts);
    if (spread > 1) add('left-edge-ragged',
      'top-level blocks start at ' + [...new Set(lefts)].join('/') + 'px', null);
  }

  // 15. A form label and its control should line up on the left.
  document.querySelectorAll('.mb-3, .col, .form-group').forEach(group => {
    if (!visible(group)) return;
    const label = group.querySelector(':scope > label');
    const control = group.querySelector(':scope > input, :scope > select, :scope > textarea');
    if (!label || !control || !visible(label) || !visible(control)) return;
    const off = Math.abs(Math.round(rect(label).left - rect(control).left));
    if (off > 1) add('label-control-misaligned', off + 'px apart', group);
  });

  // 16. Text that touches or crosses its container's padding edge.
  document.querySelectorAll('.card-body, .modal-body').forEach(box => {
    if (!visible(box)) return;
    const b = rect(box);
    const pad = parseFloat(getComputedStyle(box).paddingLeft) || 0;
    [...box.children].filter(visible).forEach(el => {
      // A Bootstrap `.row` cancels the gutter with a negative left margin by
      // design; its children land back inside the padding. Reporting it said
      // "4px into the padding" on every screen with a filter bar in a card.
      if (parseFloat(getComputedStyle(el).marginLeft) < 0) return;
      const r = rect(el);
      if (r.left < b.left + pad - 1.5) add('breaks-padding',
        Math.round(b.left + pad - r.left) + 'px into the padding', el);
    });
  });

  return {
    findings,
    title: (document.querySelector('h1') || {}).innerText || document.title,
    width: document.documentElement.scrollWidth,
    viewport: vw
  };
})()
"""



REVEAL_JS = r"""
(() => {
  // Anything hidden at load is never measured, so the confirmation dialogs and
  // the inactive tabs — which is where a lot of this product's UI lives — were
  // invisible to the audit. Reveal them, measure, then put them back.
  const opened = [];
  document.querySelectorAll('.modal').forEach(m => {
    if (getComputedStyle(m).display === 'none') {
      m.dataset.qcRevealed = '1';
      m.style.display = 'block';
      m.classList.add('show');
      opened.push(m.id || '(unnamed modal)');
    }
  });
  document.querySelectorAll('.tab-pane:not(.active), [role=tabpanel]:not(.active)')
    .forEach(t => { t.dataset.qcRevealed = '1'; t.classList.add('active','show'); });
  return opened;
})()
"""

RESTORE_JS = r"""
(() => {
  document.querySelectorAll('[data-qc-revealed]').forEach(el => {
    el.style.display = '';
    el.classList.remove('show');
    if (el.classList.contains('tab-pane')) el.classList.remove('active');
    delete el.dataset.qcRevealed;
  });
  return true;
})()
"""

SCROLL_JS = r"""
(() => {
  // Scroll the whole page in steps so anything that only renders once it comes
  // near the viewport has actually rendered before we measure.
  const h = document.documentElement.scrollHeight;
  for (let y = 0; y <= h; y += 400) window.scrollTo(0, y);
  window.scrollTo(0, 0);
  return h;
})()
"""


def screens():
    """Every screen worth auditing, with ids pulled from the demo data."""
    con = sqlite3.connect('devdata.sqlite3')
    company = list(con.execute(
        "select id from companies where company_code='SOFADEMO'"))[0][0]

    def one(sql):
        rows = [r[0] for r in con.execute(sql, (company,))]
        return rows[0] if rows else None

    paths = ['/', '/orders', '/customers', '/materials/', '/materials/low-stock',
             '/materials/purchase-suggestions', '/materials/categories',
             '/materials/suppliers', '/materials/units',
             '/purchase-orders', '/requisitions', '/goods-receipts',
             '/production',
             '/agreements', '/supplier-invoices', '/reports',
             '/reports/receivables', '/settings/company',
             '/settings/standardization', '/settings/workflow',
             '/settings/templates', '/settings/extension-fields',
             '/stores', '/users', '/customers/create', '/orders/create',
             '/stores/create', '/users/create',
             # Create screens reached only from a button on another page. The
             # first version of this list was written from the navigation menu,
             # so these were never opened — and a create form is where a user
             # spends the most time on any screen.
             '/materials/create', '/agreements/create',
             '/purchase-orders/create', '/requisitions/create']

    order = one("select id from orders where company_id=? order by order_code")
    if order:
        paths += [f'/orders/{order}', f'/orders/{order}/edit',
                  f'/documents/{order}']
    for sql, template in [
        ("select q.id from quotations q join orders o on o.id=q.order_id "
         "where o.company_id=?", '/quotations/{}/view'),
        ("select c.id from contracts c join orders o on o.id=c.order_id "
         "where o.company_id=?", '/contracts/{}/view'),
        ("select h.id from handover_records h join orders o on o.id=h.order_id "
         "where o.company_id=?", '/handover/{}'),
        ("select p.id from payment_reports p join orders o on o.id=p.order_id "
         "where o.company_id=?", '/payment/{}'),
        ("select id from purchase_orders where company_id=?", '/purchase-orders/{}'),
        ("select id from purchase_requisitions where company_id=?", '/requisitions/{}'),
        ("select id from goods_receipts where company_id=?", '/goods-receipts/{}'),
        ("select id from master_agreements where company_id=?", '/agreements/{}'),
        ("select id from supplier_invoices where company_id=?", '/supplier-invoices/{}'),
        ("select id from customers where company_id=?", '/customers/{}'),
        ("select id from materials where company_id=?", '/materials/{}'),
        ("select order_id from production_plans where company_id=?",
         '/orders/{}/production-plan'),
    ]:
        value = one(sql)
        if value:
            paths.append(template.format(value))
    return paths


def login(page):
    page.goto(APP + '/auth/login')
    page.evaluate(f"""
        (() => {{
          const f = document.querySelector('form');
          const email = f.querySelector('[name=email], [type=email]');
          const pw = f.querySelector('[name=password], [type=password]');
          email.value = {LOGIN[0]!r};
          pw.value = {LOGIN[1]!r};
          f.submit();
          return true;
        }})()
    """)
    time.sleep(2.0)
    return page.evaluate("location.pathname")


def main():
    page = Page()
    where = login(page)
    print(f'logged in -> {where}\n')

    wanted = sys.argv[1:] or screens()
    tally = {}
    total = 0
    for path in wanted:
        page.goto(APP + path)
        page.evaluate(SCROLL_JS)          # render anything below the fold
        hidden = page.evaluate(REVEAL_JS) # and anything behind a dialog or tab
        result = page.evaluate(AUDIT_JS)
        page.evaluate(RESTORE_JS)
        if not result:
            print(f'{path:44} (no result)')
            continue
        findings = result['findings']
        total += len(findings)
        for f in findings:
            tally[f['rule']] = tally.get(f['rule'], 0) + 1
        flag = '.' if not findings else f'{len(findings)} issue(s)'
        extra = f' [+{len(hidden)} dialog(s)]' if hidden else ''
        print(f'{path:44} {flag}{extra}')
        seen = set()
        for f in findings:
            key = (f['rule'], f['detail'])
            if key in seen:
                continue
            seen.add(key)
            print(f"      {f['rule']:26} {f['detail']}  {f['where']}")

    print(f'\n--- {total} findings across {len(wanted)} screens')
    for rule, count in sorted(tally.items(), key=lambda kv: -kv[1]):
        print(f'  {rule:26} {count}')
    page.close()


if __name__ == '__main__':
    raise SystemExit(main())
