"""
Sample data script — creates a full demo environment for testing.

Structure created:
  Company : SOFAFLOW DEMO (DEMO01)
  │
  ├── company_admin : admin / Admin@123
  │
  ├── Store CH001 — "Chi Nhánh Quận 1"
  │     ├── store_admin : admin_q1 / Admin@123
  │     ├── user        : nv01_q1 / User@123
  │     └── user        : nv02_q1 / User@123
  │
  └── Store CH002 — "Chi Nhánh Quận 7"
        ├── store_admin : admin_q7 / Admin@123
        ├── user        : nv01_q7 / User@123
        └── user        : nv02_q7 / User@123

  Each store also gets 2 customers and 1 demo order.

Run with:  python create_sample_data.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import date, datetime
from app import create_app
from app.config.database import db
from app.models.models import (
    Company, Store, User, Customer, Order, LifecycleStatus, Quotation
)

app = create_app()

COMPANY_CODE = 'DEMO01'
ADMIN_PWD    = 'Admin@123'
USER_PWD     = 'User@123'


def clean_existing():
    """Remove existing demo company (if re-running)."""
    c = Company.query.filter_by(company_code=COMPANY_CODE).first()
    if c:
        db.session.delete(c)
        db.session.commit()
        print(f"[~] Removed existing company {COMPANY_CODE}")


def create_company():
    company = Company(
        company_code         = COMPANY_CODE,
        name                 = 'SOFAFLOW DEMO CO., LTD',
        email                = 'demo@sofaflow.vn',
        phone                = '028-1234-5678',
        address              = '123 Đường Lê Lợi, Phường Bến Nghé, Quận 1',
        production_address   = '456 Đường Cộng Hòa, Phường 13, Quận Tân Bình',
        city                 = 'TP. Hồ Chí Minh',
        country              = 'Việt Nam',
        tax_code             = '0312345678',
        representative_name  = 'Nguyễn Văn Hùng',
        representative_title = 'Giám Đốc',
        vat_rate             = 10.00,
        bank_accounts        = [
            {
                'bank_name':      'Vietcombank',
                'account_number': '0071001234567',
                'account_holder': 'SOFAFLOW DEMO CO., LTD',
            },
            {
                'bank_name':      'Techcombank',
                'account_number': '19037654321012',
                'account_holder': 'SOFAFLOW DEMO CO., LTD',
            },
        ],
    )
    db.session.add(company)
    db.session.flush()
    print(f"[+] Company: {company.name} ({company.company_code})")
    return company


def create_stores(company):
    s1 = Store(
        company_id   = company.id,
        store_code   = 'CH001',
        name         = 'Chi Nhánh Quận 1',
        manager_name = 'Trần Thị Hoa',
        phone        = '028-3812-0001',
        address      = '15 Nguyễn Huệ, Phường Bến Nghé, Quận 1',
        city         = 'TP. Hồ Chí Minh',
    )
    s2 = Store(
        company_id   = company.id,
        store_code   = 'CH002',
        name         = 'Chi Nhánh Quận 7',
        manager_name = 'Lê Minh Tuấn',
        phone        = '028-3412-0002',
        address      = '88 Nguyễn Thị Thập, Phường Tân Phú, Quận 7',
        city         = 'TP. Hồ Chí Minh',
    )
    db.session.add_all([s1, s2])
    db.session.flush()
    print(f"[+] Store: {s1.name} ({s1.store_code})")
    print(f"[+] Store: {s2.name} ({s2.store_code})")
    return s1, s2


def add_user(company_id, store_id, username, full_name, email, role, phone=None, position=None, password=None):
    u = User(
        company_id = company_id,
        store_id   = store_id,
        username   = username,
        full_name  = full_name,
        email      = email,
        role       = role,
        phone      = phone,
        position   = position,
    )
    u.set_password(password or (ADMIN_PWD if 'admin' in role else USER_PWD))
    db.session.add(u)
    return u


def create_users(company, store1, store2):
    # Company admin (no store)
    ca = add_user(company.id, None, 'admin',
                  full_name='Nguyễn Quản Trị', email='admin@sofaflow.vn',
                  role='company_admin', position='Giám Đốc', password=ADMIN_PWD)

    # Store 1 users
    sa1 = add_user(company.id, store1.id, 'admin_q1',
                   full_name='Trần Thị Hoa', email='hoa@sofaflow.vn',
                   role='store_admin', position='Trưởng Chi Nhánh', password=ADMIN_PWD)
    u1a = add_user(company.id, store1.id, 'nv01_q1',
                   full_name='Phạm Văn Bình', email='binh@sofaflow.vn',
                   role='user', position='Nhân Viên Kinh Doanh', password=USER_PWD)
    u1b = add_user(company.id, store1.id, 'nv02_q1',
                   full_name='Lê Thị Cúc', email='cuc@sofaflow.vn',
                   role='user', position='Nhân Viên Hỗ Trợ', password=USER_PWD)

    # Store 2 users
    sa2 = add_user(company.id, store2.id, 'admin_q7',
                   full_name='Lê Minh Tuấn', email='tuan@sofaflow.vn',
                   role='store_admin', position='Trưởng Chi Nhánh', password=ADMIN_PWD)
    u2a = add_user(company.id, store2.id, 'nv01_q7',
                   full_name='Hoàng Văn Dũng', email='dung@sofaflow.vn',
                   role='user', position='Nhân Viên Kinh Doanh', password=USER_PWD)
    u2b = add_user(company.id, store2.id, 'nv02_q7',
                   full_name='Nguyễn Thị Lan', email='lan@sofaflow.vn',
                   role='user', position='Nhân Viên Hỗ Trợ', password=USER_PWD)

    db.session.flush()
    for u in [ca, sa1, u1a, u1b, sa2, u2a, u2b]:
        print(f"[+] User: {u.username} ({u.role}) → Store: {u.store.name if u.store_id else 'N/A'}")
    return ca, sa1, sa2


def create_customers_and_orders(company, store1, store2):
    """Create 2 customers per store + 1 order per customer."""
    def make_customer(company_id, store_id, code, name, phone, address, city,
                      tax_code=None, rep_name=None, rep_title=None):
        c = Customer(
            company_id           = company_id,
            store_id             = store_id,
            customer_code        = code,
            name                 = name,
            phone                = phone,
            address              = address,
            city                 = city,
            tax_code             = tax_code,
            representative_name  = rep_name,
            representative_title = rep_title,
            country              = 'Việt Nam',
        )
        db.session.add(c)
        return c

    def make_order(company_id, store_id, customer, code, title, total=0):
        o = Order(
            company_id   = company_id,
            store_id     = store_id,
            customer_id  = customer.id,
            order_code   = code,
            title        = title,
            total_amount = total,
        )
        db.session.add(o)
        db.session.flush()
        lc = LifecycleStatus(order_id=o.id)
        db.session.add(lc)
        return o

    # --- Store 1 customers ---
    c1a = make_customer(company.id, store1.id,
        'KH001', 'Công Ty TNHH Nội Thất Ánh Sáng', '028-3512-1111',
        '10 Đào Duy Từ, Quận 10', 'TP. Hồ Chí Minh',
        tax_code='0301234500', rep_name='Nguyễn Tiến Thành', rep_title='Giám Đốc')
    c1b = make_customer(company.id, store1.id,
        'KH002', 'Hộ Kinh Doanh Thu Hằng', '090-1234-5678',
        '5 Trần Phú, Phường 8, Quận 5', 'TP. Hồ Chí Minh',
        rep_name='Lê Thu Hằng', rep_title='Chủ Hộ')
    db.session.flush()

    # --- Store 2 customers ---
    c2a = make_customer(company.id, store2.id,
        'KH001', 'Văn Phòng Kiến Trúc Hòa Bình', '028-3862-2222',
        '22 Nguyễn Thị Thập, Quận 7', 'TP. Hồ Chí Minh',
        tax_code='0303456789', rep_name='Trần Văn Hòa', rep_title='Kiến Trúc Sư Trưởng')
    c2b = make_customer(company.id, store2.id,
        'KH002', 'Chị Phương Thảo', '090-9876-5432',
        '88 Hoàng Diệu 2, Quận Thủ Đức', 'TP. Hồ Chí Minh',
        rep_name='Nguyễn Phương Thảo', rep_title='Cá Nhân')
    db.session.flush()

    for c in [c1a, c1b, c2a, c2b]:
        print(f"[+] Customer: {c.customer_code} — {c.name} (Store: {c.store.store_code})")

    # --- Orders ---
    o1 = make_order(company.id, store1.id, c1a, 'DH001',
                    'Bộ Ghế Sofa Phòng Khách Luxury 3+1+1', 45_000_000)
    o2 = make_order(company.id, store1.id, c1b, 'DH002',
                    'Sofa Góc L + Bàn Trà Kính Cường Lực',  28_500_000)
    o3 = make_order(company.id, store2.id, c2a, 'DH001',
                    'Nội Thất Phòng Họp Căn Hộ Mẫu',        67_000_000)
    o4 = make_order(company.id, store2.id, c2b, 'DH002',
                    'Bộ Phòng Ngủ Master Bedroom',            38_200_000)

    # Mark o1 with a quotation created step
    o1.lifecycle.quotation_created    = True
    o1.lifecycle.quotation_created_at = datetime.utcnow()
    o2.lifecycle.quotation_created    = True
    o2.lifecycle.quotation_created_at = datetime.utcnow()
    o3.lifecycle.quotation_created    = True
    o3.lifecycle.quotation_created_at = datetime.utcnow()
    o3.lifecycle.quotation_approved   = True
    o3.lifecycle.quotation_approved_at= datetime.utcnow()
    o3.lifecycle.contract_created     = True
    o3.lifecycle.contract_created_at  = datetime.utcnow()

    db.session.flush()
    for o in [o1, o2, o3, o4]:
        print(f"[+] Order: {o.order_code} — {o.title[:40]} (Store: {o.store.store_code})")


def main():
    with app.app_context():
        print("\n=== Creating Sample Data ===\n")
        clean_existing()
        company = create_company()
        store1, store2 = create_stores(company)
        create_users(company, store1, store2)
        create_customers_and_orders(company, store1, store2)
        db.session.commit()
        print("""
=== Sample Data Created! ===

Login credentials:
  Company Code : DEMO01

  company_admin  username: admin       password: Admin@123
  store_admin    username: admin_q1    password: Admin@123  (Chi Nhánh Quận 1)
  store_admin    username: admin_q7    password: Admin@123  (Chi Nhánh Quận 7)
  user           username: nv01_q1    password: User@123   (Chi Nhánh Quận 1)
  user           username: nv02_q1    password: User@123   (Chi Nhánh Quận 1)
  user           username: nv01_q7    password: User@123   (Chi Nhánh Quận 7)
  user           username: nv02_q7    password: User@123   (Chi Nhánh Quận 7)
""")


if __name__ == '__main__':
    main()
