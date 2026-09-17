"""
Tạo / reset bộ tài khoản mô phỏng cho môi trường QAS/DEV.

Idempotent: chạy lại sẽ reset mật khẩu, role, quyền về đúng bộ chuẩn.
Chỉ đụng các tài khoản có email @sofaflow.test và công ty QATEST —
không sửa tài khoản thật.

An toàn: từ chối chạy khi APP_ENV_NAME != QAS/DEV (container prod không có biến này),
trừ khi truyền --i-know-this-is-not-prod.

Usage (QAS):
    docker exec sofa-flow-qas-app-1 sh -c "PYTHONPATH=/app python /app/scripts/create_qas_test_accounts.py"
Usage (local dev):
    set APP_ENV_NAME=DEV && venv/Scripts/python.exe scripts/create_qas_test_accounts.py
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.config.database import db
from app.models.models import Company, Store, User, MasterAdmin, FEATURE_KEYS

PASSWORD = 'Qas@2026!'
DOMAIN = 'sofaflow.test'
MAIN_COMPANY = 'NGOCHAN'      # tenant có dữ liệu copy từ prod
ISO_COMPANY = 'QATEST'        # tenant thứ 2 để test cô lập dữ liệu (IDOR)

MASTER_ADMINS = [
    # username, full_name
    ('qa_master', 'QA Master Admin'),
]

# username, full_name, role, features (None = admin/full), active, store-scoped
NGOCHAN_USERS = [
    ('qa_admin',     'QA Quản trị công ty',     User.ROLE_COMPANY_ADMIN, None, True,  False),
    ('qa_store',     'QA Quản lý cửa hàng',     User.ROLE_STORE_ADMIN,   None, True,  True),
    ('qa_full',      'QA Nhân viên full quyền', User.ROLE_USER, list(FEATURE_KEYS), True, True),
    ('qa_sales',     'QA Nhân viên bán hàng',   User.ROLE_USER, ['customers', 'orders'], True, True),
    ('qa_kho',       'QA Nhân viên kho',        User.ROLE_USER, ['inventory', 'purchasing'], True, True),
    ('qa_report',    'QA Chỉ xem báo cáo',      User.ROLE_USER, ['reports'], True, True),
    ('qa_noperm',    'QA Không có quyền',       User.ROLE_USER, [], True, True),
    ('qa_disabled',  'QA Tài khoản bị khoá',    User.ROLE_USER, list(FEATURE_KEYS), False, True),
]

QATEST_USERS = [
    ('qa_other_admin', 'QA Admin tenant khác', User.ROLE_COMPANY_ADMIN, None, True, False),
    ('qa_other_user',  'QA User tenant khác',  User.ROLE_USER, list(FEATURE_KEYS), True, True),
]


def _email(username, company_code=None):
    local = username if company_code in (None, MAIN_COMPANY) else f'{username}.{company_code.lower()}'
    return f'{local}@{DOMAIN}'


def ensure_iso_company():
    company = Company.query.filter_by(company_code=ISO_COMPANY).first()
    if not company:
        company = Company(company_code=ISO_COMPANY, name='Công ty QA Test (tenant cô lập)',
                          email=f'company@{DOMAIN}', phone='0000000000',
                          address='QA', city='QA', country='Vietnam', vat_rate=8)
        db.session.add(company)
        db.session.flush()
    store = Store.query.filter_by(company_id=company.id, store_code='QA-01').first()
    if not store:
        store = Store(company_id=company.id, store_code='QA-01', name='Cửa hàng QA Test')
        db.session.add(store)
        db.session.flush()
    return company, store


def upsert_users(company, store, specs):
    rows = []
    for username, name, role, features, active, scoped in specs:
        email = _email(username, company.company_code)
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email, company_id=company.id)
            db.session.add(user)
        user.company_id = company.id
        user.username = username
        user.full_name = name
        user.role = role
        user.store_id = store.id if (scoped and store) else None
        user.allowed_features = features or []
        user.is_active = active
        user.position = 'QA'
        user.set_password(PASSWORD)
        rows.append((company.company_code, email, role, '(full)' if features is None else (','.join(features) or '(none)'),
                     'yes' if active else 'LOCKED'))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--i-know-this-is-not-prod', action='store_true')
    args = ap.parse_args()

    env_name = os.environ.get('APP_ENV_NAME', '').upper()
    if env_name not in ('QAS', 'DEV') and not args.i_know_this_is_not_prod:
        sys.exit(f'REFUSED: APP_ENV_NAME={env_name!r} (need QAS or DEV). Không chạy trên production.')

    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    with app.app_context():
        for username, name in MASTER_ADMINS:
            ma = MasterAdmin.query.filter_by(username=username).first()
            if not ma:
                ma = MasterAdmin(username=username, email=f'{username}@{DOMAIN}')
                db.session.add(ma)
            ma.full_name = name
            ma.is_active = True
            ma.set_password(PASSWORD)

        main_co = Company.query.filter_by(company_code=MAIN_COMPANY).first()
        if not main_co:
            sys.exit(f'Company {MAIN_COMPANY} not found')
        main_store = Store.query.filter_by(company_id=main_co.id).order_by(Store.created_at).first()

        rows = upsert_users(main_co, main_store, NGOCHAN_USERS)
        iso_co, iso_store = ensure_iso_company()
        rows += upsert_users(iso_co, iso_store, QATEST_USERS)
        db.session.commit()

        print(f'Password chung: {PASSWORD}\n')
        print('ADMIN APP (/admin/login, đăng nhập bằng username):')
        for username, _ in MASTER_ADMINS:
            print(f'  {username}')
        print('\nAPP (/auth/login, đăng nhập bằng email):')
        for r in rows:
            print('  {:<8} {:<34} {:<14} {:<32} {}'.format(*r))


if __name__ == '__main__':
    main()
