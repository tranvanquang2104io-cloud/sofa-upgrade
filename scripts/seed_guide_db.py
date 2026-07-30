# -*- coding: utf-8 -*-
"""Seed a rich demo SQLite DB for the user-guide screenshots.

Creates NGOCHAN with a login (email + password), taxonomy, a full demo order
(quotation→contract→plan→handover→payment) and a procurement demo (PR→PO→GR),
so every screen has realistic data for capture.

Usage: seed_guide_db.py <db_path> [email] [password]
"""
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB_PATH = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else 'guide.db')
EMAIL = sys.argv[2] if len(sys.argv) > 2 else 'huongdan@sofangochan.vn'
PASSWORD = sys.argv[3] if len(sys.argv) > 3 else 'Demo@1234'

os.environ['DATABASE_URL'] = 'sqlite:///' + DB_PATH.replace('\\', '/')
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('SECRET_KEY', 'guide-demo-secret')
os.environ['WTF_CSRF_ENABLED'] = 'False'  # keep Playwright form posts simple

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

from app import create_app
from app.config import db
app = create_app('development')
app.config['WTF_CSRF_ENABLED'] = False

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))

with app.app_context():
    db.create_all()
    from app.models.models import Company, Store, User, Supplier, Material, MaterialStock
    co = Company(company_code='NGOCHAN', name='CÔNG TY TNHH MTV TM-DV NGỌC HÂN',
                 email='sofangochan@gmail.com', phone='0832 777 718',
                 address='Ấp 3, Xã Tân Phước 1, Tỉnh Đồng Tháp', production_address='Xưởng sản xuất Ngọc Hân',
                 city='TP. Hồ Chí Minh', country='Việt Nam', tax_code='1201687458',
                 representative_name='Lê Thị Thắm', representative_title='Giám đốc', vat_rate=8,
                 bank_accounts=[{'bank_name': 'LPBank', 'account_number': '074736259190',
                                 'account_holder': 'CÔNG TY TNHH MTV TM-DV NGỌC HÂN'}])
    db.session.add(co); db.session.flush()
    store = Store(company_id=co.id, store_code='CH01', name='Cửa hàng chính Ngọc Hân',
                  city='TP. Hồ Chí Minh', address='Ấp 3, Xã Tân Phước 1, Tỉnh Đồng Tháp',
                  manager_name='Lê Thị Thắm', phone='0832 777 718')
    db.session.add(store); db.session.flush()
    u = User(company_id=co.id, store_id=store.id, username='ngochan', email=EMAIL,
             full_name='Quản trị Ngọc Hân', role='company_admin', position='Giám đốc')
    u.set_password(PASSWORD)
    db.session.add(u); db.session.commit()

    from seed_sofa_taxonomy import seed_taxonomy
    seed_taxonomy(co.id)

    # extra suppliers/materials so procurement + low-stock look real
    from app.models.models import MaterialCategory, MaterialUnit
    cat = MaterialCategory.query.filter_by(company_id=co.id, name='Vải bọc').first()
    unit = MaterialUnit.query.filter_by(company_id=co.id, name='m²').first()
    sup = Supplier(company_id=co.id, supplier_code='NCC-001', name='Công Ty TNHH Vải & Da Thành Phát',
                   contact_person='Trần Văn Phát', phone='0909 123 456', email='thanhphat@vaida.vn',
                   address='45 Tô Ký, Q.12, TP.HCM', tax_code='0312001122', payment_terms='NET30',
                   lead_time_days=7, rating=5)
    db.session.add(sup); db.session.flush()
    m1 = Material(company_id=co.id, supplier_id=sup.id, category_id=cat.id if cat else None,
                  unit_id=unit.id if unit else None, material_code='NVL-VAI-001',
                  name='Vải nỉ Hàn Quốc cao cấp', color='Xám tro', unit_price=Decimal('185000'),
                  min_stock_level=Decimal('50'), spec_composition='100% Polyester',
                  spec_country_of_origin='Hàn Quốc')
    m2 = Material(company_id=co.id, supplier_id=sup.id, unit_id=unit.id if unit else None,
                  material_code='NVL-MUT-001', name='Mút D40 (foam)', unit_price=Decimal('120000'),
                  min_stock_level=Decimal('30'))
    db.session.add_all([m1, m2]); db.session.flush()
    db.session.add(MaterialStock(company_id=co.id, material_id=m1.id, store_id=None, current_quantity=Decimal('20')))
    db.session.add(MaterialStock(company_id=co.id, material_id=m2.id, store_id=None, current_quantity=Decimal('200')))
    # a norm so a signed contract auto-derives a BOM
    from app.models.models import MaterialNorm
    db.session.add(MaterialNorm(company_id=co.id, product_key='sofa góc l khung gỗ sồi, bọc nỉ hàn quốc',
                                material_id=m1.id, quantity_per_unit=Decimal('22'), unit='m²'))
    db.session.commit()

    # full demo order (quotation→contract→plan→handover→payment)
    from seed_demo_order import seed_demo_order, _clean_demo
    _clean_demo(co.id)
    seed_demo_order(co.id, store.id)

    # procurement demo: PR → PO → partial GR
    from app.services.requisition_service import RequisitionService
    from app.services.procurement_service import ProcurementService
    rsvc, psvc = RequisitionService(), ProcurementService()
    pr = rsvc.create_pr(co.id, {'title': 'Bổ sung vải & mút cho đơn hàng mới', 'store_id': store.id},
                        [{'material_id': str(m1.id), 'quantity': 80, 'unit': 'm²'},
                         {'material_id': str(m2.id), 'quantity': 40, 'unit': 'Kg'}])
    rsvc.transition(pr, 'submit'); rsvc.transition(pr, 'approve')
    pos = rsvc.convert_to_pos(pr)
    if pos:
        po = pos[0]
        psvc.transition(po, 'submit')
        # partial receive: first line fully, second line half → PO becomes 'partial'
        qtys = {}
        for i, ln in enumerate(po.lines):
            qtys[str(ln.id)] = float(ln.quantity_ordered) if i == 0 else float(ln.quantity_ordered) / 2
        psvc.receive(po, qtys, store_id=None)

    print('Seeded guide DB at', DB_PATH)
    print('Login:', EMAIL, '/', PASSWORD)
