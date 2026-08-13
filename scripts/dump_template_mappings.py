# -*- coding: utf-8 -*-
"""Dump the exact Jinja2 context (variable → sample value) for each document type.

Runs the real DocumentVariableCollector against representative sample entities so the
emitted JSON is guaranteed to match what the docx generator actually feeds docxtpl —
including the extend01..extend10 flexfields. Output: tests/template_mappings/<type>.json

Usage:  venv/Scripts/python.exe scripts/dump_template_mappings.py
"""
import os
import sys
import json
from datetime import date
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils.template_engine import DocumentVariableCollector as DVC  # noqa: E402

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'tests', 'template_mappings')

# ── Sample building blocks ────────────────────────────────────────────────────
BANKS = [
    {'bank_name': 'Vietcombank - CN Đống Đa', 'account_number': '0123456789',
     'account_holder': 'CÔNG TY TNHH SOFA NGỌC HÂN'},
    {'bank_name': 'Techcombank - CN Hà Nội', 'account_number': '9988776655',
     'account_holder': 'CÔNG TY TNHH SOFA NGỌC HÂN'},
]

COMPANY = NS(
    name='CÔNG TY TNHH SOFA NGỌC HÂN', address='Số 1, Đường ABC, Hà Nội',
    production_address='Xưởng SX, KCN XYZ, Hà Nội', phone='0900000000',
    email='info@sofangochan.vn', tax_code='0101234567',
    business_registration_number='0101234567', website='sofangochan.com',
    representative_name='Nguyễn Văn A', representative_title='Giám đốc',
    vat_rate=8, bank_accounts=BANKS,
)

STORE = NS(city='Hà Nội')

CUSTOMER = NS(
    name='Trần Thị B', customer_code='KH-0001', phone='0911111111',
    email='khachhang@example.com', address='12 Phố Huế, Hai Bà Trưng, Hà Nội',
    city='Hà Nội', postal_code='100000', tax_code='0209876543',
    representative_name='Trần Thị B', representative_title='Chủ hộ',
)

ORDER = NS(order_code='DH-2026-001', title='Bộ sofa góc L + 2 ghế đơn',
           description='Gia công, bọc lại bộ sofa da thật theo mẫu.', store=STORE)

EXT = {f'extend{i:02d}': f'[giá trị extend{i:02d}]' for i in range(1, 11)}

QUOT_ITEMS = [
    {'name': 'Sofa góc chữ L', 'unit': 'Bộ', 'quantity': 1, 'unit_price': 15000000,
     'total': 15000000, 'notes': 'Da Microfiber', 'image_path': ''},
    {'name': 'Ghế đơn', 'unit': 'Cái', 'quantity': 2, 'unit_price': 3000000,
     'total': 6000000, 'notes': '', 'image_path': ''},
]

HANDOVER_ITEMS = [
    {'name': 'Sofa góc chữ L', 'unit': 'Bộ', 'quantity': 1, 'delivered_qty': 1,
     'accepted_qty': 1, 'accepted': True, 'rejection_reason': '', 'notes': ''},
    {'name': 'Ghế đơn', 'unit': 'Cái', 'quantity': 2, 'delivered_qty': 2,
     'accepted_qty': 2, 'accepted': True, 'rejection_reason': '', 'notes': ''},
]


def _quotation():
    return NS(quotation_number='BG-2026-001', quotation_date=date(2026, 2, 1),
              validity_days=30, city='Hà Nội', items=QUOT_ITEMS,
              subtotal=21000000, vat_rate=8, vat_amount=1680000, shipping_fee=500000,
              another_fee=0, total_amount=23180000, amount_in_words='Hai ba triệu ...',
              payment_terms='50% tạm ứng, 50% khi bàn giao', notes='Giao trong 20 ngày.',
              **EXT)


def _contract(quotation):
    return NS(contract_number='HĐ-2026-001', contract_date=date(2026, 2, 3),
              contract_start_date=date(2026, 2, 5), selected_bank_index=0,
              contract_value=23180000, amount_in_words='Hai ba triệu ...', city='Hà Nội',
              contract_days_complete=20, num_date_notice_cancel=7, items=QUOT_ITEMS,
              subtotal=21000000, vat_rate=8, vat_amount=1680000, shipping_fee=500000,
              another_fee=0, advance_percentage=50, advance_amount=11590000,
              warranty_months=12, delivery_terms='Giao tại nhà khách hàng',
              terms_and_conditions='Các điều khoản chung ...', notes='',
              quotation=quotation, **EXT)


def _delivery():
    return NS(report_number='BBBG-2026-001', report_date=date(2026, 2, 25),
              handover_date=date(2026, 2, 25), handover_location='Nhà khách hàng',
              start_time='09:00', end_time='10:30', copies_count=2, items=HANDOVER_ITEMS,
              subtotal=21000000, vat_rate=8, vat_amount=1680000, shipping_fee=500000,
              another_fee=0, total_amount=23180000,
              company_representative='Nguyễn Văn A', company_representative_title='Giám đốc',
              customer_representative='Trần Thị B', customer_representative_title='Chủ hộ',
              product_condition='Sản phẩm nguyên vẹn, đúng mẫu', notes='', **EXT)


def _payment(payment_type):
    return NS(report_number=f'TT-2026-001-{payment_type}', payment_type=payment_type,
              report_date=date(2026, 2, 26), payment_date=date(2026, 2, 26),
              quotation_reference_date=date(2026, 2, 1), items=QUOT_ITEMS,
              subtotal=21000000, vat_rate=8, vat_amount=1680000, shipping_fee=500000,
              another_fee=0, amount=23180000, advance_percentage=50,
              advance_amount=11590000, remaining_amount=11590000,
              amount_in_words='Mười một triệu ...',
              work_completed_summary='Hoàn thành 100% khối lượng',
              bank_account_info=BANKS, payment_method='Chuyển khoản',
              transaction_reference='FT2026xxxx', notes='', **EXT)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    quotation = _quotation()
    contract = _contract(quotation)
    mappings = {
        'quotation': DVC.collect_quotation_variables(quotation, CUSTOMER, ORDER, company=COMPANY),
        'contract': DVC.collect_contract_variables(contract, quotation, CUSTOMER, ORDER, company=COMPANY),
        'delivery': DVC.collect_delivery_variables(_delivery(), CUSTOMER, ORDER, company=COMPANY),
        'payment_advance': DVC.collect_payment_variables(_payment('advance'), CUSTOMER, ORDER, company=COMPANY, contract=contract),
        'payment_final': DVC.collect_payment_variables(_payment('final'), CUSTOMER, ORDER, company=COMPANY, contract=contract),
    }

    def _safe(v):
        if isinstance(v, dict):
            return {k: _safe(x) for k, x in v.items()}
        if isinstance(v, list):
            return [_safe(x) for x in v]
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        return str(v)

    for name, ctx in mappings.items():
        path = os.path.join(OUT_DIR, f'{name}.json')
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(_safe(ctx), fh, ensure_ascii=False, indent=2, sort_keys=True)
        print(f'wrote {path}  ({len(ctx)} variables)')


if __name__ == '__main__':
    main()
