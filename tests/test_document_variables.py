"""Regression: document variable collector fills every placeholder used by the
hand-uploaded SOFA-NGOCHAN templates (no blank fields when printed)."""
from datetime import date
from types import SimpleNamespace as NS

from app.utils.template_engine import DocumentVariableCollector as C


def _company():
    return NS(name='NGOCHAN', address='a', production_address='pa', phone='p',
              email='e', tax_code='t', business_registration_number='b', website='w',
              representative_name='rn', representative_title='rt', vat_rate=8,
              bank_accounts=[{'bank_name': 'BN', 'account_number': 'AN', 'account_holder': 'AH'}])


def _cust():
    return NS(name='cn', customer_code='cc', phone='cp', email='ce', address='ca',
              city='ci', postal_code='pc', tax_code='ct',
              representative_name='crn', representative_title='crt')


def test_company_ctx_has_uppercase_alias():
    ctx = C._company_ctx(_company())
    assert ctx['COMPANY_NAME'] == 'NGOCHAN'
    assert ctx['company_name'] == 'NGOCHAN'


def test_header_city_from_store_and_contract_header_date():
    """Header '<Tỉnh/TP>, ngày…' city comes from the store; the contract's top
    header (which reuses quotation_* tokens) shows the CONTRACT date."""
    store = NS(city='Tỉnh Đồng Tháp')
    order = NS(order_code='oc', title='ot', description='d', store=store)
    quo = NS(quotation_number='BG', quotation_date=date(2026, 7, 29), validity_days=30,
             city='doc-city', items=[], subtotal=0, vat_rate=8, vat_amount=0, shipping_fee=0,
             another_fee=0, total_amount=0, amount_in_words='', payment_terms='', notes='')
    qc = C.collect_quotation_variables(quo, _cust(), order, company=_company())
    assert qc['city'] == 'Tỉnh Đồng Tháp'   # store wins over quotation.city

    contract = NS(contract_number='HD', contract_date=date(2026, 8, 15), contract_start_date=None,
                  contract_value=0, amount_in_words='', city='doc-city', contract_days_complete=30,
                  num_date_notice_cancel=7, items=[], subtotal=0, vat_rate=8, vat_amount=0,
                  shipping_fee=0, another_fee=0, advance_percentage=30, advance_amount=0,
                  warranty_months=12, delivery_terms='', terms_and_conditions='',
                  selected_bank_index=0, quotation=quo)
    cc = C.collect_contract_variables(contract, None, _cust(), order, company=_company())
    assert cc['city'] == 'Tỉnh Đồng Tháp'
    assert (cc['quotation_day'], cc['quotation_month'], cc['quotation_year']) == ('15', '08', '2026')


def test_contract_ctx_falls_back_to_linked_quotation():
    """When no quotation is passed, quotation_number comes from contract.quotation."""
    quo = NS(quotation_number='BG-DEMO-2026', items=[])
    contract = NS(contract_number='HD-1', contract_date=date.today(), contract_start_date=None,
                  contract_value=100, amount_in_words='w', city='c', contract_days_complete=30,
                  num_date_notice_cancel=7, items=[], subtotal=100, vat_rate=8, vat_amount=8,
                  shipping_fee=0, another_fee=0, advance_percentage=30, advance_amount=30,
                  warranty_months=12, delivery_terms='dt', terms_and_conditions='tc',
                  selected_bank_index=0, quotation=quo)
    ctx = C.collect_contract_variables(contract, None, _cust(),
                                       NS(order_code='oc', title='ot', description='d'),
                                       company=_company())
    assert ctx['quotation_number'] == 'BG-DEMO-2026'


def test_payment_ctx_has_quotation_number_and_total():
    contract = NS(contract_number='CN', contract_date=date.today(),
                  contract_value=108, advance_percentage=30, advance_amount=32,
                  quotation=NS(quotation_number='BG-DEMO-001'))
    payment = NS(report_number='PR', payment_type='advance', report_date=date.today(),
                 payment_date=date.today(), quotation_reference_date=None, items=[],
                 subtotal=100, vat_rate=8, vat_amount=8, shipping_fee=0, another_fee=0,
                 amount=32, advance_percentage=30, advance_amount=32, remaining_amount=76,
                 amount_in_words='w', work_completed_summary='', bank_account_info=[],
                 payment_method='', transaction_reference='', notes='')
    ctx = C.collect_payment_variables(payment, _cust(), NS(order_code='oc', title='ot'),
                                      company=_company(), contract=contract)
    assert ctx['quotation_number'] == 'BG-DEMO-001'
    assert ctx['total_amount']  # non-empty (alias of amount)
