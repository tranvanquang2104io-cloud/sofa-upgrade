"""Demo data for SofaFlow — one example of every state the product can be in.

Run it:

    DATABASE_URL="sqlite:///C:/Users/AlbertTran/Documents/sofa-upgrade/devdata.sqlite3" \
        python scripts/seed_demo.py --reset

It builds its own company (SOFADEMO) and never touches anything else, so an
existing dev database keeps whatever is already in it. `--reset` deletes and
rebuilds only that company.

Login: demo@sofa.test / demo1234

WHAT IT COVERS. Each block below is one case somebody has to be able to test,
and the comment says which. The point is not volume: it is that every branch a
screen can take has a row behind it — an order at each lifecycle stage, a
contract at 0% advance as well as 30%, a purchase order part-received, an
invoice that fails the 3-way match in each direction, a material with no cost,
a template that cannot be deleted because it has printed.

The wording is the trade's: bộ sofa góc, vải nhung, mút D40, khung gỗ sồi.
Prices are in đồng at roughly the right order of magnitude for Hanoi in 2026,
because a figure that reads wrong makes the whole screen read wrong.
"""
import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app                                    # noqa: E402
from app.config import db                                     # noqa: E402

COMPANY_CODE = 'SOFADEMO'
TODAY = dt.date(2026, 9, 20)


def d(days):
    """A date `days` before today, so the data reads as a real history."""
    return TODAY - dt.timedelta(days=days)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def money(subtotal, vat_rate=8, shipping=0, other=0):
    """Same arithmetic the app uses: VAT on goods only, fees added after."""
    vat = round(subtotal * vat_rate / 100)
    return {
        'subtotal': subtotal,
        'vat_rate': vat_rate,
        'vat_amount': vat,
        'shipping_fee': shipping,
        'another_fee': other,
        'total_amount': subtotal + vat + shipping + other,
    }


def item(name, unit, qty, price):
    return {'name': name, 'unit': unit, 'quantity': qty,
            'unit_price': price, 'total': qty * price}


def wipe(company_id):
    """Remove the demo company and everything hanging off it."""
    from app.models import Company, Customer, Document, Order, Quotation, Store, User
    from app.models.models import (
        Contract, DocumentTemplate, GoodsReceipt, GoodsReceiptLine,
        HandoverRecord, LifecycleStatus, MasterAgreement,
        MasterAgreementPriceLine, Material, MaterialCategory, MaterialStock,
        MaterialUnit, NormalizationRule, OrderConfirmation, PaymentReport,
        ProductionMaterialLine, ProductionPlan, ProductionPlanItem,
        PurchaseOrder, PurchaseOrderLine, PurchaseRequisition,
        PurchaseRequisitionLine, Supplier, SupplierInvoice, SupplierPayment,
        SupplierPaymentAllocation,
        WorkflowRule, WorkflowWaiver,
    )

    order_ids = [o.id for o in Order.query.filter_by(company_id=company_id)]
    plan_ids = [p.id for p in ProductionPlan.query.filter_by(company_id=company_id)]
    po_ids = [p.id for p in PurchaseOrder.query.filter_by(company_id=company_id)]
    pr_ids = [p.id for p in PurchaseRequisition.query.filter_by(company_id=company_id)]
    gr_ids = [g.id for g in GoodsReceipt.query.filter_by(company_id=company_id)]
    ma_ids = [m.id for m in MasterAgreement.query.filter_by(company_id=company_id)]

    def drop(model, **kw):
        model.query.filter_by(**kw).delete(synchronize_session=False)

    def drop_in(model, column, values):
        if values:
            model.query.filter(column.in_(values)).delete(synchronize_session=False)

    drop_in(ProductionMaterialLine, ProductionMaterialLine.plan_id, plan_ids)
    drop_in(ProductionPlanItem, ProductionPlanItem.plan_id, plan_ids)
    drop(ProductionPlan, company_id=company_id)
    drop_in(GoodsReceiptLine, GoodsReceiptLine.gr_id, gr_ids)
    drop(GoodsReceipt, company_id=company_id)
    # Allocations carry no company_id — only the two foreign keys — so they
    # have to be collected from their parents before those parents go, or a
    # second seed run leaves rows pointing at deleted invoices.
    pay_ids = [p.id for p in SupplierPayment.query.filter_by(company_id=company_id)]
    drop_in(SupplierPaymentAllocation, SupplierPaymentAllocation.payment_id,
            pay_ids)
    drop(SupplierInvoice, company_id=company_id)
    drop(SupplierPayment, company_id=company_id)
    drop_in(PurchaseOrderLine, PurchaseOrderLine.po_id, po_ids)
    drop(PurchaseOrder, company_id=company_id)
    drop_in(PurchaseRequisitionLine, PurchaseRequisitionLine.pr_id, pr_ids)
    drop(PurchaseRequisition, company_id=company_id)
    drop_in(MasterAgreementPriceLine, MasterAgreementPriceLine.agreement_id, ma_ids)
    drop_in(OrderConfirmation, OrderConfirmation.order_id, order_ids)
    drop(MasterAgreement, company_id=company_id)
    drop_in(HandoverRecord, HandoverRecord.order_id, order_ids)
    drop_in(PaymentReport, PaymentReport.order_id, order_ids)
    drop_in(Contract, Contract.order_id, order_ids)
    drop_in(Quotation, Quotation.order_id, order_ids)
    drop_in(LifecycleStatus, LifecycleStatus.order_id, order_ids)
    drop(Document, company_id=company_id)
    drop(Order, company_id=company_id)
    drop(MaterialStock, company_id=company_id)
    drop(Material, company_id=company_id)
    drop(MaterialCategory, company_id=company_id)
    drop(MaterialUnit, company_id=company_id)
    drop(Supplier, company_id=company_id)
    drop(Customer, company_id=company_id)
    drop(DocumentTemplate, company_id=company_id)
    drop(NormalizationRule, company_id=company_id)
    drop(WorkflowWaiver, company_id=company_id)
    drop(WorkflowRule, company_id=company_id)
    drop(User, company_id=company_id)
    drop(Store, company_id=company_id)
    Company.query.filter_by(id=company_id).delete(synchronize_session=False)
    db.session.commit()


# --------------------------------------------------------------------------
# the seed
# --------------------------------------------------------------------------

def seed():
    from app.models import Company, Customer, Document, Order, Quotation, Store, User
    from app.models.models import (
        Contract, DocumentTemplate, GoodsReceipt, GoodsReceiptLine,
        HandoverRecord, LifecycleStatus, MasterAgreement,
        MasterAgreementPriceLine, Material, MaterialCategory, MaterialStock,
        MaterialUnit, NormalizationRule, OrderConfirmation, PaymentReport,
        ProductionMaterialLine, ProductionPlan, ProductionPlanItem,
        PurchaseOrder, PurchaseOrderLine, PurchaseRequisition,
        PurchaseRequisitionLine, Supplier, SupplierInvoice, SupplierPayment,
        SupplierPaymentAllocation,
        WorkflowRule,
    )
    from app.services.agreement_service import product_key
    from app.services.workflow_service import WorkflowService

    company = Company(company_code=COMPANY_CODE, name='Nội Thất Sofa An Phát',
                      email='lienhe@sofaanphat.test', phone='0243 888 6688',
                      address='Số 128 Nguyễn Trãi, Thanh Xuân, Hà Nội',
                      tax_code='0108888888')
    db.session.add(company)
    db.session.flush()

    # --- two stores: the showroom and the workshop ------------------------
    showroom = Store(company_id=company.id, store_code='SR-HN',
                     name='Showroom Nguyễn Trãi', manager_name='Phạm Thu Hà',
                     phone='0243 888 6688',
                     address='128 Nguyễn Trãi', city='Hà Nội')
    workshop = Store(company_id=company.id, store_code='XUONG',
                     name='Xưởng sản xuất Hoài Đức', manager_name='Lê Văn Bình',
                     phone='0243 777 5544',
                     address='Cụm CN Trường An, Hoài Đức', city='Hà Nội')
    db.session.add_all([showroom, workshop])
    db.session.flush()

    # --- users: one of each role, plus a deactivated one ------------------
    admin = User(company_id=company.id, store_id=showroom.id, username='demo',
                 email='demo@sofa.test', full_name='Nguyễn Quốc Anh',
                 position='Giám đốc', role='company_admin', phone='0912 345 678')
    admin.set_password('demo1234')
    manager = User(company_id=company.id, store_id=showroom.id,
                   username='thuha', email='thuha@sofa.test',
                   full_name='Phạm Thu Hà', position='Quản lý showroom',
                   role='store_admin', phone='0987 654 321')
    manager.set_password('demo1234')
    sales = User(company_id=company.id, store_id=showroom.id, username='minh',
                 email='minh@sofa.test', full_name='Trần Văn Minh',
                 position='Nhân viên kinh doanh', role='user',
                 phone='0977 111 222')
    sales.set_password('demo1234')
    # CASE: a user who has left — the list must not offer them work
    left = User(company_id=company.id, store_id=showroom.id, username='cunhanvien',
                email='cu@sofa.test', full_name='Đỗ Thị Lan (đã nghỉ)',
                position='Nhân viên kinh doanh', role='user', is_active=False)
    left.set_password('demo1234')
    db.session.add_all([admin, manager, sales, left])

    WorkflowService.seed_defaults(company.id)

    # --- customers: individuals, companies, and one retired ---------------
    customers = {}
    for code, name, extra in [
        ('KH-001', 'Nguyễn Thị Hồng Nhung',
         dict(phone='0903 111 222', email='nhung@gmail.test',
              address='Số 45 ngõ 12 Trần Duy Hưng', city='Hà Nội')),
        ('KH-002', 'CÔNG TY TNHH NỘI THẤT MINH LONG',
         dict(phone='0243 555 7788', email='ketoan@minhlong.test',
              address='Lô B2 KCN Quang Minh, Mê Linh', city='Hà Nội',
              tax_code='0106543210', representative_name='Vũ Đức Long',
              representative_title='Giám đốc')),
        ('KH-003', 'Trần Văn Hùng',
         dict(phone='0912 888 999', address='Chung cư Royal City, R3-1502',
              city='Hà Nội')),
        ('KH-004', 'KHÁCH SẠN THÀNH ĐÔ',
         dict(phone='0243 222 3344', email='muahang@thanhdo.test',
              address='88 Hàng Bài, Hoàn Kiếm', city='Hà Nội',
              tax_code='0101112223', representative_name='Bùi Thị Mai',
              representative_title='Trưởng phòng Mua hàng')),
        # CASE: a customer who has closed down — deactivate is testable here
        ('KH-005', 'Cửa hàng Nội thất Sao Mai (đã đóng cửa)',
         dict(phone='0988 000 111', city='Hà Nội', is_active=False)),
    ]:
        record = Customer(company_id=company.id, store_id=showroom.id,
                          customer_code=code, name=name, **extra)
        db.session.add(record)
        customers[code] = record
    db.session.flush()

    # --- material catalogue ------------------------------------------------
    units = {}
    for name, abbr in [('Mét', 'm'), ('Mét vuông', 'm2'), ('Cái', 'cái'),
                       ('Bộ', 'bộ'), ('Kilôgam', 'kg'), ('Tấm', 'tấm')]:
        unit = MaterialUnit(company_id=company.id, name=name, abbreviation=abbr)
        db.session.add(unit)
        units[abbr] = unit

    categories = {}
    for name, order in [('Vải bọc', 1), ('Da', 2), ('Mút & đệm', 3),
                        ('Khung & chân', 4), ('Phụ kiện', 5)]:
        category = MaterialCategory(company_id=company.id, name=name,
                                    sort_order=order)
        db.session.add(category)
        categories[name] = category

    suppliers = {}
    for code, name, extra in [
        ('NCC-001', 'Công ty TNHH Vải Thiên Hà',
         dict(contact_person='Ngô Thị Vân', phone='0243 666 1122',
              email='banhang@vaithienha.test', tax_code='0104445556',
              address='KCN Phú Nghĩa, Chương Mỹ, Hà Nội',
              payment_terms='Thanh toán 30 ngày', lead_time_days=7, rating=5)),
        ('NCC-002', 'Da Bò Việt Thành',
         dict(contact_person='Hoàng Minh Tuấn', phone='0908 333 444',
              email='vietthanh.da@gmail.test', tax_code='0302223334',
              address='Quận 12, TP. Hồ Chí Minh',
              payment_terms='Trả trước 50%', lead_time_days=14, rating=4)),
        ('NCC-003', 'Mút xốp Hòa Bình',
         dict(contact_person='Đặng Văn Khoa', phone='0218 355 666',
              address='TP. Hòa Bình', lead_time_days=5, rating=4)),
        ('NCC-004', 'Gỗ & Khung Đông Anh',
         dict(contact_person='Lý Thị Thu', phone='0243 999 0011',
              address='Đông Anh, Hà Nội', lead_time_days=10, rating=3)),
    ]:
        supplier = Supplier(company_id=company.id, supplier_code=code,
                            name=name, **extra)
        db.session.add(supplier)
        suppliers[code] = supplier
    db.session.flush()

    materials = {}
    # (code, name, category, unit, supplier, price, min level, stock, avg_cost)
    for code, name, cat, unit, sup, price, minimum, stock, avg, extra in [
        ('VAI-NHUNG', 'Vải nhung Hàn Quốc màu ghi sáng', 'Vải bọc', 'm',
         'NCC-001', 285_000, 50, 180, 275_000,
         dict(color='Ghi sáng', spec_width_cm=140,
              spec_composition='100% Polyester',
              spec_durability_cycles=30000, spec_pattern='Trơn')),
        ('VAI-BO', 'Vải bố cao cấp màu be', 'Vải bọc', 'm', 'NCC-001',
         215_000, 40, 32, 210_000,
         dict(color='Be', spec_width_cm=145, spec_composition='Cotton pha')),
        ('DA-BO-A', 'Da bò thật Grade A nhập Ý', 'Da', 'm2', 'NCC-002',
         1_450_000, 20, 46, 1_420_000,
         dict(color='Nâu cognac', spec_thickness_mm=12,
              spec_country_of_origin='Ý', spec_certifications='LWG Gold')),
        ('DA-CN', 'Da công nghiệp Microfiber', 'Da', 'm2', 'NCC-002',
         320_000, 30, 12, 315_000,
         dict(color='Đen', spec_thickness_mm=10)),
        ('MUT-D40', 'Mút D40 cao su non', 'Mút & đệm', 'tấm', 'NCC-003',
         650_000, 15, 44, 640_000,
         dict(spec_density_kg_m3=40, spec_thickness_mm=100,
              spec_hardness='Trung bình')),
        ('MUT-D25', 'Mút D25 lót lưng', 'Mút & đệm', 'tấm', 'NCC-003',
         380_000, 10, 6, 372_000,
         dict(spec_density_kg_m3=25)),
        ('KHUNG-SOI', 'Khung gỗ sồi Nga đã sấy', 'Khung & chân', 'bộ',
         'NCC-004', 2_150_000, 5, 9, 2_100_000,
         dict(spec_country_of_origin='Nga')),
        ('CHAN-INOX', 'Chân inox mạ vàng cao 15cm', 'Khung & chân', 'cái',
         'NCC-004', 95_000, 40, 210, 92_000, dict(color='Vàng')),
        # CASE: no avg_cost yet — the job costing screen must flag it, not
        # silently treat this as free
        ('LOXO-TUI', 'Lò xo túi độc lập', 'Phụ kiện', 'cái', 'NCC-004',
         38_000, 100, 260, 0, {}),
        # CASE: stock at zero AND below minimum — purchase suggestions
        ('CHI-MAY', 'Chỉ may chuyên dụng 40/3', 'Phụ kiện', 'cái', 'NCC-001',
         45_000, 30, 0, 44_000, {}),
        # CASE: a material no longer bought
        ('VAI-CU', 'Vải nỉ cũ (ngừng kinh doanh)', 'Vải bọc', 'm', 'NCC-001',
         120_000, 0, 5, 118_000, dict(is_active=False)),
    ]:
        material = Material(company_id=company.id, material_code=code,
                            name=name, category_id=categories[cat].id,
                            unit_id=units[unit].id,
                            supplier_id=suppliers[sup].id, unit_price=price,
                            min_stock_level=minimum, avg_cost=avg, **extra)
        db.session.add(material)
        db.session.flush()
        materials[code] = material
        db.session.add(MaterialStock(company_id=company.id,
                                     material_id=material.id,
                                     store_id=workshop.id,
                                     current_quantity=stock))
    db.session.flush()

    # ----------------------------------------------------------------------
    # O2C — one order per lifecycle stage
    # ----------------------------------------------------------------------
    def make_order(code, title, customer, store=None, **lifecycle):
        order = Order(company_id=company.id, store_id=(store or showroom).id,
                      customer_id=customers[customer].id, order_code=code,
                      title=title)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id, **lifecycle))
        return order

    SOFA_L = item('Sofa góc chữ L bọc da bò thật Grade A, khung gỗ sồi',
                  'bộ', 1, 48_500_000)
    SOFA_3 = item('Sofa băng 3 chỗ bọc vải nhung Hàn Quốc', 'bộ', 1, 21_800_000)
    ARMCHAIR = item('Ghế thư giãn khung gỗ sồi, bọc vải bố', 'chiếc', 2, 6_400_000)
    POUF = item('Đôn sofa vuông 50x50cm', 'chiếc', 2, 1_850_000)
    REUPHOLSTER = item('Bọc lại sofa 3 chỗ (thay vải + mút)', 'bộ', 1, 7_200_000)

    # CASE 1: brand new, nothing issued yet
    make_order('DH-2609-001', 'Sofa phòng khách căn hộ Trần Duy Hưng', 'KH-001')

    # CASE 2: quotation issued, waiting for the customer
    order2 = make_order('DH-2609-002', 'Bộ sofa góc da bò - chị Nhung',
                        'KH-001', quotation_created=True)
    totals = money(SOFA_L['total'] + POUF['total'], 8, 500_000)
    db.session.add(Quotation(
        company_id=company.id, order_id=order2.id, quotation_number='BG-2609-002',
        quotation_date=d(18), validity_days=15, city='Hà Nội',
        items=[SOFA_L, POUF], payment_terms='Tạm ứng 30%, thanh toán nốt khi bàn giao',
        **totals))

    # CASE 3: quotation approved, contract not drafted yet
    order3 = make_order('DH-2609-003', 'Sofa băng 3 chỗ vải nhung', 'KH-003',
                        quotation_created=True, quotation_approved=True)
    db.session.add(Quotation(
        company_id=company.id, order_id=order3.id, quotation_number='BG-2609-003',
        quotation_date=d(16), validity_days=15, items=[SOFA_3],
        is_approved=True, **money(SOFA_3['total'])))

    # CASE 4: contract drafted but unsigned — the Unsigned badge
    order4 = make_order('DH-2609-004', 'Ghế thư giãn x2 - anh Hùng', 'KH-003',
                        quotation_created=True, quotation_approved=True,
                        contract_created=True)
    db.session.add(Quotation(
        company_id=company.id, order_id=order4.id, quotation_number='BG-2609-004',
        quotation_date=d(14), items=[ARMCHAIR], is_approved=True,
        **money(ARMCHAIR['total'])))
    t4 = money(ARMCHAIR['total'])
    db.session.add(Contract(
        company_id=company.id, order_id=order4.id, contract_number='HD-2609-004',
        contract_date=d(12), city='Hà Nội', items=[ARMCHAIR],
        contract_value=t4['total_amount'], subtotal=t4['subtotal'],
        vat_rate=8, vat_amount=t4['vat_amount'],
        advance_percentage=30,
        advance_amount=round(t4['total_amount'] * 0.3),
        contract_days_complete=21, warranty_months=24,
        delivery_terms='Giao và lắp đặt tại nhà khách hàng'))

    # CASE 5: signed, 30% advance due — handover must WAIT for it
    order5 = make_order('DH-2609-005', 'Sofa góc da bò - Khách sạn Thành Đô',
                        'KH-004', quotation_created=True,
                        quotation_approved=True, contract_created=True,
                        contract_signed=True)
    t5 = money(SOFA_L['total'] * 2, 8, 1_200_000)
    db.session.add(Contract(
        company_id=company.id, order_id=order5.id, contract_number='HD-2609-005',
        contract_date=d(10), signed_date=dt.datetime(2026, 9, 11),
        items=[dict(SOFA_L, quantity=2, total=SOFA_L['unit_price'] * 2)],
        contract_value=t5['total_amount'], subtotal=t5['subtotal'],
        vat_rate=8, vat_amount=t5['vat_amount'], shipping_fee=1_200_000,
        advance_percentage=30, advance_amount=round(t5['total_amount'] * 0.3),
        is_signed=True, contract_days_complete=30, warranty_months=24))

    # CASE 6: signed at 0% advance — the new contract-driven rule: handover
    # and payment are open immediately, nothing to skip
    order6 = make_order('DH-2609-006', 'Bọc lại sofa cũ - khách quen',
                        'KH-003', quotation_created=True,
                        quotation_approved=True, contract_created=True,
                        contract_signed=True)
    t6 = money(REUPHOLSTER['total'])
    db.session.add(Contract(
        company_id=company.id, order_id=order6.id, contract_number='HD-2609-006',
        contract_date=d(9), signed_date=dt.datetime(2026, 9, 12),
        items=[REUPHOLSTER], contract_value=t6['total_amount'],
        subtotal=t6['subtotal'], vat_rate=8, vat_amount=t6['vat_amount'],
        advance_percentage=0, advance_amount=0, is_signed=True,
        contract_days_complete=10, warranty_months=12,
        terms_and_conditions='Khách quen, hai bên thống nhất không thu tạm ứng.'))

    # CASE 7: advance received and confirmed — in production
    order7 = make_order('DH-2609-007', 'Sofa băng + đôn - chị Nhung đợt 2',
                        'KH-001', quotation_created=True,
                        quotation_approved=True, contract_created=True,
                        contract_signed=True, advance_paid=True)
    t7 = money(SOFA_3['total'] + POUF['total'])
    contract7 = Contract(
        company_id=company.id, order_id=order7.id, contract_number='HD-2609-007',
        contract_date=d(25), signed_date=dt.datetime(2026, 8, 27),
        items=[SOFA_3, POUF], contract_value=t7['total_amount'],
        subtotal=t7['subtotal'], vat_rate=8, vat_amount=t7['vat_amount'],
        advance_percentage=30, advance_amount=round(t7['total_amount'] * 0.3),
        is_signed=True, contract_days_complete=25, warranty_months=24)
    db.session.add(contract7)
    db.session.add(PaymentReport(
        company_id=company.id, order_id=order7.id, report_number='TU-2609-007',
        payment_type='advance', report_date=d(24), payment_date=d(24),
        amount=round(t7['total_amount'] * 0.3),
        advance_percentage=30, advance_amount=round(t7['total_amount'] * 0.3),
        remaining_amount=t7['total_amount'] - round(t7['total_amount'] * 0.3),
        payment_method='Chuyển khoản', transaction_reference='VCB.2608.7742',
        is_confirmed=True, confirmed_date=dt.datetime(2026, 8, 27)))

    # CASE 8: delivered, balance outstanding — and the handover carries a
    # PARTIALLY ACCEPTED line, which is the case the acceptance column exists for
    order8 = make_order('DH-2608-008', 'Sofa góc + ghế - Minh Long', 'KH-002',
                        quotation_created=True, quotation_approved=True,
                        contract_created=True, contract_signed=True,
                        advance_paid=True, handover_confirmed=True)
    t8 = money(SOFA_L['total'] + ARMCHAIR['total'], 8, 800_000)
    db.session.add(Contract(
        company_id=company.id, order_id=order8.id, contract_number='HD-2608-008',
        contract_date=d(40), signed_date=dt.datetime(2026, 8, 12),
        items=[SOFA_L, ARMCHAIR], contract_value=t8['total_amount'],
        subtotal=t8['subtotal'], vat_rate=8, vat_amount=t8['vat_amount'],
        shipping_fee=800_000, advance_percentage=40,
        advance_amount=round(t8['total_amount'] * 0.4), is_signed=True,
        contract_days_complete=30, warranty_months=24))
    db.session.add(PaymentReport(
        company_id=company.id, order_id=order8.id, report_number='TU-2608-008',
        payment_type='advance', report_date=d(39), payment_date=d(39),
        amount=round(t8['total_amount'] * 0.4),
        advance_percentage=40, advance_amount=round(t8['total_amount'] * 0.4),
        payment_method='Chuyển khoản', is_confirmed=True,
        confirmed_date=dt.datetime(2026, 8, 13)))
    db.session.add(HandoverRecord(
        company_id=company.id, order_id=order8.id, report_number='BB-2608-008',
        report_date=d(6), handover_date=d(6),
        handover_location='Lô B2 KCN Quang Minh, Mê Linh, Hà Nội',
        items=[
            dict(SOFA_L, delivered_qty=1, accepted_qty=1, status='accepted',
                 rejection_reason=''),
            dict(ARMCHAIR, delivered_qty=2, accepted_qty=1, status='partial',
                 rejection_reason='01 chiếc xước nhẹ mặt tựa, hẹn đổi trong 7 ngày'),
        ],
        subtotal=t8['subtotal'], vat_rate=8, vat_amount=t8['vat_amount'],
        shipping_fee=800_000, total_amount=t8['total_amount'],
        customer_representative='Vũ Đức Long',
        customer_representative_title='Giám đốc',
        company_representative='Phạm Thu Hà',
        company_representative_title='Quản lý showroom',
        product_condition='Hàng giao đúng mẫu, 01 ghế cần đổi',
        is_confirmed=True, confirmed_date=dt.datetime(2026, 9, 14)))

    # CASE 9: fully paid and completed
    order9 = make_order('DH-2607-009', 'Sofa da phòng giám đốc', 'KH-002',
                        quotation_created=True, quotation_approved=True,
                        contract_created=True, contract_signed=True,
                        advance_paid=True, handover_confirmed=True,
                        fully_paid=True, completed=True)
    t9 = money(SOFA_L['total'])
    db.session.add(Contract(
        company_id=company.id, order_id=order9.id, contract_number='HD-2607-009',
        contract_date=d(70), signed_date=dt.datetime(2026, 7, 14),
        items=[SOFA_L], contract_value=t9['total_amount'],
        subtotal=t9['subtotal'], vat_rate=8, vat_amount=t9['vat_amount'],
        advance_percentage=50, advance_amount=round(t9['total_amount'] * 0.5),
        is_signed=True, warranty_months=24))
    db.session.add(PaymentReport(
        company_id=company.id, order_id=order9.id, report_number='TU-2607-009',
        payment_type='advance', report_date=d(69), payment_date=d(69),
        amount=round(t9['total_amount'] * 0.5),
        advance_percentage=50, advance_amount=round(t9['total_amount'] * 0.5),
        is_confirmed=True, confirmed_date=dt.datetime(2026, 7, 15),
        payment_method='Chuyển khoản'))
    db.session.add(PaymentReport(
        company_id=company.id, order_id=order9.id, report_number='TT-2607-009',
        payment_type='final', report_date=d(35), payment_date=d(35),
        amount=t9['total_amount'] - round(t9['total_amount'] * 0.5),
        is_confirmed=True, confirmed_date=dt.datetime(2026, 8, 16),
        payment_method='Tiền mặt'))

    # CASE 10: cancelled after signing was refused — cancelled badge, and the
    # reason showing on screen
    order10 = make_order('DH-2609-010', 'Sofa vải bố - khách đổi ý', 'KH-001',
                         quotation_created=True, quotation_approved=True)
    order10.is_canceled = True
    order10.canceled_at = dt.datetime(2026, 9, 15)
    order10.canceled_reason = 'Khách chuyển sang mẫu khác, hẹn đặt lại sau Tết'
    db.session.add(Quotation(
        company_id=company.id, order_id=order10.id,
        quotation_number='BG-2609-010', quotation_date=d(20),
        items=[item('Sofa băng 2 chỗ vải bố', 'bộ', 1, 14_500_000)],
        is_approved=True, **money(14_500_000)))

    # CASE 11: a payment entered but NOT yet confirmed — it must not reduce
    # what the customer owes
    order11 = make_order('DH-2609-011', 'Đôn sofa lẻ - giao nhanh', 'KH-003',
                         quotation_created=True, quotation_approved=True,
                         contract_created=True, contract_signed=True)
    t11 = money(POUF['total'])
    db.session.add(Contract(
        company_id=company.id, order_id=order11.id,
        contract_number='HD-2609-011', contract_date=d(5),
        signed_date=dt.datetime(2026, 9, 16), items=[POUF],
        contract_value=t11['total_amount'], subtotal=t11['subtotal'],
        vat_rate=8, vat_amount=t11['vat_amount'], advance_percentage=0,
        advance_amount=0, is_signed=True))
    db.session.add(PaymentReport(
        company_id=company.id, order_id=order11.id,
        report_number='TT-2609-011', payment_type='final', report_date=d(1),
        payment_date=d(1), amount=t11['total_amount'],
        payment_method='Tiền mặt', is_confirmed=False,
        notes='Khách hẹn chuyển khoản chiều nay — chưa xác nhận.'))

    db.session.flush()

    # ----------------------------------------------------------------------
    # HĐNT + ĐƠN ĐẶT HÀNG — the second O2C route
    # ----------------------------------------------------------------------
    # CASE: an ACTIVE framework agreement with a revised price line
    agreement = MasterAgreement(
        company_id=company.id, customer_id=customers['KH-004'].id,
        agreement_number='HDNT-2026-001', signed_date=d(120),
        effective_from=d(120), effective_to=dt.date(2027, 5, 31),
        status=MasterAgreement.STATUS_ACTIVE, commitment_type='value',
        target_value=800_000_000,
        scope_description='Cung cấp sofa và ghế cho chuỗi phòng khách sạn',
        payment_terms='Thanh toán 30 ngày kể từ ngày nghiệm thu từng đợt',
        delivery_terms='Giao theo từng đợt, báo trước 7 ngày',
        penalty_pct=8, penalty_basis_note='Tính trên phần nghĩa vụ bị vi phạm',
        seller_representative='Nguyễn Quốc Anh',
        seller_representative_title='Giám đốc',
        buyer_representative='Bùi Thị Mai',
        buyer_representative_title='Trưởng phòng Mua hàng')
    db.session.add(agreement)
    db.session.flush()
    for name, unit, price, frm, to in [
        ('Sofa băng 3 chỗ bọc vải nhung Hàn Quốc', 'bộ', 19_500_000, d(120), d(40)),
        ('Sofa băng 3 chỗ bọc vải nhung Hàn Quốc', 'bộ', 20_400_000, d(39), None),
        ('Ghế thư giãn khung gỗ sồi, bọc vải bố', 'chiếc', 5_900_000, d(120), None),
        ('Đôn sofa vuông 50x50cm', 'chiếc', 1_650_000, d(120), None),
    ]:
        db.session.add(MasterAgreementPriceLine(
            agreement_id=agreement.id, product_key=product_key(name),
            product_name=name, unit=unit, agreed_unit_price=price,
            effective_from=frm, effective_to=to))

    # CASE: a CONFIRMED release order under that agreement
    order_ddh = make_order('DH-2609-012', 'Đợt giao tháng 9 - Thành Đô',
                           'KH-004')
    ddh_items = [
        item('Sofa băng 3 chỗ bọc vải nhung Hàn Quốc', 'bộ', 6, 20_400_000),
        item('Đôn sofa vuông 50x50cm', 'chiếc', 12, 1_650_000),
    ]
    t_ddh = money(sum(i['total'] for i in ddh_items), 8, 2_000_000)
    db.session.add(OrderConfirmation(
        company_id=company.id, order_id=order_ddh.id,
        master_agreement_id=agreement.id, confirmation_number='DDH-2609-001',
        confirmation_date=d(8), cited_agreement_number='HDNT-2026-001',
        cited_agreement_date=d(120), items=ddh_items,
        subtotal=t_ddh['subtotal'], vat_rate=8, vat_amount=t_ddh['vat_amount'],
        shipping_fee=2_000_000, total_amount=t_ddh['total_amount'],
        delivery_date=d(-12), delivery_address='88 Hàng Bài, Hoàn Kiếm, Hà Nội',
        status=OrderConfirmation.STATUS_CONFIRMED))

    # CASE: a DRAFT release order — not yet revenue
    order_ddh2 = make_order('DH-2609-013', 'Đợt giao tháng 10 - dự kiến',
                            'KH-004')
    ddh2_items = [item('Ghế thư giãn khung gỗ sồi, bọc vải bố', 'chiếc', 20,
                       5_900_000)]
    t_ddh2 = money(ddh2_items[0]['total'])
    db.session.add(OrderConfirmation(
        company_id=company.id, order_id=order_ddh2.id,
        master_agreement_id=agreement.id, confirmation_number='DDH-2610-002',
        confirmation_date=d(2), cited_agreement_number='HDNT-2026-001',
        cited_agreement_date=d(120), items=ddh2_items,
        subtotal=t_ddh2['subtotal'], vat_rate=8,
        vat_amount=t_ddh2['vat_amount'], total_amount=t_ddh2['total_amount'],
        status=OrderConfirmation.STATUS_DRAFT))

    # CASE: a DRAFT agreement and a TERMINATED one, for the status filters
    db.session.add(MasterAgreement(
        company_id=company.id, customer_id=customers['KH-002'].id,
        agreement_number='HDNT-2026-002', effective_from=d(3),
        status=MasterAgreement.STATUS_DRAFT,
        scope_description='Dự thảo khung cung cấp nội thất văn phòng'))
    db.session.add(MasterAgreement(
        company_id=company.id, customer_id=customers['KH-001'].id,
        agreement_number='HDNT-2025-009', effective_from=d(400),
        effective_to=d(30), status=MasterAgreement.STATUS_TERMINATED,
        scope_description='Khung cũ, đã chấm dứt',
        notes='Chấm dứt theo thỏa thuận hai bên.'))

    # ----------------------------------------------------------------------
    # PRODUCTION
    # ----------------------------------------------------------------------
    # CASE: a plan in progress with materials issued — job costing has numbers
    plan = ProductionPlan(company_id=company.id, order_id=order7.id,
                          contract_id=contract7.id, plan_number='KHSX-00001',
                          status=ProductionPlan.STATUS_IN_PROGRESS,
                          notes='Ưu tiên hoàn thiện trước 30/09')
    db.session.add(plan)
    db.session.flush()
    plan_item = ProductionPlanItem(plan_id=plan.id,
                                   source_name=SOFA_3['name'], quantity=1,
                                   unit='bộ')
    db.session.add(plan_item)
    db.session.flush()
    for code, required, issued in [('VAI-NHUNG', 18, 18), ('MUT-D40', 4, 4),
                                   ('KHUNG-SOI', 1, 1), ('CHAN-INOX', 6, 6),
                                   ('LOXO-TUI', 24, 24)]:
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=plan_item.id,
            material_id=materials[code].id, quantity_required=required,
            quantity_issued=issued,
            unit=materials[code].unit.abbreviation if materials[code].unit else ''))

    # CASE: a plan still a DRAFT — the only state whose material list can be
    # edited, and the only one that can be approved. Without it the owner
    # never meets the draft → approve → in-production sequence at all, and
    # every plan they open is locked: "chưa duyệt nhưng cũng không sửa được".
    plan_draft = ProductionPlan(
        company_id=company.id, order_id=order6.id,
        plan_number='KHSX-00004', status=ProductionPlan.STATUS_DRAFT,
        notes='Chưa chốt — còn chờ khách xác nhận màu vải.')
    db.session.add(plan_draft)
    db.session.flush()
    draft_item = ProductionPlanItem(plan_id=plan_draft.id,
                                    source_name=REUPHOLSTER['name'],
                                    quantity=1, unit='bộ')
    db.session.add(draft_item)
    db.session.flush()
    for code, required in [('VAI-NHUNG', 12), ('MUT-D40', 3)]:
        db.session.add(ProductionMaterialLine(
            plan_id=plan_draft.id, plan_item_id=draft_item.id,
            material_id=materials[code].id, quantity_required=required,
            quantity_issued=0,
            unit=materials[code].unit.abbreviation if materials[code].unit else ''))

    # CASE: a plan running LATE — the behind-schedule flag
    plan_late = ProductionPlan(
        company_id=company.id, order_id=order5.id,
        plan_number='KHSX-00002', status=ProductionPlan.STATUS_IN_PROGRESS,
        is_delayed=True,
        delay_reason='Da bò Grade A về chậm 10 ngày do vướng thủ tục nhập khẩu')
    db.session.add(plan_late)
    db.session.flush()
    late_item = ProductionPlanItem(plan_id=plan_late.id,
                                   source_name=SOFA_L['name'], quantity=2,
                                   unit='bộ')
    db.session.add(late_item)
    db.session.flush()
    # CASE: required but NOT issued — the shortage path, and one unpriced line
    for code, required, issued in [('DA-BO-A', 34, 0), ('MUT-D40', 8, 0),
                                   ('KHUNG-SOI', 2, 0), ('LOXO-TUI', 48, 0)]:
        db.session.add(ProductionMaterialLine(
            plan_id=plan_late.id, plan_item_id=late_item.id,
            material_id=materials[code].id, quantity_required=required,
            quantity_issued=issued, unit='m2' if code == 'DA-BO-A' else 'cái'))

    # CASE: a finished plan
    plan_done = ProductionPlan(company_id=company.id, order_id=order9.id,
                               plan_number='KHSX-00003',
                               status=ProductionPlan.STATUS_COMPLETED)
    db.session.add(plan_done)

    # ----------------------------------------------------------------------
    # P2P — requisition, order, receipt, invoice, payment
    # ----------------------------------------------------------------------
    # CASE: PR at each status
    pr_states = [
        ('PR-2609-0001', PurchaseRequisition.STATUS_DRAFT,
         'Bổ sung vải nhung cho đơn chị Nhung', [('VAI-NHUNG', 60)]),
        ('PR-2609-0002', PurchaseRequisition.STATUS_SUBMITTED,
         'Mút và lò xo cho lô sofa tháng 10', [('MUT-D40', 20), ('LOXO-TUI', 200)]),
        ('PR-2609-0003', PurchaseRequisition.STATUS_APPROVED,
         'Da bò Grade A cho Khách sạn Thành Đô', [('DA-BO-A', 40)]),
        ('PR-2608-0004', PurchaseRequisition.STATUS_CONVERTED,
         'Khung gỗ sồi đợt tháng 8', [('KHUNG-SOI', 12)]),
        ('PR-2609-0005', PurchaseRequisition.STATUS_CANCELED,
         'Đặt nhầm mã vải - đã hủy', [('VAI-BO', 30)]),
    ]
    for number, status, title, lines in pr_states:
        pr = PurchaseRequisition(company_id=company.id, store_id=workshop.id,
                                 pr_number=number, status=status,
                                 request_date=d(20), expected_date=d(-5),
                                 title=title)
        db.session.add(pr)
        db.session.flush()
        for code, qty in lines:
            db.session.add(PurchaseRequisitionLine(
                pr_id=pr.id, material_id=materials[code].id, quantity=qty,
                unit=materials[code].unit.abbreviation if materials[code].unit else ''))

    # CASE: PO at each status, including one PART received
    def make_po(number, supplier, status, lines, order_date, notes=None):
        po = PurchaseOrder(company_id=company.id, store_id=workshop.id,
                           supplier_id=suppliers[supplier].id, po_number=number,
                           status=status, order_date=order_date,
                           expected_date=order_date + dt.timedelta(days=10),
                           vat_rate=8, notes=notes)
        db.session.add(po)
        db.session.flush()
        subtotal = 0
        made = []
        for code, qty, price, received, invoiced in lines:
            line = PurchaseOrderLine(
                po_id=po.id, material_id=materials[code].id,
                quantity_ordered=qty, quantity_received=received,
                quantity_invoiced=invoiced,
                unit=materials[code].unit.abbreviation if materials[code].unit else '',
                unit_price=price, line_total=qty * price)
            db.session.add(line)
            made.append(line)
            subtotal += qty * price
        totals = money(subtotal)
        po.subtotal = totals['subtotal']
        po.vat_amount = totals['vat_amount']
        po.total_amount = totals['total_amount']
        db.session.flush()
        return po, made

    make_po('PO-2609-0001', 'NCC-001', PurchaseOrder.STATUS_DRAFT,
            [('VAI-NHUNG', 60, 285_000, 0, 0)], d(4),
            notes='Chờ duyệt giá trước khi gửi nhà cung cấp.')

    po_ordered, _ = make_po('PO-2609-0002', 'NCC-002',
                            PurchaseOrder.STATUS_ORDERED,
                            [('DA-BO-A', 40, 1_450_000, 0, 0)], d(12))

    # CASE: partially received — outstanding quantity on screen
    po_partial, partial_lines = make_po(
        'PO-2609-0003', 'NCC-003', PurchaseOrder.STATUS_PARTIAL,
        [('MUT-D40', 20, 650_000, 12, 12), ('MUT-D25', 15, 380_000, 0, 0)], d(14))

    # CASE: fully received, invoiced, part-paid
    po_done, done_lines = make_po(
        'PO-2608-0004', 'NCC-004', PurchaseOrder.STATUS_RECEIVED,
        [('KHUNG-SOI', 12, 2_100_000, 12, 12),
         ('CHAN-INOX', 120, 92_000, 120, 120)], d(35))

    make_po('PO-2609-0005', 'NCC-001', PurchaseOrder.STATUS_CANCELED,
            [('VAI-BO', 30, 215_000, 0, 0)], d(8),
            notes='Hủy do nhà cung cấp báo hết hàng.')

    # CASE: goods receipts — one partial, one full
    gr1 = GoodsReceipt(company_id=company.id, po_id=po_partial.id,
                       store_id=workshop.id, gr_number='GR-2609-0001',
                       receipt_date=d(6), is_posted=True,
                       notes='Nhận trước 12 tấm, còn lại giao đợt sau.')
    db.session.add(gr1)
    db.session.flush()
    db.session.add(GoodsReceiptLine(
        gr_id=gr1.id, po_line_id=partial_lines[0].id,
        material_id=materials['MUT-D40'].id, quantity_received=12, unit='tấm'))

    gr2 = GoodsReceipt(company_id=company.id, po_id=po_done.id,
                       store_id=workshop.id, gr_number='GR-2608-0002',
                       receipt_date=d(30), is_posted=True)
    db.session.add(gr2)
    db.session.flush()
    for line, code, qty, unit in [(done_lines[0], 'KHUNG-SOI', 12, 'bộ'),
                                  (done_lines[1], 'CHAN-INOX', 120, 'cái')]:
        db.session.add(GoodsReceiptLine(
            gr_id=gr2.id, po_line_id=line.id, material_id=materials[code].id,
            quantity_received=qty, unit=unit))

    # CASE: supplier invoices — clean match, over-invoiced, price variance
    inv_ok = SupplierInvoice(
        company_id=company.id, supplier_id=suppliers['NCC-004'].id,
        po_id=po_done.id, invoice_series='AA/26E', invoice_number='0001234',
        invoice_date=d(29), seller_tax_code='0105556667',
        subtotal=12 * 2_100_000 + 120 * 92_000, vat_rate=8,
        status=SupplierInvoice.STATUS_CONFIRMED,
        match_status=SupplierInvoice.MATCH_OK)
    inv_ok.vat_amount = round(inv_ok.subtotal * 0.08)
    inv_ok.total_amount = inv_ok.subtotal + inv_ok.vat_amount
    db.session.add(inv_ok)

    inv_over = SupplierInvoice(
        company_id=company.id, supplier_id=suppliers['NCC-003'].id,
        po_id=po_partial.id, invoice_series='AA/26E', invoice_number='0005678',
        invoice_date=d(5), subtotal=20 * 650_000, vat_rate=8,
        status=SupplierInvoice.STATUS_DRAFT,
        match_status='over_invoiced',
        match_notes='Hóa đơn 20 tấm nhưng mới nhận 12 tấm — chênh 8 tấm.')
    inv_over.vat_amount = round(inv_over.subtotal * 0.08)
    inv_over.total_amount = inv_over.subtotal + inv_over.vat_amount
    db.session.add(inv_over)

    inv_price = SupplierInvoice(
        company_id=company.id, supplier_id=suppliers['NCC-002'].id,
        po_id=po_ordered.id, invoice_series='AB/26E', invoice_number='0009999',
        invoice_date=d(3), subtotal=40 * 1_520_000, vat_rate=8,
        status=SupplierInvoice.STATUS_DRAFT, match_status='price_variance',
        match_notes='Đơn giá 1.520.000 so với đặt 1.450.000 — lệch 4,8%.')
    inv_price.vat_amount = round(inv_price.subtotal * 0.08)
    inv_price.total_amount = inv_price.subtotal + inv_price.vat_amount
    db.session.add(inv_price)
    db.session.flush()

    # CASE: a supplier payment, confirmed — leaves the invoice part-paid.
    # The allocation is the point of the case, not a detail: without it the
    # note says the payment settles 0001234 while the payable stays whole, and
    # payables/view.html can never reach the payment (it looks through
    # `alloc.payment`), so the cash-VAT warning cannot appear on the demo at
    # all. `method` uses the model's constant for the same reason — free text
    # leaves `is_cash` False whatever was meant.
    payment = SupplierPayment(
        company_id=company.id, supplier_id=suppliers['NCC-004'].id,
        payment_number='CHI-2609-0001', payment_date=d(20), amount=20_000_000,
        method=SupplierPayment.METHOD_TRANSFER,
        reference_number='VCB.2609.1188',
        status=SupplierPayment.STATUS_CONFIRMED,
        notes='Trả một phần hóa đơn 0001234.')
    db.session.add(payment)
    db.session.flush()
    db.session.add(SupplierPaymentAllocation(
        payment_id=payment.id, invoice_id=inv_ok.id,
        allocated_amount=20_000_000))

    # ----------------------------------------------------------------------
    # CONFIGURATION
    # ----------------------------------------------------------------------
    # CASE: standardization in both modes, so the matrix has ticks to look at
    db.session.add(NormalizationRule(
        company_id=company.id, entity_type='customer', field_name='name',
        primitives=['nfc', 'trim', 'collapse_whitespace', 'upper'],
        mode=NormalizationRule.MODE_AUTO, is_active=True))
    db.session.add(NormalizationRule(
        company_id=company.id, entity_type='customer', field_name='address',
        primitives=['nfc', 'trim', 'collapse_whitespace', 'title_case'],
        mode=NormalizationRule.MODE_CONFIRM, is_active=True))
    db.session.add(NormalizationRule(
        company_id=company.id, entity_type='material', field_name='name',
        primitives=['nfc', 'trim', 'collapse_whitespace', 'capitalize_first'],
        mode=NormalizationRule.MODE_AUTO, is_active=True))

    # CASE: a workflow rule the shop has customised away from the default
    rule = WorkflowRule.query.filter_by(
        company_id=company.id, action='payment.advance').first()
    if rule:
        rule.mode = WorkflowRule.MODE_WAIVABLE
        rule.message = 'Khách quen có thể bỏ qua tạm ứng — ghi rõ lý do.'

    # CASE: two templates, one of which has printed and so cannot be deleted
    used = DocumentTemplate(
        company_id=company.id, name='Mẫu hợp đồng chuẩn 2026',
        document_type='contract', template_file='templates/hop_dong_2026.docx',
        description='Mẫu đang dùng cho mọi hợp đồng bán lẻ.', is_active=True)
    unused = DocumentTemplate(
        company_id=company.id, name='Mẫu báo giá thử (chưa dùng)',
        document_type='quotation', template_file='templates/bao_gia_thu.docx',
        description='Bản nháp đang thử bố cục.', is_active=False)
    db.session.add_all([used, unused])
    db.session.flush()
    db.session.add(Document(
        company_id=company.id, order_id=order9.id, template_id=used.id,
        document_name='HD-2607-009', document_type='contract',
        document_format='pdf', file_path='documents/HD-2607-009.pdf',
        file_size=184_320, status='current', generated_at=dt.datetime(2026, 7, 14)))

    db.session.commit()
    return company


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reset', action='store_true',
                        help='delete the demo company first and rebuild it')
    args = parser.parse_args()

    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        from app.models import Company

        existing = Company.query.filter_by(company_code=COMPANY_CODE).first()
        if existing and not args.reset:
            print(f'Demo company {COMPANY_CODE} already exists. '
                  f'Use --reset to rebuild it.')
            return 1
        if existing:
            print(f'Removing the existing {COMPANY_CODE} data...')
            wipe(existing.id)

        seed()
        # The console here is cp1252 and cannot print Vietnamese; the company
        # name would raise AFTER the data had already been committed, which
        # reads as a failed seed when it succeeded.
        print('Seeded ' + COMPANY_CODE + '.')
        print('Login: demo@sofa.test / demo1234')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
