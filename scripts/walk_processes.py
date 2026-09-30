"""Drive every business process end to end against a running app.

`walk_screens.py` answers "does every screen open, and can every action be
reached?". It cannot answer the question a shop owner actually has: **does the
work get done?** A screen can render perfectly and a process still stop dead
in the middle, because the state after step three is not the state step four
needs.

So this walks the journeys, not the routes, and asserts the CONSEQUENCE at
each step — the flags, the money, the stock — rather than the HTTP status. A
302 proves a redirect happened, not that anything was recorded.

Run with the app up:

    SOFA_APP=http://127.0.0.1:5002 SOFA_DB=path/to.db \\
        python scripts/walk_processes.py

Every step prints PASS or FAIL with what was actually observed, and the exit
code is non-zero if any process failed to complete. Nothing is skipped
silently: a step that cannot run says so and why.
"""
import os
import re
import sys

import requests

APP = os.environ.get('SOFA_APP', 'http://127.0.0.1:5000')
DB = os.environ.get('SOFA_DB', 'devdata.sqlite3')
LOGIN = (os.environ.get('SOFA_USER', 'demo@sofa.test'),
         os.environ.get('SOFA_PASS', 'demo1234'))

results = []


def record(process, step, ok, detail=''):
    results.append((process, step, ok, detail))
    mark = 'PASS' if ok else 'FAIL'
    print(f'  [{mark}] {step}' + (f'  — {detail}' if detail else ''))
    return ok


def q(sql, *args):
    from walk_screens import connect
    conn = connect(DB)
    try:
        row = conn.execute(sql, args).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


class App:
    """A logged-in browser session that keeps the CSRF token fresh."""

    def __init__(self):
        self.s = requests.Session()

    def token(self, path='/'):
        html = self.s.get(APP + path, timeout=30).text
        m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
        return m.group(1) if m else ''

    def login(self, email, password):
        t = self.token('/auth/login')
        r = self.s.post(APP + '/auth/login',
                        data={'email': email, 'password': password,
                              'csrf_token': t}, timeout=30,
                        allow_redirects=False)
        return r.status_code in (301, 302)

    def get(self, path, **kw):
        return self.s.get(APP + path, timeout=60, **kw)

    def post(self, path, data=None, files=None, token_from='/'):
        payload = dict(data or {})
        payload['csrf_token'] = self.token(token_from)
        return self.s.post(APP + path, data=payload, files=files, timeout=60,
                           allow_redirects=True)


def process_sales(app, company_id):
    """Quotation → contract → signature → advance → handover → final payment.

    The spine of the product. Each step is checked by what it left behind,
    because a step that redirects and records nothing looks identical to one
    that worked.
    """
    print('\n=== BÁN HÀNG: báo giá → hợp đồng → ký → tạm ứng → bàn giao → tất toán ===')
    customer_id = q('select id from customers where store_id in '
                    '(select id from stores where company_id=?)', company_id)
    if not customer_id:
        return record('sales', 'a customer exists to sell to', False,
                      'no customer in the seed')
    # The route validates that the customer belongs to the chosen branch, so
    # the branch must be the customer's own — not simply the first one.
    store_id = q('select store_id from customers where id=?', customer_id)

    # 1. an order
    r = app.post('/orders/create', {
        'customer_id': customer_id, 'store_id': store_id,
        'order_code': 'E2E-001',
        'title': 'Sofa góc L + 2 đôn — chạy thử quy trình',
        'order_date': '2026-09-01'}, token_from='/orders/create')
    order_id = q("select id from orders where order_code='E2E-001'")
    if not record('sales', 'tạo đơn hàng', bool(order_id),
                  f'HTTP {r.status_code}'):
        return False

    # 2. a quotation on it
    app.post(f'/quotations/{order_id}/create', {
        'quotation_number': 'E2E-BG-001', 'quotation_date': '2026-09-01',
        'item_name[]': 'Sofa góc L', 'item_unit[]': 'Bộ',
        'item_quantity[]': '1', 'item_price[]': '32000000', 'vat_rate': '8',
    }, token_from=f'/quotations/{order_id}/create')
    quotation_id = q("select id from quotations where quotation_number='E2E-BG-001'")
    total = q('select total_amount from quotations where id=?', quotation_id)
    record('sales', 'lập báo giá', bool(quotation_id),
           f'tổng {float(total or 0):,.0f} đ')

    # 3. approve it
    app.post(f'/quotations/{quotation_id}/approve',
             token_from=f'/quotations/{quotation_id}/view')
    approved = q('select is_approved from quotations where id=?', quotation_id)
    record('sales', 'duyệt báo giá', bool(approved))

    # 4. a contract
    app.post(f'/contracts/{order_id}/create', {
        'contract_number': 'E2E-HD-001', 'contract_date': '2026-09-02',
        'item_name[]': 'Sofa góc L', 'item_unit[]': 'Bộ',
        'item_quantity[]': '1', 'item_price[]': '32000000',
        'vat_rate': '8', 'advance_percentage': '50',
    }, token_from=f'/contracts/{order_id}/create')
    contract_id = q("select id from contracts where contract_number='E2E-HD-001'")
    value = q('select contract_value from contracts where id=?', contract_id)
    record('sales', 'lập hợp đồng', bool(contract_id),
           f'giá trị {float(value or 0):,.0f} đ')

    # 5. sign it
    app.post(f'/contracts/{contract_id}/sign',
             token_from=f'/contracts/{contract_id}/view')
    signed = q('select is_signed from contracts where id=?', contract_id)
    lifecycle_signed = q('select contract_signed from lifecycle_statuses '
                         'where order_id=?', order_id)
    record('sales', 'ký hợp đồng', bool(signed) and bool(lifecycle_signed),
           'cờ hợp đồng và lifecycle cùng bật')

    # 6. the advance
    app.post(f'/payment/{order_id}/create', {
        'report_number': 'E2E-TT-001', 'report_date': '2026-09-03',
        'payment_date': '2026-09-03', 'payment_type': 'advance',
        'amount': '16000000', 'payment_method': 'bank_transfer',
    }, token_from=f'/payment/{order_id}/create')
    payment_id = q("select id from payment_reports where report_number='E2E-TT-001'")
    record('sales', 'ghi nhận tạm ứng', bool(payment_id))

    # 7. confirm the money (admin decides directly)
    app.post(f'/payment/{payment_id}/confirm',
             token_from=f'/payment/{payment_id}')
    confirmed = q('select is_confirmed from payment_reports where id=?', payment_id)
    advance_paid = q('select advance_paid from lifecycle_statuses where order_id=?',
                     order_id)
    record('sales', 'xác nhận đã thu tiền', bool(confirmed) and bool(advance_paid),
           'phiếu và lifecycle cùng đổi')

    # 8. the audit trail recorded it
    who = q("select user_name from document_transitions where document_id=? "
            "and action='payment.confirm'", payment_id)
    record('sales', 'sổ "ai làm gì" ghi lại', bool(who), f'người xác nhận: {who}')

    # 9. handover
    app.post(f'/handover/{order_id}/create', {
        'report_number': 'E2E-BB-001', 'report_date': '2026-09-10',
        'handover_date': '2026-09-10',
    }, token_from=f'/handover/{order_id}/create')
    handover_id = q("select id from handover_records where report_number='E2E-BB-001'")
    record('sales', 'lập biên bản bàn giao', bool(handover_id))

    if handover_id:
        app.post(f'/handover/{handover_id}/confirm',
                 token_from=f'/handover/{handover_id}')
        hconf = q('select is_confirmed from handover_records where id=?', handover_id)
        hlife = q('select handover_confirmed from lifecycle_statuses where order_id=?',
                  order_id)
        record('sales', 'xác nhận bàn giao', bool(hconf) and bool(hlife))

    # 10. final payment — THE REST OF WHAT IS OWED, not a round number.
    #
    # My first version paid 16m + 16m against a 34,560,000 đ contract and then
    # complained the order would not close. It was right not to: 32m of
    # 34.56m had been paid and 2,560,000 đ — exactly the 8% VAT — was still
    # outstanding. The product refusing to call that "fully paid" is the
    # behaviour anybody would want; the arithmetic in the test was what was
    # wrong. Pay the actual balance.
    agreed = float(q('select contract_value from contracts where order_id=?',
                     order_id) or 0)
    paid = float(q('select coalesce(sum(amount),0) from payment_reports '
                   'where order_id=? and is_confirmed=1 and is_canceled=0',
                   order_id) or 0)
    remaining = round(agreed - paid)
    app.post(f'/payment/{order_id}/create', {
        'report_number': 'E2E-TT-002', 'report_date': '2026-09-11',
        'payment_date': '2026-09-11', 'payment_type': 'final',
        'amount': str(remaining), 'payment_method': 'cash',
    }, token_from=f'/payment/{order_id}/create')
    final_id = q("select id from payment_reports where report_number='E2E-TT-002'")
    if final_id:
        app.post(f'/payment/{final_id}/confirm', token_from=f'/payment/{final_id}')
    fully = q('select fully_paid from lifecycle_statuses where order_id=?', order_id)
    record('sales', 'thu nốt và đóng đơn', bool(fully),
           f'đã thu đủ {agreed:,.0f} đ (đợt cuối {remaining:,.0f} đ)')
    return True


def process_procurement(app, company_id):
    """Requisition → purchase order → send → receive → stock actually moves."""
    print('\n=== MUA HÀNG: đề nghị → đơn mua → gửi NCC → nhập kho → tồn tăng ===')
    supplier_id = q('select id from suppliers where company_id=?', company_id)
    material_id = q('select id from materials where company_id=?', company_id)
    if not (supplier_id and material_id):
        return record('procurement', 'có NCC và vật tư', False, 'seed thiếu')

    before = q('select coalesce(sum(current_quantity),0) from material_stock '
               'where material_id=?', material_id) or 0

    app.post('/requisitions/create', {
        'title': 'E2E — bổ sung vải', 'request_date': '2026-09-05',
        'line_material_id[]': material_id, 'line_quantity[]': '30',
        'line_unit[]': 'm'}, token_from='/requisitions/create')
    pr_id = q("select id from purchase_requisitions where title='E2E — bổ sung vải'")
    record('procurement', 'lập đề nghị mua', bool(pr_id))

    # The PO number is ASSIGNED BY THE APP, not chosen here — sending one is
    # ignored, so looking the order up by it finds nothing even when the order
    # was created. Take the newest instead, which is what actually happened.
    newest_before = q('select count(*) from purchase_orders where company_id=?',
                      company_id)
    app.post('/purchase-orders/create', {
        'supplier_id': supplier_id, 'store_id':
            q('select id from stores where company_id=?', company_id),
        'order_date': '2026-09-06', 'vat_rate': '8',
        'line_material_id[]': material_id, 'line_quantity[]': '30',
        'line_unit[]': 'm', 'line_price[]': '450000',
    }, token_from='/purchase-orders/create')
    po_id = q('select id from purchase_orders where company_id=? '
              'order by created_at desc limit 1', company_id)
    grew = (q('select count(*) from purchase_orders where company_id=?',
              company_id) or 0) > (newest_before or 0)
    if not grew:
        po_id = None
    if not record('procurement', 'lập đơn mua hàng', bool(po_id)):
        return False

    status = q('select status from purchase_orders where id=?', po_id)
    record('procurement', 'đơn mua bắt đầu ở trạng thái nháp',
           status == 'draft', f'status={status}')

    app.post(f'/purchase-orders/{po_id}/status/submit',
             token_from=f'/purchase-orders/{po_id}')
    status = q('select status from purchase_orders where id=?', po_id)
    record('procurement', 'gửi NCC', status == 'ordered', f'status={status}')

    line_id = q('select id from purchase_order_lines where po_id=?', po_id)
    app.post(f'/purchase-orders/{po_id}/receive', {
        'receipt_date': '2026-09-12', f'qty_{line_id}': '30',
    }, token_from=f'/purchase-orders/{po_id}')
    after = q('select coalesce(sum(current_quantity),0) from material_stock '
              'where material_id=?', material_id) or 0
    record('procurement', 'nhập kho làm tồn kho TĂNG', after > before,
           f'{float(before):g} → {float(after):g}')

    gr = q('select count(*) from goods_receipts where po_id=?', po_id)
    record('procurement', 'có phiếu nhập kho', bool(gr))

    moved = q("select count(*) from stock_movements where ref_type='goods_receipt'")
    record('procurement', 'sổ kho ghi nhận chiều nhập', bool(moved),
           f'{moved} dòng')
    return True


def process_printing(app, company_id):
    """Every document type produces a file and records what made it."""
    print('\n=== IN ẤN: sinh mẫu mặc định → in → có file và có vết ===')
    for doc_type, label in (('purchase_order', 'Đơn mua hàng'),
                            ('production_plan', 'Lệnh sản xuất')):
        app.post(f'/settings/templates/seed-default/{doc_type}',
                 token_from='/settings/templates')
        made = q('select count(*) from document_templates where document_type=? '
                 'and company_id=?', doc_type, company_id)
        record('printing', f'tạo mẫu mặc định — {label}', bool(made))

    po_id = q('select id from purchase_orders where company_id=?', company_id)
    if po_id:
        r = app.get(f'/purchase-orders/{po_id}/print')
        ok = r.status_code == 200 and len(r.content) > 5000
        record('printing', 'in đơn mua hàng', ok,
               f'HTTP {r.status_code}, {len(r.content):,} bytes')
        from_tpl = q("select template_id from documents "
                     "where document_type='purchase_order' "
                     "order by generated_at desc limit 1")
        record('printing', 'bản in đến TỪ mẫu (không phải code cứng)',
               from_tpl is not None)

    plan_id = q('select id from production_plans where company_id=?', company_id)
    if plan_id:
        r = app.get(f'/production-plan/{plan_id}/print')
        record('printing', 'in lệnh sản xuất', r.status_code == 200
               and len(r.content) > 5000,
               f'HTTP {r.status_code}, {len(r.content):,} bytes')
    return True


def process_approval(app, company_id):
    """A clerk asks, a manager decides, and the decision performs the work."""
    print('\n=== DUYỆT HAI CẤP: nhân viên xin → quản lý duyệt → việc được làm ===')
    # A CLERK raises it, here and now. The seed ships one pending request, but
    # the first run of this script approves it — so a second run found an empty
    # queue and reported a failure that was really "already done". A walk that
    # only works on a virgin database is a walk nobody runs twice.
    clerk = App()
    if not clerk.login('minh@sofa.test', 'demo1234'):
        record('approval', 'nhân viên đăng nhập được', False,
               'không đăng nhập được bằng tài khoản nhân viên')
        return False
    unconfirmed = q('select id from payment_reports where company_id=? '
                    'and is_confirmed=0 and is_canceled=0', company_id)
    if unconfirmed:
        clerk.post(f'/payment/{unconfirmed}/confirm',
                   token_from=f'/payment/{unconfirmed}')

    pending = q("select count(*) from approval_requests where status='pending'")
    record('approval', 'nhân viên xin duyệt → vào hàng đợi', bool(pending),
           f'{pending} đề nghị chờ')

    req_id = q("select id from approval_requests where status='pending'")
    if not req_id:
        return record('approval', 'có đề nghị để duyệt', False,
                      'không phiếu thu nào đang chờ xác nhận')

    target = q('select target_id from approval_requests where id=?', req_id)
    app.post(f'/approvals/{req_id}/approve', token_from='/approvals')
    status = q('select status from approval_requests where id=?', req_id)
    confirmed = q('select is_confirmed from payment_reports where id=?', target)
    record('approval', 'duyệt xong thì THỰC HIỆN luôn', status == 'approved'
           and bool(confirmed), f'đề nghị={status}, phiếu thu đã xác nhận={bool(confirmed)}')
    decided_by = q('select decided_by_id from approval_requests where id=?', req_id)
    record('approval', 'ghi lại ai là người duyệt', decided_by is not None)
    return True


def process_warehouse(app, company_id):
    """Stock lives in a warehouse, and moving it leaves two ledger lines."""
    print('\n=== KHO: điều chuyển → hai dòng sổ đối ứng ===')
    n = q('select count(*) from warehouses where company_id=?', company_id)
    record('warehouse', 'có kho để chọn', bool(n), f'{n} kho')

    active = q('select count(*) from warehouses where company_id=? and is_active=1',
               company_id)
    record('warehouse', 'kho đã đóng không còn được chào', active < n,
           f'{active} đang mở / {n} tổng')

    out = q("select count(*) from stock_movements where movement_type='transfer_out'")
    inn = q("select count(*) from stock_movements where movement_type='transfer_in'")
    record('warehouse', 'mỗi lần điều chuyển ghi cả xuất lẫn nhập',
           out == inn and out > 0, f'{out} xuất / {inn} nhập')
    return True


def main():
    print(f'App: {APP}\nDB : {DB}')
    app = App()
    if not app.login(*LOGIN):
        print('FATAL: could not log in'); return 2
    print(f'Logged in as {LOGIN[0]}')

    company_id = q("select id from companies where company_code='SOFADEMO'")
    if not company_id:
        print('FATAL: SOFADEMO company not found — run scripts/seed_demo.py')
        return 2

    process_sales(app, company_id)
    process_procurement(app, company_id)
    process_printing(app, company_id)
    process_approval(app, company_id)
    process_warehouse(app, company_id)

    failed = [r for r in results if not r[2]]
    print('\n' + '=' * 62)
    print(f'{len(results) - len(failed)} / {len(results)} bước ĐẠT')
    if failed:
        print(f'\n{len(failed)} bước KHÔNG đạt:')
        for process, step, _, detail in failed:
            print(f'  - [{process}] {step}' + (f'  ({detail})' if detail else ''))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
