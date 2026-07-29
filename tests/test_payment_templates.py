"""Advance vs final payment templates render distinctly and correctly."""
import os
import re
import sys
import zipfile
from datetime import date
from decimal import Decimal


def _render_text(tpl_path, ctx):
    from app.utils.template_engine import DocxTemplateEngine
    bio = DocxTemplateEngine.render(tpl_path, ctx)
    xml = zipfile.ZipFile(bio).read('word/document.xml').decode('utf-8', 'ignore')
    return re.sub(r'<[^>]+>', '', xml).replace('&amp;', '&')


def _ctx(app, seed, payment_type, amount):
    from app.config import db
    from app.models.models import Order, Contract, PaymentReport
    from app.utils.template_engine import DocumentVariableCollector as C
    from app.models.models import Company, Customer
    with app.app_context():
        sfx = payment_type[:3].upper()
        o = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                  customer_id=seed['customer_id'], order_code=f'PT-{sfx}', title='Bọc sofa')
        db.session.add(o); db.session.flush()
        c = Contract(order_id=o.id, company_id=seed['company_id'], contract_number=f'HD-{sfx}',
                     contract_date=date(2026, 7, 29), contract_value=Decimal('48600000'),
                     advance_percentage=30, advance_amount=Decimal('14580000'))
        db.session.add(c); db.session.flush()
        p = PaymentReport(order_id=o.id, company_id=seed['company_id'], report_number=f'TT-{sfx}',
                          payment_type=payment_type, report_date=date(2026, 7, 29),
                          payment_date=date(2026, 7, 29), amount=Decimal(str(amount)),
                          advance_percentage=30, advance_amount=Decimal('14580000'),
                          remaining_amount=Decimal('34020000'), items=[{'name': 'Sofa', 'unit': 'Bộ',
                          'quantity': 1, 'unit_price': 48600000, 'total': 48600000}])
        db.session.add(p); db.session.commit()
        company = Company.query.get(seed['company_id'])
        cust = Customer.query.get(seed['customer_id'])
        return C.collect_payment_variables(p, cust, o, company=company, contract=c)


def test_advance_and_final_templates_are_distinct(app, seed, tmp_path):
    sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))
    from create_payment_templates import build_advance, build_final
    adv = str(tmp_path / 'adv.docx'); fin = str(tmp_path / 'fin.docx')
    build_advance(adv); build_final(fin)

    ta = _render_text(adv, _ctx(app, seed, 'advance', 14580000))
    assert 'GIẤY ĐỀ NGHỊ TẠM ỨNG' in ta
    assert 'THANH TOÁN' not in ta.replace('THÔNG TIN THANH TOÁN', '')  # only the payment-info label
    assert '{{' not in ta and '{%' not in ta            # every tag resolved
    assert '48,600,000' in ta and '14,580,000' in ta    # contract total + advance amount
    assert 'Sofa' in ta                                  # items loop rendered

    tf = _render_text(fin, _ctx(app, seed, 'final', 34020000))
    assert 'GIẤY ĐỀ NGHỊ THANH TOÁN' in tf
    assert 'TẠM ỨNG' not in tf.split('Đã tạm ứng')[0]    # title isn't advance
    assert '{{' not in tf and '{%' not in tf
    assert '48,600,000' in tf and '14,580,000' in tf and '34,020,000' in tf
