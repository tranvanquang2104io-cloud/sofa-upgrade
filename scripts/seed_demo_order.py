# -*- coding: utf-8 -*-
"""Seed ONE complete demo order (+ one supplier/material/customer) for a company.

Purpose: a full end-to-end example for handover/training — every document
(quotation, contract, handover, advance & final payment) and the production plan
are present and printable. The order is flagged CANCELED with a clear reason so
it never counts toward real accounting/revenue.

Usage:
    venv/Scripts/python.exe scripts/seed_demo_order.py NGOCHAN
Idempotent: re-running removes the previous demo entities (by code) first.
Requires the company to already have a store, a user, and the seeded
material Categories + Units (scripts/seed_sofa_taxonomy.py).
"""
import os
import sys
from datetime import date, timedelta, datetime
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Codes used so the demo is idempotent and easy to spot.
SUP_CODE  = 'NCC-DEMO'
MAT_CODE  = 'VT-DEMO'
CUST_CODE = 'KH-DEMO'
ORD_CODE  = 'DH-DEMO'
QUO_NO    = 'BG-DEMO-2026'
CON_NO    = 'HD-DEMO-2026'
HAN_NO    = 'BBBG-DEMO-2026'
PAY_ADV   = 'TT-DEMO-TU'
PAY_FIN   = 'TT-DEMO-CK'

_ONES = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']


def _read_triple(n, full):
    """Read a 0..999 group. `full` = read the hundreds place even when 0
    (used for non-leading groups, e.g. 'không trăm lẻ năm')."""
    h, d, u = n // 100, (n % 100) // 10, n % 10
    out = []
    if h or full:
        out.append(_ONES[h] + ' trăm')
    if d == 0:
        if u != 0:
            out.append(('lẻ ' + _ONES[u]) if (h or full) else _ONES[u])
    elif d == 1:
        out.append('mười')
        if u == 1:   out.append('một')
        elif u == 5: out.append('lăm')
        elif u != 0: out.append(_ONES[u])
    else:
        out.append(_ONES[d] + ' mươi')
        if u == 1:   out.append('mốt')
        elif u == 5: out.append('lăm')
        elif u != 0: out.append(_ONES[u])
    return ' '.join(out)


def doc_so(n):
    """Đọc số tiền (nguyên, đồng) sang chữ tiếng Việt."""
    n = int(round(n))
    if n == 0:
        return 'Không đồng'
    units = ['', ' nghìn', ' triệu', ' tỷ']
    groups = []
    while n > 0:
        groups.append(n % 1000); n //= 1000
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        if groups[i] == 0:
            continue
        parts.append(_read_triple(groups[i], full=(i != len(groups) - 1)) + units[i])
    s = ' '.join(parts).strip()
    return s[0].upper() + s[1:] + ' đồng'


def _clean_demo(company_id):
    from app.config import db
    from app.models.models import (Order, Customer, Material, MaterialStock,
                                   Supplier, MaterialNorm, ProductionPlan,
                                   ProductionPlanItem, ProductionMaterialLine)
    o = Order.query.filter_by(company_id=company_id, order_code=ORD_CODE).first()
    if o:
        plan = ProductionPlan.query.filter_by(order_id=o.id).first()
        if plan:
            ProductionMaterialLine.query.filter_by(plan_id=plan.id).delete(synchronize_session=False)
            ProductionPlanItem.query.filter_by(plan_id=plan.id).delete(synchronize_session=False)
            db.session.delete(plan)
        db.session.delete(o)          # cascades quotations/contracts/handover/payment/lifecycle/docs
    for m in Material.query.filter_by(company_id=company_id, material_code=MAT_CODE).all():
        MaterialNorm.query.filter_by(material_id=m.id).delete(synchronize_session=False)
        MaterialStock.query.filter_by(material_id=m.id).delete(synchronize_session=False)
        db.session.delete(m)
    for s in Supplier.query.filter_by(company_id=company_id, supplier_code=SUP_CODE).all():
        db.session.delete(s)
    for c in Customer.query.filter_by(company_id=company_id, customer_code=CUST_CODE).all():
        db.session.delete(c)
    db.session.commit()


def seed_demo_order(company_id, store_id):
    from app.config import db
    from app.models.models import (Company, Supplier, Material, MaterialStock,
                                   Customer, MaterialCategory, MaterialUnit,
                                   MaterialNorm, Order, LifecycleStatus, ProductionPlan)
    from app.services.services import (QuotationService, ContractService,
                                       HandoverRecordService, PaymentReportService,
                                       ProductionPlanService)
    company = Company.query.get(company_id)
    vat_rate = float(getattr(company, 'vat_rate', 8) or 8)
    cat = (MaterialCategory.query.filter_by(company_id=company_id, name='Vải bọc').first()
           or MaterialCategory.query.filter_by(company_id=company_id).first())
    unit_m2 = (MaterialUnit.query.filter_by(company_id=company_id, name='m²').first()
               or MaterialUnit.query.filter_by(company_id=company_id).first())

    # 1) Supplier
    sup = Supplier(company_id=company_id, supplier_code=SUP_CODE,
                   name='Công Ty TNHH Vải & Da Thành Phát', contact_person='Trần Văn Phát',
                   phone='0909 123 456', email='thanhphat@vaida.vn',
                   address='45 Đường Tô Ký, Quận 12, TP. Hồ Chí Minh', tax_code='0312001122',
                   payment_terms='NET30', lead_time_days=7, rating=5,
                   notes='Nhà cung cấp vải bọc & da cao cấp (demo).')
    db.session.add(sup); db.session.flush()

    # 2) Material (full technical specs) + stock
    mat = Material(company_id=company_id, supplier_id=sup.id,
                   category_id=cat.id if cat else None,
                   unit_id=unit_m2.id if unit_m2 else None,
                   material_code=MAT_CODE, name='Vải nỉ Hàn Quốc cao cấp (demo)',
                   description='Vải bọc sofa nỉ Hàn Quốc, mềm, bền màu.',
                   color='Xám tro', unit_price=Decimal('185000'), supplier_sku='NI-HQ-GREY',
                   min_stock_level=Decimal('50'),
                   spec_width_cm=Decimal('280'), spec_thickness_mm=Decimal('2.5'),
                   spec_roll_length_m=Decimal('30'), spec_weight_per_unit=Decimal('340'),
                   spec_weight_unit='g/m²', spec_composition='100% Polyester',
                   spec_pattern='Trơn', spec_finish='Nhung',
                   spec_durability_cycles=40000, spec_hardness='Grade A',
                   spec_fire_resistance='BS5852', spec_water_resistance='Kháng nước',
                   spec_uv_resistance='Trung bình', spec_country_of_origin='Hàn Quốc',
                   spec_certifications='OEKO-TEX Standard 100')
    db.session.add(mat); db.session.flush()
    db.session.add(MaterialStock(company_id=company_id, material_id=mat.id,
                                 store_id=None, current_quantity=Decimal('200')))

    # 3) Customer
    cust = Customer(company_id=company_id, store_id=store_id, customer_code=CUST_CODE,
                    name='Công Ty TNHH Nội Thất An Gia', phone='028 3999 8888',
                    email='contact@angia-noithat.vn',
                    address='128 Đường Nguyễn Văn Linh, Quận 7, TP. Hồ Chí Minh',
                    city='TP. Hồ Chí Minh', country='Việt Nam', tax_code='0316888999',
                    representative_name='Nguyễn Thị An', representative_title='Giám Đốc',
                    notes='Khách hàng mẫu dùng để demo/hướng dẫn.')
    db.session.add(cust); db.session.flush()

    # 4) Order
    order = Order(company_id=company_id, store_id=store_id, customer_id=cust.id,
                  order_code=ORD_CODE,
                  title='[DEMO] Bộ Sofa Góc L Cao Cấp Bọc Nỉ 3+2',
                  description=('Gia công bộ sofa góc L khung gỗ sồi tự nhiên, bọc vải nỉ Hàn Quốc, '
                               'đệm mút D40 kết hợp lò xo túi; kèm 02 ghế thư giãn cùng bộ.'))
    db.session.add(order); db.session.flush()
    db.session.add(LifecycleStatus(order_id=order.id))
    db.session.commit()

    # 5) Material norm so the production plan auto-derives its BOM
    db.session.add(MaterialNorm(company_id=company_id,
                                product_key='sofa góc l khung gỗ sồi, bọc nỉ hàn quốc',
                                material_id=mat.id, quantity_per_unit=Decimal('22'), unit='m²'))
    db.session.commit()

    # Line items (subtotal → VAT → total)
    items = [
        {'name': 'Sofa góc L khung gỗ sồi, bọc nỉ Hàn Quốc', 'unit': 'Bộ',
         'quantity': 1, 'unit_price': 32000000, 'total': 32000000},
        {'name': 'Ghế thư giãn (armchair) cùng bộ', 'unit': 'Cái',
         'quantity': 2, 'unit_price': 6500000, 'total': 13000000},
    ]
    subtotal = sum(i['total'] for i in items)
    vat_amount = round(subtotal * vat_rate / 100)
    total = subtotal + vat_amount
    today = date.today()

    # 6) Quotation → approve
    qsvc = QuotationService()
    quo = qsvc.create_quotation(order_id=order.id, quotation_number=QUO_NO,
                                quotation_date=today, items=items, total_amount=total,
                                subtotal=subtotal, vat_rate=vat_rate, vat_amount=vat_amount,
                                validity_days=30, city='TP. Hồ Chí Minh',
                                payment_terms='Tạm ứng 30% khi ký hợp đồng, 70% khi bàn giao.',
                                amount_in_words=doc_so(total), company_id=company_id)
    qsvc.approve_quotation(quo.id, order.id)

    # 7) Contract → sign (auto-creates production plan)
    csvc = ContractService()
    con = csvc.create_contract(order_id=order.id, quotation_id=quo.id, contract_number=CON_NO,
                               contract_date=today, contract_value=total,
                               terms_and_conditions='Bảo hành khung gỗ 24 tháng, vải & mút 12 tháng.')
    advance_amount = round(total * 30 / 100)
    con.subtotal = subtotal; con.vat_rate = vat_rate; con.vat_amount = vat_amount
    con.advance_percentage = 30; con.advance_amount = advance_amount
    con.amount_in_words = doc_so(total); con.city = 'TP. Hồ Chí Minh'
    con.contract_start_date = today; con.contract_days_complete = 21
    con.num_date_notice_cancel = 7; con.warranty_months = 24
    con.delivery_terms = 'Giao và lắp đặt tận nơi trong nội thành TP. HCM.'
    con.selected_bank_index = 0
    db.session.commit()
    csvc.mark_signed(con.id, order.id)

    # 8) Advance payment → confirm
    psvc = PaymentReportService()
    adv = psvc.create_payment_report(order_id=order.id, report_number=PAY_ADV,
                                     payment_type='advance', report_date=today, payment_date=today,
                                     amount=advance_amount, items=items, subtotal=subtotal,
                                     vat_rate=vat_rate, vat_amount=vat_amount,
                                     advance_percentage=30, advance_amount=advance_amount,
                                     remaining_amount=total - advance_amount,
                                     amount_in_words=doc_so(advance_amount),
                                     work_completed_summary='Tạm ứng khi ký hợp đồng.',
                                     quotation_reference_date=today,
                                     payment_method='Chuyển khoản')
    psvc.mark_confirmed(adv.id, order.id)

    # 9) Handover → confirm
    hsvc = HandoverRecordService()
    han_items = [dict(i, delivered_qty=i['quantity'], accepted_qty=i['quantity'], accepted=True)
                 for i in items]
    han = hsvc.create_handover_record(order_id=order.id, report_number=HAN_NO,
                                      report_date=today, handover_date=today,
                                      handover_location=cust.address, start_time='08:30', end_time='10:00',
                                      customer_representative=cust.representative_name,
                                      customer_representative_title=cust.representative_title,
                                      company_representative=getattr(company, 'representative_name', '') or 'Đại diện công ty',
                                      company_representative_title=getattr(company, 'representative_title', '') or 'Giám đốc',
                                      product_condition='Sản phẩm đúng mẫu, đường may sắc nét, không lỗi.',
                                      items=han_items, subtotal=subtotal, vat_rate=vat_rate,
                                      vat_amount=vat_amount, total_amount=total,
                                      notes='Khách hàng nghiệm thu và đồng ý nhận sản phẩm.')
    hsvc.confirm_handover(han.id, order.id)

    # 10) Final payment → CREATE only (leave unconfirmed so order isn't "completed")
    final_amount = total - advance_amount
    psvc.create_payment_report(order_id=order.id, report_number=PAY_FIN,
                               payment_type='final', report_date=today, payment_date=today,
                               amount=final_amount, items=items, subtotal=subtotal,
                               vat_rate=vat_rate, vat_amount=vat_amount,
                               advance_percentage=30, advance_amount=advance_amount,
                               remaining_amount=final_amount, amount_in_words=doc_so(final_amount),
                               work_completed_summary='Thanh toán phần còn lại sau bàn giao.',
                               quotation_reference_date=today, payment_method='Chuyển khoản')

    # 11) Production plan: chốt (approve) + cấp phát vật tư (→ processing) for a lively demo
    plan = ProductionPlan.query.filter_by(order_id=order.id).first()
    if plan:
        ppsvc = ProductionPlanService()
        try:
            ppsvc.transition(plan, 'approve')
            ppsvc.issue_materials(plan)     # deducts stock, → processing
        except Exception:
            db.session.rollback()

    # 12) Flag the whole order as canceled DEMO so accounting ignores it
    order = Order.query.get(order.id)
    order.is_canceled = True
    order.canceled_at = datetime.utcnow()
    order.canceled_reason = 'Đơn DEMO — dữ liệu mẫu để hướng dẫn sử dụng, KHÔNG tính doanh thu.'
    db.session.commit()
    return order


def main():
    from app import create_app
    from app.models.models import Company, Store, User
    code = sys.argv[1] if len(sys.argv) > 1 else 'NGOCHAN'
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        co = Company.query.filter_by(company_code=code).first()
        if not co:
            print(f'Company {code} not found'); sys.exit(1)
        store = Store.query.filter_by(company_id=co.id).first()
        if not store:
            print(f'Company {code} has no store'); sys.exit(1)
        _clean_demo(co.id)
        order = seed_demo_order(co.id, store.id)
        print(f'Seeded demo order {order.order_code} for {code} (flagged canceled/DEMO).')


if __name__ == '__main__':
    main()
