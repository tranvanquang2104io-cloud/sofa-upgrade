"""Defects found by doing the work in Chrome, pinned where Python can see them.

A browser pass (scripts/browser_check.py) drove the sales and purchase flows the
way staff do — typing, clicking, answering confirm() — and found what 1,400
green tests had not: the first quotation line never calculated, a 0 đ advance
could be saved and confirmed, a supplier with no tax code produced an invoice
whose tax code was the word "None", and a pay form with nothing suggested.

The JavaScript half of these is checked by that script, in a real browser. What
is here is the server half, plus the few template facts a lint can hold.
"""
import datetime as dt
import pathlib
import re

import pytest
from flask import render_template_string

from app.models.models import SupplierInvoice
from tests.test_payables_screens import po  # noqa: F401 — fixture

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / 'app' / 'templates'


# -- A missing value is shown as nothing, never as the word "None" -----------

def test_none_renders_as_nothing(app):
    with app.test_request_context():
        assert render_template_string('<input value="{{ v }}">', v=None) == '<input value="">'
        # ...and only None: falsy values that mean something still print.
        assert render_template_string('{{ a }}|{{ b }}|{{ c }}', a=0, b=False, c='') == '0|False|'
        # The fallback idiom the templates use keeps working.
        assert render_template_string("{{ v or 'N/A' }}", v=None) == 'N/A'


def test_a_supplier_without_a_tax_code_does_not_become_None(app, client, login, po):
    from app.config import db
    from app.models.models import PurchaseOrder
    with app.app_context():
        PurchaseOrder.query.get(po['po_id']).supplier.tax_code = None
        db.session.commit()
    login('admin')
    body = client.get(f'/purchase-orders/{po["po_id"]}/invoice').get_data(as_text=True)
    field = re.search(r'<input[^>]*name="seller_tax_code"[^>]*>', body, re.S).group(0)
    assert 'value="None"' not in field
    assert 'value=""' in field


# -- A payment document must be for some money --------------------------------

def test_a_payment_for_nothing_is_refused(app, seeded_order):
    from app.models.models import PaymentReport
    from app.services.services import PaymentReportService

    with app.app_context():
        with pytest.raises(ValueError, match='chưa có số tiền'):
            PaymentReportService().create_payment_report(
                order_id=seeded_order['order_id'], report_number='TT-ZERO',
                payment_type='advance', report_date=dt.date(2026, 9, 30),
                payment_date=dt.date(2026, 9, 30), amount=0, items=[])
        assert PaymentReport.query.filter_by(report_number='TT-ZERO').first() is None


def test_the_payment_form_loads_the_contract_when_it_opens():
    """The header knew the contract's value while the table stayed empty."""
    text = (TEMPLATES / 'payments' / 'create.html').read_text(encoding='utf-8')
    assert "request.method == 'GET'" in text and 'loadBtn.click()' in text


# -- Quotation lines calculate as they are typed ------------------------------

@pytest.mark.parametrize('screen', ['create.html', 'edit.html'])
def test_every_quotation_line_is_wired_through_the_table(screen):
    """Listeners attached only in addRow() left the page's own row dead."""
    text = (TEMPLATES / 'quotations' / screen).read_text(encoding='utf-8')
    assert "getElementById('items-tbody').addEventListener('input'" in text
    assert "row.querySelector('.qty-input').addEventListener" not in text


@pytest.mark.parametrize('path', ['quotations/edit.html', 'contracts/edit.html'])
def test_stored_amount_in_words_is_not_frozen_on_open(path):
    """Words written for the old amount must be rewritten when it changes."""
    text = (TEMPLATES / path).read_text(encoding='utf-8')
    assert re.search(r'(total|contractTotal)AtLoad', text)
    assert "if (wordsInput.value.trim()) wordsInput._userEdited = true" not in text
    assert "if (aiw.value.trim()) aiw.dataset.manualEdit = '1'" not in text


# -- The pay form suggests what every other form suggests ---------------------

def test_the_pay_form_suggests_a_voucher_number_and_today(app, client, login, po):
    login('admin')
    client.post(f'/purchase-orders/{po["po_id"]}/invoice', data={
        'invoice_number': '0007001', 'invoice_date': '2026-06-20', 'vat_rate': '8',
        f'qty_{po["line_id"]}': '10', f'price_{po["line_id"]}': '100000',
    }, follow_redirects=True)
    with app.app_context():
        inv_id = str(SupplierInvoice.query.filter_by(invoice_number='0007001').first().id)
    client.post(f'/supplier-invoices/{inv_id}/confirm', follow_redirects=True)

    body = client.get(f'/supplier-invoices/{inv_id}').get_data(as_text=True)
    number = re.search(r'name="payment_number"[^>]*value="([^"]*)"', body)
    date = re.search(r'name="payment_date"[^>]*value="([^"]*)"', body)
    assert number and re.fullmatch(rf'CHI-{dt.date.today():%y%m}-\d{{4}}', number.group(1))
    assert date and date.group(1) == dt.date.today().isoformat()


# -- Advice names the step it is about ----------------------------------------

def test_workflow_advice_names_its_step(app, seeded_order):
    from app.models.models import Order
    from app.services.workflow_service import ACTION_LABELS_VI, WorkflowService
    with app.app_context():
        advice = WorkflowService.advisories(Order.query.get(seeded_order['order_id']))
    assert advice, 'a new order gets at least the "approve the quotation first" advice'
    for item in advice:
        assert item['label'] == ACTION_LABELS_VI[item['action']]


# -- Every screen's main button says what it does -----------------------------

def test_form_actions_never_renders_a_wordless_button(app):
    with app.test_request_context():
        html = render_template_string(
            '{% from "macros/ui.html" import form_actions with context %}{{ form_actions(cancel_url="/x") }}')
    label = re.search(r'<button type="submit"[^>]*>\s*<i class="bi [^"]+"></i>(.*?)</button>', html, re.S)
    assert label and label.group(1).strip(), 'the primary button has an icon and no words'
