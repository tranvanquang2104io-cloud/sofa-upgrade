"""
Master admin blueprint — system-level management (companies, global oversight).
Completely separate from company-scoped auth.
"""
import os
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, current_app
)
from app.config.database import db
from app.models.models import MasterAdmin, Company, User, Store, DocumentTemplate
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def master_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('master_admin_id'):
            return redirect(url_for('admin.login'))
        admin = db.session.get(MasterAdmin, session['master_admin_id'])
        if not admin or not admin.is_active:
            session.pop('master_admin_id', None)
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('master_admin_id'):
        return redirect(url_for('admin.companies'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        admin = MasterAdmin.query.filter_by(username=username, is_active=True).first()
        if admin and admin.check_password(password):
            session['master_admin_id']       = str(admin.id)
            session['master_admin_username'] = admin.username
            session['master_admin_name']     = admin.full_name
            admin.last_login = db.func.now()
            db.session.commit()
            logger.info(f"Master admin logged in: {username}")
            return redirect(url_for('admin.companies'))

        flash('Tên đăng nhập hoặc mật khẩu không đúng.', 'error')

    return render_template('admin/login.html')


@admin_bp.route('/logout')
def logout():
    session.pop('master_admin_id', None)
    session.pop('master_admin_username', None)
    session.pop('master_admin_name', None)
    flash('Đã đăng xuất.', 'success')
    return redirect(url_for('admin.login'))


# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------

@admin_bp.route('/')
@admin_bp.route('/companies')
@master_login_required
def companies():
    companies = Company.query.order_by(Company.created_at.desc()).all()
    return render_template('admin/companies.html', companies=companies)


@admin_bp.route('/companies/create', methods=['GET', 'POST'])
@master_login_required
def create_company():
    if request.method == 'POST':
        company_code      = request.form.get('company_code', '').strip().upper()
        name              = request.form.get('name', '').strip()
        email             = request.form.get('email', '').strip()
        phone             = request.form.get('phone', '').strip() or None
        address           = request.form.get('address', '').strip() or None
        city              = request.form.get('city', '').strip() or None
        tax_code          = request.form.get('tax_code', '').strip() or None
        representative    = request.form.get('representative_name', '').strip() or None
        rep_title         = request.form.get('representative_title', '').strip() or 'Giám Đốc'
        vat_rate          = request.form.get('vat_rate', '8').strip()
        admin_username    = request.form.get('admin_username', '').strip()
        admin_password    = request.form.get('admin_password', '')
        admin_fullname    = request.form.get('admin_fullname', '').strip()
        admin_email       = request.form.get('admin_email', '').strip()

        if not all([company_code, name, email, admin_username, admin_password, admin_fullname]):
            flash('Vui lòng điền đầy đủ các trường bắt buộc.', 'error')
            return render_template('admin/create_company.html')

        if Company.query.filter_by(company_code=company_code).first():
            flash(f'Mã công ty "{company_code}" đã tồn tại.', 'error')
            return render_template('admin/create_company.html')

        try:
            # Create company
            company = Company(
                company_code=company_code,
                name=name,
                email=email,
                phone=phone,
                address=address,
                city=city,
                tax_code=tax_code,
                representative_name=representative,
                representative_title=rep_title,
                vat_rate=float(vat_rate) if vat_rate else 8.0,
            )
            db.session.add(company)
            db.session.flush()  # get company.id

            # Auto-create template folder
            templates_dir = current_app.config.get('TEMPLATES_FOLDER')
            if templates_dir:
                safe_code = company_code.replace('/', '_').replace('\\', '_')
                os.makedirs(os.path.join(templates_dir, safe_code), exist_ok=True)

            # Create docs folder
            docs_dir = current_app.config.get('DOCUMENTS_FOLDER')
            if docs_dir:
                os.makedirs(docs_dir, exist_ok=True)

            # Create default store (same as company)
            store = Store(
                company_id=company.id,
                store_code=company_code,
                name=f'Cửa hàng chính – {name}',
            )
            db.session.add(store)
            db.session.flush()

            # Create company admin user
            admin_user = User(
                company_id=company.id,
                store_id=None,
                username=admin_username,
                email=admin_email or email,
                full_name=admin_fullname,
                role=User.ROLE_COMPANY_ADMIN,
            )
            admin_user.set_password(admin_password)
            db.session.add(admin_user)
            db.session.commit()

            flash(f'Công ty "{name}" ({company_code}) đã được tạo thành công.', 'success')
            logger.info(f"Master admin created company: {company_code}")
            return redirect(url_for('admin.companies'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating company: {e}", exc_info=True)
            flash(f'Lỗi: {e}', 'error')

    return render_template('admin/create_company.html')


@admin_bp.route('/companies/<company_id>/edit', methods=['GET', 'POST'])
@master_login_required
def edit_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Không tìm thấy công ty.', 'error')
        return redirect(url_for('admin.companies'))

    if request.method == 'POST':
        company.name               = request.form.get('name', company.name).strip()
        company.email              = request.form.get('email', company.email).strip()
        company.phone              = request.form.get('phone', '').strip() or company.phone
        company.address            = request.form.get('address', '').strip() or None
        company.city               = request.form.get('city', '').strip() or None
        company.tax_code           = request.form.get('tax_code', '').strip() or None
        company.representative_name  = request.form.get('representative_name', '').strip() or None
        company.representative_title = request.form.get('representative_title', '').strip() or 'Giám Đốc'
        vat = request.form.get('vat_rate', '').strip()
        if vat:
            company.vat_rate = float(vat)
        try:
            db.session.commit()
            flash('Đã cập nhật thông tin công ty.', 'success')
            return redirect(url_for('admin.companies'))
        except Exception as e:
            db.session.rollback()
            flash(f'Lỗi: {e}', 'error')

    users = User.query.filter_by(company_id=company.id).order_by(User.role, User.full_name).all()
    return render_template('admin/edit_company.html', company=company, users=users)


@admin_bp.route('/companies/<company_id>/toggle', methods=['POST'])
@master_login_required
def toggle_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Không tìm thấy công ty.', 'error')
    else:
        company.is_active = not company.is_active
        db.session.commit()
        state = 'kích hoạt' if company.is_active else 'vô hiệu hóa'
        flash(f'Công ty "{company.name}" đã được {state}.', 'success')
    return redirect(url_for('admin.companies'))


# ---------------------------------------------------------------------------
# Master admin self-management
# ---------------------------------------------------------------------------

@admin_bp.route('/admins')
@master_login_required
def list_admins():
    admins = MasterAdmin.query.order_by(MasterAdmin.created_at).all()
    return render_template('admin/admins.html', admins=admins)


@admin_bp.route('/admins/create', methods=['GET', 'POST'])
@master_login_required
def create_admin():
    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        email     = request.form.get('email', '').strip()
        fullname  = request.form.get('full_name', '').strip()
        password  = request.form.get('password', '')

        if not all([username, email, fullname, password]):
            flash('Vui lòng điền đầy đủ các trường.', 'error')
            return render_template('admin/create_admin.html')

        if MasterAdmin.query.filter_by(username=username).first():
            flash(f'Tên đăng nhập "{username}" đã tồn tại.', 'error')
            return render_template('admin/create_admin.html')

        new_admin = MasterAdmin(username=username, email=email, full_name=fullname)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()
        flash(f'Master admin "{username}" đã được tạo.', 'success')
        return redirect(url_for('admin.list_admins'))

    return render_template('admin/create_admin.html')
