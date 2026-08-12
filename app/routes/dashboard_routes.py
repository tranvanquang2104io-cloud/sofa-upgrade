"""
Dashboard and main application routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, send_file, current_app, session, abort
from app.utils.i18n import t
from app.utils.auth_utils import (
    login_required, company_admin_required, store_admin_required,
    ensure_tenant_access, ensure_store_access,
    get_current_company_id, get_current_store_id,
    get_accessible_store_ids, is_company_admin,
)
from app.services.services import (
    StoreService, UserService, CustomerService, OrderService, QuotationService,
    ContractService, HandoverRecordService, PaymentReportService, DocumentService,
    MaterialService, SupplierService,
)
from app.repositories.repository import (
    StoreRepository, CustomerRepository, OrderRepository, DocumentRepository,
    QuotationRepository, ContractRepository, HandoverRecordRepository,
    PaymentReportRepository, LifecycleStatusRepository, DocumentTemplateRepository,
)
from app.models import Order, Document
from app.config.database import db
from sqlalchemy.orm import joinedload
from app.utils.extension_fields import (
    collect_extension_values, apply_extension_values, get_enabled_configs, FIELD_KEYS,
)
from app.models import ExtensionFieldConfig
from datetime import datetime, date
import logging
import os
import uuid

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


@dashboard_bp.before_request
def _enforce_feature_permissions():
    """RBAC: block a logged-in regular user from feature areas they weren't granted.
    Admins and unmapped endpoints pass through; unauthenticated requests are handled
    by each view's login_required."""
    from app.utils.auth_utils import feature_for_endpoint, current_user_can
    if 'user_id' not in session:
        return
    feature = feature_for_endpoint(request.endpoint)
    if feature and not current_user_can(feature):
        abort(403)


def _save_item_image(file_storage, existing_path: str = None) -> str | None:
    """
    Save an uploaded item image to uploads/items/ and return its relative path.

    - If ``file_storage`` has a filename, save it and return the new relative path.
    - Otherwise return ``existing_path`` (preserves existing image on edit).
    Returns ``None`` if neither is provided.
    """
    if file_storage and getattr(file_storage, 'filename', ''):
        from werkzeug.utils import secure_filename
        items_folder = current_app.config['ITEMS_FOLDER']
        os.makedirs(items_folder, exist_ok=True)
        ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
        filename = f"{uuid.uuid4()}{ext}"
        file_storage.save(os.path.join(items_folder, filename))
        return f"items/{filename}"
    return existing_path or None


def _create_final_payment_from_handover(order_id, company_id, handover):
    """Create a draft final payment report derived from a just-confirmed handover.

    Used by the "create both at once" option on the handover form (item 4). Amounts come
    from the handover totals; the advance already collected is subtracted so the report
    shows the true remaining balance. The report is left unconfirmed (draft) — the user
    confirms it later, optionally attaching payment proof.
    """
    from app.models.models import Company as _Company, PaymentReport as _PR
    from app.repositories.repository import PaymentReportRepository as _PaymentRepo

    # Map handover items to the payment item schema
    pay_items = []
    for it in (handover.items or []):
        qty = float(it.get('accepted_qty') or it.get('quantity') or 0)
        price = float(it.get('unit_price') or 0)
        pay_items.append({
            'name': it.get('name', ''),
            'unit': it.get('unit', ''),
            'quantity': qty,
            'unit_price': price,
            'total': qty * price,
        })

    # Advance already confirmed for this order
    confirmed_adv = db.session.query(_PR).filter(
        _PR.order_id == order_id, _PR.payment_type == 'advance',
        _PR.is_confirmed == True, _PR.is_canceled == False).all()
    advance_amount = float(sum(p.advance_amount or 0 for p in confirmed_adv))

    amount = float(handover.total_amount or 0)
    remaining_amount = amount - advance_amount

    # Derive a unique report number from the handover number
    base_number = f"TT-{handover.report_number}"
    report_number = base_number
    repo = _PaymentRepo()
    if repo.get_by_company_and_number(company_id, report_number):
        report_number = f"{base_number}-{datetime.utcnow().strftime('%H%M%S')}"

    company = db.session.get(_Company, company_id)
    bank_info = getattr(company, 'bank_accounts', None) or []

    today = datetime.utcnow().date()
    payment_service = PaymentReportService()
    payment = payment_service.create_payment_report(
        order_id=order_id,
        report_number=report_number,
        payment_type='final',
        report_date=today,
        payment_date=today,
        items=pay_items,
        subtotal=float(handover.subtotal or 0),
        vat_rate=float(handover.vat_rate or 8),
        vat_amount=float(handover.vat_amount or 0),
        shipping_fee=float(handover.shipping_fee or 0),
        another_fee=float(handover.another_fee or 0),
        amount=amount,
        advance_amount=advance_amount,
        remaining_amount=remaining_amount,
        bank_account_info=bank_info,
    )
    db.session.commit()
    return payment


def parse_line_items(form, files=None, with_images=False):
    """Parse repeated item_* form fields into a list of item dicts and the subtotal.

    Reads item_name[]/item_unit[]/item_quantity[]/item_price[]; blank-name rows are
    skipped. Validates that quantity and price are non-negative (raises ValueError —
    generalises the W7 guard to every standard document form). Per-line totals and
    the subtotal are computed with Decimal to avoid float drift, then returned as
    JSON-serialisable floats. When ``with_images`` is set, item images are saved
    (honouring item_existing_image[] for edits) and stored under ``image_path``.

    Note: handover records are NOT parsed here — they carry a different item schema
    (delivered/accepted qty, status, reason) and keep their own parser.
    """
    from decimal import Decimal

    names = form.getlist('item_name[]')
    units = form.getlist('item_unit[]')
    quantities = form.getlist('item_quantity[]')
    prices = form.getlist('item_price[]')
    images = files.getlist('item_image[]') if (with_images and files is not None) else []
    existing_images = form.getlist('item_existing_image[]') if with_images else []

    items = []
    subtotal = Decimal('0')
    for i, name in enumerate(names):
        if not name or not name.strip():
            continue
        qty = float(quantities[i] or 0) if i < len(quantities) else 0.0
        price = float(prices[i] or 0) if i < len(prices) else 0.0
        if qty < 0 or price < 0:
            raise ValueError(t('Quantity and unit price cannot be negative'))
        unit = units[i].strip() if i < len(units) else ''
        line_total = Decimal(str(qty)) * Decimal(str(price))
        item = {
            'name': name.strip(),
            'unit': unit,
            'quantity': qty,
            'unit_price': price,
            'total': float(line_total),
        }
        if with_images:
            existing = existing_images[i] if i < len(existing_images) else None
            item['image_path'] = _save_item_image(
                images[i] if i < len(images) else None, existing)
        items.append(item)
        subtotal += line_total
    return items, float(subtotal)


def parse_material_lines(form, with_price=False):
    """Parse repeated line_* fields (procurement docs: PR/PO) into dicts.

    Reads line_material_id[]/line_quantity[]/line_unit[] (+ line_price[] when
    with_price). Rows with no material are skipped.
    """
    mids = form.getlist('line_material_id[]')
    qtys = form.getlist('line_quantity[]')
    units = form.getlist('line_unit[]')
    prices = form.getlist('line_price[]') if with_price else []
    out = []
    for i, mid in enumerate(mids):
        if not mid:
            continue
        row = {
            'material_id': mid,
            'quantity': (qtys[i] if i < len(qtys) else 0) or 0,
            'unit': (units[i].strip() if i < len(units) and units[i] else None),
        }
        if with_price:
            row['unit_price'] = (prices[i] if i < len(prices) else '') or ''
        out.append(row)
    return out


# ===== LANGUAGE SWITCHER =====

@dashboard_bp.route('/set-language/<lang>')
def set_language(lang):
    """Switch the UI language stored in the session."""
    if lang in ('en', 'vi'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('dashboard.index'))


# ===== DASHBOARD =====

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard — stats scoped to the current user's accessible stores"""
    company_id = get_current_company_id()

    store_repo       = StoreRepository()
    customer_service = CustomerService()

    # Stores the user can see
    accessible_store_ids = get_accessible_store_ids(company_id)
    stores = store_repo.get_stores_for_company(company_id) if is_company_admin() \
             else [store_repo.get_by_id(sid) for sid in accessible_store_ids if store_repo.get_by_id(sid)]

    # Scope orders to accessible stores
    from app.repositories.repository import OrderRepository as _OrderRepo
    from app.models.models import Customer as _Customer, Order as _Order
    order_repo = _OrderRepo()

    if is_company_admin():
        all_orders = order_repo.get_orders_for_company(company_id)
        total_customers = db.session.query(_Customer).filter_by(company_id=company_id).count()
    else:
        all_orders = []
        for sid in accessible_store_ids:
            all_orders += _Order.query.filter_by(
                company_id=company_id, store_id=sid, is_active=True
            ).all()
        total_customers = db.session.query(_Customer).filter(
            _Customer.store_id.in_(accessible_store_ids)
        ).count()

    total_orders = len(all_orders)
    in_progress  = sum(1 for o in all_orders if not o.is_canceled and o.lifecycle and not o.lifecycle.completed)
    completed    = sum(1 for o in all_orders if o.lifecycle and o.lifecycle.completed)
    canceled     = sum(1 for o in all_orders if o.is_canceled)

    # Recent orders (last 10)
    order_service = OrderService()
    recent_orders = order_service.list_orders_for_company(company_id, page=1, per_page=10)
    if not is_company_admin():
        recent_orders = [o for o in recent_orders if o.store_id in accessible_store_ids][:10]

    return render_template('dashboard/index.html',
                           orders=recent_orders,
                           stores=stores,
                           total_orders=total_orders,
                           total_customers=total_customers,
                           in_progress=in_progress,
                           completed=completed,
                           canceled=canceled)


# ===== COMPANY SETTINGS =====

@dashboard_bp.route('/settings/company', methods=['GET', 'POST'])
@company_admin_required
def company_settings():
    """View and update company profile/settings"""
    from app.models.models import Company
    import json as _json
    company_id = get_current_company_id()
    company = db.session.get(Company, company_id)
    if not company:
        flash(t('Company not found'), 'error')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        try:
            company.name = request.form.get('name', '').strip() or company.name
            company.email = request.form.get('email', '').strip() or company.email
            company.phone = request.form.get('phone', '').strip() or None
            company.address = request.form.get('address', '').strip() or None
            company.production_address = request.form.get('production_address', '').strip() or None
            company.city = request.form.get('city', '').strip() or None
            company.country = request.form.get('country', '').strip() or None
            company.tax_code = request.form.get('tax_code', '').strip() or None
            company.representative_name = request.form.get('representative_name', '').strip() or None
            company.representative_title = request.form.get('representative_title', '').strip() or None
            company.business_registration_number = request.form.get('business_registration_number', '').strip() or None
            company.website = request.form.get('website', '').strip() or None
            vat_str = request.form.get('vat_rate', '').strip()
            company.vat_rate = float(vat_str) if vat_str else company.vat_rate
            # Bank accounts from JSON textarea
            bank_json = request.form.get('bank_accounts', '').strip()
            try:
                company.bank_accounts = _json.loads(bank_json) if bank_json else []
            except Exception:
                pass
            db.session.commit()
            flash(t('Company settings updated successfully'), 'success')
        except Exception as e:
            logger.error(f"Error updating company settings: {str(e)}")
            db.session.rollback()
            flash(t('Error updating company settings'), 'error')
    
    return render_template('settings/company.html', company=company)


# ===== DOCUMENT TEMPLATES =====

@dashboard_bp.route('/settings/templates', methods=['GET'])
@company_admin_required
def list_templates():
    """List document templates for the current company"""
    company_id = get_current_company_id()
    repo = DocumentTemplateRepository()
    templates = repo.get_for_company(company_id)
    # Also include inactive ones
    from app.models.models import DocumentTemplate as _DT
    all_templates = db.session.query(_DT).filter_by(company_id=company_id).order_by(_DT.document_type, _DT.created_at.desc()).all()
    return render_template('settings/templates.html', templates=all_templates)


@dashboard_bp.route('/settings/templates/upload', methods=['POST'])
@company_admin_required
def upload_template():
    """Upload a new document template file"""
    company_id = get_current_company_id()
    name = request.form.get('name', '').strip()
    doc_type = request.form.get('document_type', '').strip()
    description = request.form.get('description', '').strip() or None

    if not name or not doc_type:
        flash(t('Vui lòng điền đầy đủ tên và loại tài liệu.'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    file = request.files.get('template_file')
    if not file or file.filename == '':
        flash(t('Vui lòng chọn tệp mẫu (.docx).'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    allowed_exts = {'.docx', '.rtf', '.txt'}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_exts:
        flash(t('Chỉ cho phép tệp .docx, .rtf hoặc .txt.'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    try:
        from app.config.config import Config
        templates_base = current_app.config.get('TEMPLATES_FOLDER',
                                                  os.path.join(current_app.root_path, 'uploads', 'templates'))
        # Use company_code as subfolder name
        from app.models.models import Company as _CompanyM
        _co = db.session.get(_CompanyM, company_id)
        company_folder = (_co.company_code if _co else str(company_id)).replace('/', '_').replace('\\', '_')
        company_dir = os.path.join(templates_base, company_folder)
        os.makedirs(company_dir, exist_ok=True)

        # Save file with a sanitised name
        safe_name = f"{doc_type}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(company_dir, safe_name)
        file.save(file_path)

        # Deactivate existing active templates of the same type before adding the new one
        from app.models.models import DocumentTemplate as _DT
        db.session.query(_DT).filter_by(
            company_id=company_id, document_type=doc_type, is_active=True
        ).update({'is_active': False})
        db.session.flush()

        new_tpl = _DT(
            company_id=company_id,
            name=name,
            document_type=doc_type,
            description=description,
            template_file=safe_name,
            is_active=True,
        )
        db.session.add(new_tpl)
        db.session.commit()
        flash(t(f'Mẫu "{name}" đã được tải lên thành công.'), 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading template: {str(e)}", exc_info=True)
        flash(t(f'Lỗi khi tải lên mẫu: {str(e)}'), 'error')

    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_template(template_id):
    """Deactivate a document template"""
    company_id = get_current_company_id()
    from app.models.models import DocumentTemplate as _DT
    tpl = db.session.get(_DT, template_id)
    if not tpl or str(tpl.company_id) != str(company_id):
        flash(t('Không tìm thấy mẫu.'), 'error')
    else:
        tpl.is_active = False
        db.session.commit()
        flash(t(f'Mẫu "{tpl.name}" đã được vô hiệu hóa.'), 'success')
    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/activate', methods=['POST'])
@company_admin_required
def activate_template(template_id):
    """Activate a document template"""
    company_id = get_current_company_id()
    from app.models.models import DocumentTemplate as _DT
    tpl = db.session.get(_DT, template_id)
    if not tpl or str(tpl.company_id) != str(company_id):
        flash(t('Không tìm thấy mẫu.'), 'error')
    else:
        tpl.is_active = True
        db.session.commit()
        flash(t(f'Mẫu "{tpl.name}" đã được kích hoạt.'), 'success')
    return redirect(url_for('dashboard.list_templates'))


# ===== CUSTOMERS =====

@dashboard_bp.route('/customers', methods=['GET'])
@login_required
def list_customers():
    """List customers — scoped to accessible stores"""
    company_id = get_current_company_id()
    store_id   = request.args.get('store_id')
    page       = request.args.get('page', 1, type=int)
    search     = request.args.get('search', '')

    store_repo       = StoreRepository()
    customer_service = CustomerService()

    # Build the list of stores this user may see
    accessible_ids = get_accessible_store_ids(company_id)
    all_stores     = store_repo.get_stores_for_company(company_id)
    stores         = [s for s in all_stores if s.id in accessible_ids]

    # For non-company-admin: default to their own store; company-admin can select "All"
    if not store_id and not is_company_admin() and stores:
        store_id = str(stores[0].id)

    from app.models.models import Customer as _Customer
    per_page  = current_app.config.get('ITEMS_PER_PAGE', 20)
    customers = None
    total     = 0
    pagination = None  # only set for the (non-search) browse paths

    if store_id:
        # Single store — enforce access
        try:
            ensure_store_access(store_id)
        except Exception:
            flash(t('Không có quyền truy cập cửa hàng này'), 'error')
            return redirect(url_for('dashboard.index'))

        store = store_repo.get_active_store(company_id, store_id)
        if not store:
            flash(t('Cửa hàng không tìm thấy'), 'error')
            return redirect(url_for('dashboard.index'))

        if search:
            customers = customer_service.search_customers(store_id, search)
            total     = len(customers)
        else:
            q = _Customer.query.filter_by(store_id=store_id, is_active=True).order_by(_Customer.customer_code)
            pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
            customers, total = pagination.items, pagination.total
    else:
        # "All Stores" — company admin sees every accessible store's customers
        from app.repositories.repository import CustomerRepository as _CustRepo
        _repo = _CustRepo()
        if search:
            customers = _repo.search_customers_for_stores(accessible_ids, search)
            total     = len(customers)
        else:
            q = _Customer.query.filter(
                _Customer.store_id.in_(accessible_ids), _Customer.is_active == True
            ).order_by(_Customer.customer_code)
            pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
            customers, total = pagination.items, pagination.total

    # Preserve store/search filters across pagination links.
    extra_query = {k: v for k, v in (('store_id', store_id), ('search', search)) if v}

    return render_template('customers/list.html',
                           customers=customers,
                           stores=stores,
                           selected_store_id=store_id,
                           page=page,
                           total=total,
                           pagination=pagination,
                           extra_query=extra_query,
                           search=search)


@dashboard_bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
def create_customer():
    """Create customer — store list restricted to accessible stores"""
    company_id = get_current_company_id()
    store_repo = StoreRepository()
    store_id = request.args.get('store_id') or request.form.get('store_id')

    # Accessible stores only
    accessible_ids = get_accessible_store_ids(company_id)
    all_stores     = store_repo.get_stores_for_company(company_id)
    stores         = [s for s in all_stores if s.id in accessible_ids]

    # For non-company-admin: auto-assign to their store
    if not is_company_admin() and accessible_ids and not store_id:
        store_id = accessible_ids[0]

    # Check if company has any stores
    if not stores:
        flash(t('Chưa có cửa hàng nào. Vui lòng tạo cửa hàng trước.'), 'error')
        return redirect(url_for('dashboard.index'))
    
    # Set default store_id if not provided, convert string to UUID if needed
    if not store_id:
        store_id = stores[0].id
    elif isinstance(store_id, str):
        try:
            store_id = uuid.UUID(store_id)
        except ValueError:
            flash(t('Invalid store ID'), 'error')
            return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            # Validate store_id is provided
            if not store_id:
                flash(t('Store selection is required'), 'error')
                return render_template('customers/create.html', stores=stores, selected_store_id=store_id)
            
            ext_values = collect_extension_values(company_id, 'customer', request.form)  # validate early
            store_customer = CustomerService()
            customer = store_customer.create_customer(
                company_id=company_id,
                store_id=store_id,
                customer_code=request.form.get('customer_code', '').strip(),
                name=request.form.get('name', '').strip(),
                phone=request.form.get('phone', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                city=request.form.get('city', '').strip() or None,
                postal_code=request.form.get('postal_code', '').strip() or None,
                country=request.form.get('country', '').strip() or None,
                tax_code=request.form.get('tax_code', '').strip() or None,
                representative_name=request.form.get('representative_name', '').strip() or None,
                representative_title=request.form.get('representative_title', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            if apply_extension_values(customer, ext_values):
                db.session.commit()
            flash(t('Customer created successfully'), 'success')
            return redirect(url_for('dashboard.list_customers', store_id=store_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}", exc_info=True)
            flash(t('Error creating customer'), 'error')
    
    return render_template('customers/create.html', stores=stores, selected_store_id=store_id)


@dashboard_bp.route('/customers/<customer_id>')
@login_required
def view_customer(customer_id):
    """View customer details"""
    company_id = get_current_company_id()
    customer_repo = CustomerRepository()
    
    customer = customer_repo.get_by_id(customer_id)
    if not customer or str(customer.store.company_id) != str(company_id):
        flash(t('Customer not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_customers'))
    
    order_service = OrderService()
    orders = order_service.list_orders_for_customer(customer_id)
    
    return render_template('customers/view.html', customer=customer, orders=orders)


@dashboard_bp.route('/customers/<customer_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_customer(customer_id):
    """Edit customer information"""
    company_id = get_current_company_id()
    customer_repo = CustomerRepository()

    customer = customer_repo.get_by_id(customer_id)
    if not customer or str(customer.store.company_id) != str(company_id):
        flash(t('Không tìm thấy khách hàng hoặc không có quyền truy cập'), 'error')
        return redirect(url_for('dashboard.list_customers'))

    if request.method == 'POST':
        try:
            customer_service = CustomerService()
            # On update, pass empty strings through (not `or None`) so that CLEARING
            # an optional field actually saves it as empty. `name` stays required.
            customer_service.update_customer(
                customer_id=customer_id,
                name=request.form.get('name', '').strip() or None,
                phone=request.form.get('phone', '').strip(),
                email=request.form.get('email', '').strip(),
                tax_code=request.form.get('tax_code', '').strip(),
                representative_name=request.form.get('representative_name', '').strip(),
                representative_title=request.form.get('representative_title', '').strip(),
                address=request.form.get('address', '').strip(),
                city=request.form.get('city', '').strip(),
                postal_code=request.form.get('postal_code', '').strip(),
                country=request.form.get('country', '').strip(),
                notes=request.form.get('notes', '').strip(),
            )
            flash(t('Cập nhật thông tin khách hàng thành công!'), 'success')
            return redirect(url_for('dashboard.view_customer', customer_id=customer_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}", exc_info=True)
            flash(t('Lỗi khi cập nhật thông tin khách hàng'), 'error')

    return render_template('customers/edit.html', customer=customer)


# ===== ORDERS =====

@dashboard_bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    """List orders — scoped to accessible stores"""
    company_id = get_current_company_id()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    from app.models.models import Order as _Order
    query = _Order.query.filter(_Order.company_id == company_id, _Order.is_active == True)
    if not is_company_admin():
        accessible_ids = get_accessible_store_ids(company_id)
        query = query.filter(_Order.store_id.in_(accessible_ids))
    query = query.options(
        joinedload(_Order.customer),
        joinedload(_Order.lifecycle),
    ).order_by(_Order.created_at.desc())

    # error_out=False → an out-of-range page renders empty instead of 404.
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return render_template('orders/list.html', orders=pagination.items,
                           pagination=pagination, page=page)


@dashboard_bp.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_order():
    """Create order — store list restricted to accessible stores"""
    company_id = get_current_company_id()
    store_repo    = StoreRepository()
    customer_repo = CustomerRepository()

    # Accessible stores only
    accessible_ids = get_accessible_store_ids(company_id)
    all_stores     = store_repo.get_stores_for_company(company_id)
    stores         = [s for s in all_stores if s.id in accessible_ids]
    
    if request.method == 'POST':
        try:
            store_id = request.form.get('store_id')
            customer_id = request.form.get('customer_id')
            
            # Tenant + RBAC guard (AUDIT B5/B7): the customer must belong to THIS
            # company, to the selected store, and the store must be one the current
            # user can access. Blocks cross-tenant / cross-store order creation.
            accessible_store_ids = {str(s.id) for s in stores}
            customer = customer_repo.get_for_company(customer_id, company_id)
            if (not customer
                    or str(store_id) not in accessible_store_ids
                    or str(customer.store_id) != str(store_id)):
                flash(t('Invalid customer selection'), 'error')
                return redirect(url_for('dashboard.create_order'))
            
            order_service = OrderService()
            order = order_service.create_order(
                store_id=store_id,
                company_id=company_id,
                customer_id=customer_id,
                order_code=request.form.get('order_code', '').strip(),
                title=request.form.get('title', '').strip(),
                description=request.form.get('description', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash(t('Order created successfully'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order.id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            flash(t('Error creating order'), 'error')
    
    store_customers = {}
    for store in stores:
        customers = customer_repo.get_customers_for_store(store.id)
        store_customers[str(store.id)] = [
            {
                'id': str(customer.id),
                'customer_code': customer.customer_code,
                'name': customer.name
            }
            for customer in customers
        ]
    
    return render_template('orders/create.html', stores=stores, store_customers=store_customers)


@dashboard_bp.route('/orders/<order_id>', methods=['GET'])
@login_required
def view_order(order_id):
    """View order details with lifecycle"""
    company_id = get_current_company_id()
    
    order_service = OrderService()
    order_details = order_service.get_order_with_details(order_id, company_id)
    
    if not order_details:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('orders/view.html', **order_details)


# ===== QUOTATIONS =====

@dashboard_bp.route('/quotations/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_quotation(order_id):
    """Create quotation"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    from app.models.models import Company as _CompanyQ
    _company_q = db.session.get(_CompanyQ, company_id)
    company_vat_rate = getattr(_company_q, 'vat_rate', 8) or 8

    if request.method == 'POST':
        try:
            # Check for duplicate quotation number
            quotation_number = request.form.get('quotation_number', '').strip()
            quotation_repo = QuotationRepository()
            from app.models.models import Quotation
            existing = quotation_repo.get_by_company_and_number(company_id, quotation_number)
            if existing:
                flash(t(f'Quotation number "{quotation_number}" is already taken. Please use a different number.'), 'error')
                return render_template('quotations/create.html', order=order, company_vat_rate=company_vat_rate)
            
            # Parse items from request
            items, subtotal = parse_line_items(request.form, request.files, with_images=True)

            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            shipping_fee = float(request.form.get('shipping_fee') or 0)
            another_fee = float(request.form.get('another_fee') or 0)
            total = subtotal + vat_amount + shipping_fee + another_fee
            city = request.form.get('city', '').strip() or None
            payment_terms = request.form.get('payment_terms', '').strip() or None
            amount_in_words = request.form.get('amount_in_words', '').strip() or None
            
            quotation_service = QuotationService()
            ext_values = collect_extension_values(company_id, 'quotation', request.form)
            quotation = quotation_service.create_quotation(
                order_id=order_id,
                company_id=company_id,
                quotation_number=request.form.get('quotation_number', '').strip(),
                quotation_date=datetime.strptime(request.form.get('quotation_date'), '%Y-%m-%d').date(),
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                shipping_fee=shipping_fee,
                another_fee=another_fee,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                city=city,
                payment_terms=payment_terms,
                amount_in_words=amount_in_words,
                notes=request.form.get('notes', '').strip() or None
            )
            
            apply_extension_values(quotation, ext_values)
            db.session.commit()

            flash(t('Quotation created successfully'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(t(f'Error: {str(e)}'), 'error')
        except Exception as e:
            logger.error(f"Error creating quotation: {str(e)}")
            flash(t('Error creating quotation'), 'error')

    return render_template('quotations/create.html', order=order, company_vat_rate=company_vat_rate)


# ===== QUOTATION DETAIL, EDIT, AND LIFECYCLE ACTIONS =====

@dashboard_bp.route('/quotations/<quotation_id>/view', methods=['GET'])
@login_required
def view_quotation(quotation_id):
    """View quotation details"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    quotation = quotation_service.get_quotation(quotation_id)
    if not quotation or str(quotation.order.company_id) != str(company_id):
        flash(t('Quotation not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('quotations/view.html', quotation=quotation, order=quotation.order)


@dashboard_bp.route('/quotations/<quotation_id>/edit', methods=['GET', 'POST'])
@login_required  
def edit_quotation(quotation_id):
    """Edit quotation - only if not approved"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    quotation = quotation_service.get_quotation(quotation_id)
    if not quotation or str(quotation.order.company_id) != str(company_id):
        flash(t('Quotation not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not quotation.can_edit():
        flash(t('Quotation cannot be edited after approval'), 'error')
        return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
    
    if request.method == 'POST':
        try:
            # Parse items from request
            items, subtotal = parse_line_items(request.form, request.files, with_images=True)

            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            shipping_fee = float(request.form.get('shipping_fee') or 0)
            another_fee = float(request.form.get('another_fee') or 0)
            total = subtotal + vat_amount + shipping_fee + another_fee
            
            quotation_service.update_quotation(
                quotation_id=quotation_id,
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                shipping_fee=shipping_fee,
                another_fee=another_fee,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                city=request.form.get('city', '').strip() or None,
                payment_terms=request.form.get('payment_terms', '').strip() or None,
                amount_in_words=request.form.get('amount_in_words', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash(t('Quotation updated successfully'), 'success')
            return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
            
        except ValueError as e:
            flash(t(f'Error: {str(e)}'), 'error')
        except Exception as e:
            logger.error(f"Error updating quotation: {str(e)}")
            flash(t('Error updating quotation'), 'error')
    
    return render_template('quotations/edit.html', quotation=quotation, order=quotation.order)


@dashboard_bp.route('/quotations/<quotation_id>/approve', methods=['POST'])
@login_required
def approve_quotation(quotation_id):
    """Approve quotation"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    try:
        quotation = quotation_service.get_quotation(quotation_id)
        if not quotation or str(quotation.order.company_id) != str(company_id):
            flash(t('Quotation not found or access denied'), 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        quotation_service.approve_quotation(quotation_id, quotation.order_id)
        flash(t('Quotation approved successfully'), 'success')
        return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))

    except ValueError as e:
        flash(t(f'Error: {str(e)}'), 'error')
    except Exception as e:
        logger.error(f"Error approving quotation: {str(e)}")
        flash(t('Error approving quotation'), 'error')

    return redirect(url_for('dashboard.list_orders'))


@dashboard_bp.route('/quotations/<quotation_id>/cancel', methods=['POST'])
@login_required
def cancel_quotation(quotation_id):
    """Cancel quotation"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    try:
        quotation = quotation_service.get_quotation(quotation_id)
        if not quotation or str(quotation.order.company_id) != str(company_id):
            flash(t('Quotation not found or access denied'), 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        reason = request.form.get('reason', '').strip() or 'No reason provided'
        quotation_service.cancel_quotation(quotation_id, reason)
        flash(t('Quotation canceled successfully'), 'success')
        return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))

    except ValueError as e:
        flash(t(f'Error: {str(e)}'), 'error')
    except Exception as e:
        logger.error(f"Error canceling quotation: {str(e)}")
        flash(t('Error canceling quotation'), 'error')

    return redirect(url_for('dashboard.list_orders'))


# ===== CONTRACTS =====

@dashboard_bp.route('/contracts/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_contract(order_id):
    """Create contract"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    # Only show active quotations (not canceled) - typically approved ones for contract
    quotations = [q for q in order.quotations if q.is_active and not q.is_canceled]
    
    if request.method == 'POST':
        try:
            # Check for duplicate contract number
            contract_number = request.form.get('contract_number', '').strip()
            from app.models.models import Contract
            from app.repositories.repository import ContractRepository as _ContractRepo
            existing = _ContractRepo().get_by_company_and_number(company_id, contract_number)
            if existing:
                flash(t(f'Contract number "{contract_number}" is already taken. Please use a different number.'), 'error')
                from app.models.models import Company as _CompanyC
                _co = db.session.get(_CompanyC, order.company_id)
                return render_template('contracts/create.html', order=order, quotations=quotations, company=_co)
            
            # Parse items from form
            items, subtotal = parse_line_items(request.form)

            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            # Shipping/other fees come from quotation when referenced
            shipping_fee = float(request.form.get('shipping_fee') or 0)
            another_fee = float(request.form.get('another_fee') or 0)
            contract_value = subtotal + vat_amount + shipping_fee + another_fee

            advance_percentage = float(request.form.get('advance_percentage') or 30)
            advance_amount = round(contract_value * advance_percentage / 100, 2)
            city = request.form.get('city', '').strip() or None

            # New fields
            amount_in_words = request.form.get('amount_in_words', '').strip() or None
            contract_start_date_str = request.form.get('contract_start_date', '').strip()
            contract_start_date = datetime.strptime(contract_start_date_str, '%Y-%m-%d').date() if contract_start_date_str else None
            selected_bank_index = int(request.form.get('selected_bank_index') or 0)
            num_date_notice_cancel = int(request.form.get('num_date_notice_cancel') or 7)
            contract_days_complete = int(request.form.get('contract_days_complete') or 30)

            contract_service = ContractService()
            
            # Create contract with items
            contract_repo = ContractRepository()
            
            quotation_id = request.form.get('quotation_id') or None
            
            # If items are provided from form, use them; otherwise try to copy from quotation
            if not items and quotation_id:
                quotation = QuotationRepository().get_by_id(quotation_id)
                if quotation and quotation.items:
                    items = list(quotation.items)
            
            ext_values = collect_extension_values(company_id, 'contract', request.form)
            contract = contract_repo.create(
                order_id=order_id,
                quotation_id=quotation_id,
                contract_number=request.form.get('contract_number', '').strip(),
                contract_date=datetime.strptime(request.form.get('contract_date'), '%Y-%m-%d').date(),
                city=city,
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                shipping_fee=shipping_fee,
                another_fee=another_fee,
                contract_value=contract_value,
                advance_percentage=advance_percentage,
                advance_amount=advance_amount,
                terms_and_conditions=request.form.get('terms_and_conditions', '').strip() or None,
                amount_in_words=amount_in_words,
                contract_start_date=contract_start_date,
                selected_bank_index=selected_bank_index,
                num_date_notice_cancel=num_date_notice_cancel,
                contract_days_complete=contract_days_complete,
            )
            
            # Update lifecycle
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            lifecycle.contract_created = True
            lifecycle.contract_created_at = datetime.utcnow()
            db.session.add(lifecycle)
            db.session.commit()
            
            apply_extension_values(contract, ext_values)
            db.session.commit()

            flash(t('Contract created successfully'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            flash(t('Error creating contract'), 'error')

    # Auto-select first approved quotation to pre-populate items
    selected_quotation = None
    approved_quotes = [q for q in quotations if q.is_approved]
    if approved_quotes:
        selected_quotation = approved_quotes[0]
    elif quotations:
        selected_quotation = quotations[0]

    from app.models.models import Company
    company = db.session.get(Company, order.company_id)

    return render_template('contracts/create.html', order=order, quotations=quotations,
                           selected_quotation=selected_quotation, company=company)


@dashboard_bp.route('/contracts/<contract_id>/view', methods=['GET'])
@login_required
def view_contract(contract_id):
    """View contract details"""
    company_id = get_current_company_id()
    
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash(t('Contract not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    from app.models.models import Company
    company = db.session.get(Company, contract.order.company_id)

    return render_template('contracts/view.html', contract=contract, order=contract.order, company=company)


@dashboard_bp.route('/contracts/<contract_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contract(contract_id):
    """Edit contract - only if not signed"""
    company_id = get_current_company_id()
    
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash(t('Contract not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if contract.is_signed:
        flash(t('Cannot edit a signed contract'), 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    
    if request.method == 'POST':
        try:
            from app.services.services import ContractService
            contract_service = ContractService()
            
            # Parse contract data
            terms_and_conditions = request.form.get('terms_and_conditions', '').strip() or None
            
            # Parse items from form
            items, subtotal = parse_line_items(request.form)

            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            shipping_fee = float(request.form.get('shipping_fee') or 0)
            another_fee = float(request.form.get('another_fee') or 0)
            contract_value = subtotal + vat_amount + shipping_fee + another_fee
            advance_percentage = float(request.form.get('advance_percentage') or 30)
            advance_amount = round(contract_value * advance_percentage / 100, 2)
            
            # New fields
            amount_in_words = request.form.get('amount_in_words', '').strip() or None
            contract_start_date_str = request.form.get('contract_start_date', '').strip()
            contract_start_date = datetime.strptime(contract_start_date_str, '%Y-%m-%d').date() if contract_start_date_str else None
            selected_bank_index = int(request.form.get('selected_bank_index') or 0)
            num_date_notice_cancel = int(request.form.get('num_date_notice_cancel') or 7)
            contract_days_complete = int(request.form.get('contract_days_complete') or 30)

            # Update contract
            contract.city = request.form.get('city', '').strip() or None
            contract.contract_value = contract_value
            contract.subtotal = subtotal
            contract.vat_rate = vat_rate
            contract.vat_amount = vat_amount
            contract.shipping_fee = shipping_fee
            contract.another_fee = another_fee
            contract.advance_percentage = advance_percentage
            contract.advance_amount = advance_amount
            contract.terms_and_conditions = terms_and_conditions
            contract.items = items
            contract.amount_in_words = amount_in_words
            contract.contract_start_date = contract_start_date
            contract.selected_bank_index = selected_bank_index
            contract.num_date_notice_cancel = num_date_notice_cancel
            contract.contract_days_complete = contract_days_complete
            contract.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash(t('Contract updated successfully'), 'success')
            return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
            
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            flash(t('Error updating contract'), 'error')
    
    from app.models.models import Company
    company = db.session.get(Company, contract.order.company_id)

    return render_template('contracts/edit.html', contract=contract, order=contract.order, company=company)


@dashboard_bp.route('/contracts/<contract_id>/sign', methods=['POST'])
@login_required
def sign_contract(contract_id):
    """Mark contract as signed"""
    company_id = get_current_company_id()
    
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash(t('Contract not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        contract_service = ContractService()
        contract_service.mark_signed(contract_id, contract.order_id)
        flash(t('Contract marked as signed'), 'success')
    except Exception as e:
        logger.error(f"Error signing contract: {str(e)}")
        flash(t('Error signing contract'), 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=contract.order_id))


@dashboard_bp.route('/contracts/<contract_id>/cancel', methods=['POST'])
@login_required
def cancel_contract(contract_id):
    """Cancel contract"""
    company_id = get_current_company_id()
    
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash(t('Contract not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not contract.can_cancel():
        flash(t('Contract cannot be canceled'), 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    
    try:
        canceled_reason = request.form.get('canceled_reason', '').strip()
        if not canceled_reason:
            flash(t('Cancellation reason is required'), 'error')
            return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
        
        # Cancel the contract
        contract.is_canceled = True
        contract.canceled_at = datetime.utcnow()
        contract.canceled_reason = canceled_reason
        contract.is_active = False
        db.session.commit()
        
        flash(t('Contract has been canceled successfully'), 'success')
        logger.info(f"Contract {contract.contract_number} canceled by user. Reason: {canceled_reason}")
    except Exception as e:
        logger.error(f"Error canceling contract: {str(e)}")
        db.session.rollback()
        flash(t('Error canceling contract'), 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=contract.order_id))


@dashboard_bp.route('/api/contracts/<contract_id>', methods=['GET'])
@login_required
def get_contract_api(contract_id):
    """Return contract data as JSON (used by payment form to load items)"""
    company_id = get_current_company_id()

    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)

    if not contract or str(contract.order.company_id) != str(company_id):
        return jsonify({'error': 'Contract not found or access denied'}), 404

    items = contract.items or []
    return jsonify({
        'id': str(contract.id),
        'contract_number': contract.contract_number,
        'items': items,
        'vat_rate': float(contract.vat_rate or 0),
        'advance_percentage': float(contract.advance_percentage or 0),
        'contract_value': float(contract.contract_value or 0),
    })


@dashboard_bp.route('/orders/<order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel order"""
    company_id = get_current_company_id()
    
    order_repo = OrderRepository()
    order = order_repo.get_by_id(order_id)
    
    if not order or str(order.company_id) != str(company_id):
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not order.can_cancel():
        flash(t('Order cannot be canceled'), 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))
    
    try:
        canceled_reason = request.form.get('canceled_reason', '').strip()
        if not canceled_reason:
            flash(t('Cancellation reason is required'), 'error')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
        
        # Cancel the order
        order.is_canceled = True
        order.canceled_at = datetime.utcnow()
        order.canceled_reason = canceled_reason
        db.session.commit()
        
        flash(t('Order has been canceled successfully'), 'success')
        logger.info(f"Order {order.order_code} canceled by user. Reason: {canceled_reason}")
    except Exception as e:
        logger.error(f"Error canceling order: {str(e)}")
        db.session.rollback()
        flash(t('Error canceling order'), 'error')
    
    return redirect(url_for('dashboard.list_orders'))


# ===== DELIVERY REPORTS =====

@dashboard_bp.route('/handover/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_handover(order_id):
    """Create handover record"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Check for duplicate report number
            report_number = request.form.get('report_number', '').strip()
            from app.models.models import HandoverRecord
            from app.repositories.repository import HandoverRecordRepository as _HandoverRepo
            existing = _HandoverRepo().get_by_company_and_number(company_id, report_number)
            if existing:
                flash(t(f'Handover record number "{report_number}" is already taken. Please use a different number.'), 'error')
                # Get contract items for re-render
                contract_items = []
                active_contracts = [c for c in order.contracts if c.is_active and not c.is_canceled]
                if active_contracts:
                    contract_items = active_contracts[0].items or []
                elif order.quotations:
                    approved_quotations = [q for q in order.quotations if q.is_approved and q.is_active]
                    if approved_quotations:
                        contract_items = approved_quotations[0].items or []
                active_contract_obj = next((c for c in order.contracts if c.is_active and not c.is_canceled), None)
                return render_template('handover/create.html', order=order, contract_items=contract_items,
                                       active_contract=active_contract_obj)

            # Parse items acceptance from form
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_delivered = request.form.getlist('item_delivered_qty[]')
            item_accepted = request.form.getlist('item_accepted_qty[]')
            item_statuses = request.form.getlist('item_status[]')
            item_reasons = request.form.getlist('item_reason[]')
            item_prices = request.form.getlist('item_price[]')
            item_images = request.files.getlist('item_image[]')
            
            subtotal = 0
            for i, name in enumerate(item_names):
                if name:
                    delivered_qty = float(item_delivered[i] or 0) if i < len(item_delivered) else 0
                    accepted_qty = float(item_accepted[i] or 0) if i < len(item_accepted) else 0
                    unit_price = float(item_prices[i] or 0) if i < len(item_prices) else 0
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    status = item_statuses[i] if i < len(item_statuses) else 'accepted'
                    reason = item_reasons[i].strip() if i < len(item_reasons) else ''
                    item_total = accepted_qty * unit_price
                    image_path = _save_item_image(item_images[i] if i < len(item_images) else None)
                    items.append({
                        'name': name,
                        'unit': unit,
                        'quantity': accepted_qty,
                        'unit_price': unit_price,
                        'delivered_qty': delivered_qty,
                        'accepted_qty': accepted_qty,
                        'total': item_total,
                        'status': status,
                        'rejection_reason': reason if status != 'accepted' else '',
                        'image_path': image_path
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            active_contract = next((c for c in order.contracts if c.is_active and not c.is_canceled), None)
            shipping_fee = float(getattr(active_contract, 'shipping_fee', 0) or 0)
            another_fee = float(getattr(active_contract, 'another_fee', 0) or 0)
            total_amount = subtotal + vat_amount + shipping_fee + another_fee
            
            ext_values = collect_extension_values(company_id, 'handover', request.form)
            handover_service = HandoverRecordService()
            handover = handover_service.create_handover_record(
                order_id=order_id,
                report_number=request.form.get('report_number', '').strip(),
                report_date=datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date(),
                handover_date=datetime.strptime(request.form.get('handover_date'), '%Y-%m-%d').date(),
                handover_location=request.form.get('handover_location', '').strip() or None,
                start_time=request.form.get('start_time', '').strip() or None,
                end_time=request.form.get('end_time', '').strip() or None,
                copies_count=int(request.form.get('copies_count') or 2),
                customer_representative=request.form.get('customer_representative', '').strip() or None,
                customer_representative_title=request.form.get('customer_representative_title', '').strip() or None,
                company_representative=request.form.get('company_representative', '').strip() or None,
                company_representative_title=request.form.get('company_representative_title', '').strip() or None,
                product_condition=request.form.get('product_condition', '').strip() or None,
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                shipping_fee=shipping_fee,
                another_fee=another_fee,
                total_amount=total_amount,
                notes=request.form.get('notes', '').strip() or None
            )
            
            apply_extension_values(handover, ext_values)
            db.session.commit()

            # Item 4: optionally create the final payment at the same time. Mirrors the
            # "skip advance" shortcut — confirm the handover and spin up a draft final
            # payment report from the handover items so the two documents are made together.
            if request.form.get('create_final_payment'):
                try:
                    handover_service.confirm_handover(handover.id, order_id)
                    _create_final_payment_from_handover(order_id, company_id, handover)
                    flash(t('Handover record and final payment created successfully'), 'success')
                except Exception as e:
                    logger.error(f"Error creating combined final payment: {str(e)}")
                    flash(t('Handover created, but final payment could not be created automatically'), 'warning')
                return redirect(url_for('dashboard.view_order', order_id=order_id))

            flash(t('Handover record created successfully'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating handover record: {str(e)}")
            flash(t('Error creating handover record'), 'error')
    
    # Get contract items for handover item acceptance
    contract_items = []
    active_contracts = [c for c in order.contracts if c.is_active and not c.is_canceled]
    if active_contracts:
        contract_items = active_contracts[0].items or []
    elif order.quotations:
        approved_quotations = [q for q in order.quotations if q.is_approved and q.is_active]
        if approved_quotations:
            contract_items = approved_quotations[0].items or []
    
    active_contract = active_contracts[0] if active_contracts else None
    return render_template('handover/create.html', order=order, contract_items=contract_items,
                           active_contract=active_contract)


@dashboard_bp.route('/handover/<handover_id>/confirm', methods=['POST'])
@login_required
def confirm_handover(handover_id):
    """Mark handover as confirmed"""
    company_id = get_current_company_id()
    
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash(t('Handover record not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        handover_service.confirm_handover(handover_id, handover.order_id)
        flash(t('Handover record confirmed'), 'success')
    except Exception as e:
        logger.error(f"Error confirming handover: {str(e)}")
        flash(t('Error confirming handover'), 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=handover.order_id))


@dashboard_bp.route('/handover/<handover_id>', methods=['GET'])
@login_required
def view_handover(handover_id):
    """View handover record details"""
    company_id = get_current_company_id()
    
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash(t('Handover record not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('handover/view.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_handover(handover_id):
    """Edit handover record"""
    company_id = get_current_company_id()
    
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash(t('Handover record not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not handover.can_edit():
                flash(t('Handover record cannot be edited (already confirmed or canceled)'), 'error')
                return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
            # Update handover fields
            handover.report_number = request.form.get('report_number', '').strip()
            handover.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
            handover.handover_date = datetime.strptime(request.form.get('handover_date'), '%Y-%m-%d').date()
            handover.handover_location = request.form.get('handover_location', '').strip() or None
            handover.start_time = request.form.get('start_time', '').strip() or None
            handover.end_time = request.form.get('end_time', '').strip() or None
            handover.copies_count = int(request.form.get('copies_count') or 2)
            handover.company_representative = request.form.get('company_representative', '').strip() or None
            handover.company_representative_title = request.form.get('company_representative_title', '').strip() or None
            handover.customer_representative = request.form.get('customer_representative', '').strip() or None
            handover.customer_representative_title = request.form.get('customer_representative_title', '').strip() or None
            handover.product_condition = request.form.get('product_condition', '').strip() or None
            handover.notes = request.form.get('notes', '').strip() or None
            handover.updated_at = datetime.utcnow()
            
            # Parse items acceptance data
            item_names = request.form.getlist('item_name[]')
            if item_names:
                item_units = request.form.getlist('item_unit[]')
                item_prices = request.form.getlist('item_price[]')
                item_delivered = request.form.getlist('item_delivered_qty[]')
                item_accepted = request.form.getlist('item_accepted_qty[]')
                item_statuses = request.form.getlist('item_status[]')
                item_reasons = request.form.getlist('item_reason[]')
                item_images = request.files.getlist('item_image[]')
                item_existing_images = request.form.getlist('item_existing_image[]')
                
                items = []
                subtotal = 0
                for i, name in enumerate(item_names):
                    if name.strip():
                        delivered_qty = float(item_delivered[i]) if i < len(item_delivered) and item_delivered[i] else 0
                        accepted_qty = float(item_accepted[i]) if i < len(item_accepted) and item_accepted[i] else 0
                        unit_price = float(item_prices[i]) if i < len(item_prices) and item_prices[i] else 0
                        unit = item_units[i].strip() if i < len(item_units) else ''
                        item_total = unit_price * accepted_qty
                        existing = item_existing_images[i] if i < len(item_existing_images) else None
                        image_path = _save_item_image(item_images[i] if i < len(item_images) else None, existing)
                        items.append({
                            'name': name.strip(),
                            'unit': unit,
                            'unit_price': unit_price,
                            'quantity': accepted_qty,
                            'total': item_total,
                            'delivered_qty': delivered_qty,
                            'accepted_qty': accepted_qty,
                            'accepted': item_statuses[i] == 'accepted' if i < len(item_statuses) else True,
                            'status': item_statuses[i] if i < len(item_statuses) else 'accepted',
                            'rejection_reason': item_reasons[i].strip() if i < len(item_reasons) and item_reasons[i].strip() else None,
                            'image_path': image_path
                        })
                        subtotal += item_total
                handover.items = items
                vat_rate = float(request.form.get('vat_rate') or 8)
                vat_amount = round(subtotal * vat_rate / 100, 2)
                handover.subtotal = subtotal
                handover.vat_rate = vat_rate
                handover.vat_amount = vat_amount
                ship_fee = float(handover.shipping_fee or 0)
                other_fee = float(handover.another_fee or 0)
                handover.total_amount = subtotal + vat_amount + ship_fee + other_fee
            
            db.session.add(handover)
            db.session.commit()
            
            flash(t('Handover record updated successfully'), 'success')
            return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
        except ValueError as e:
            flash(t(f'Error: {str(e)}'), 'error')
        except Exception as e:
            logger.error(f"Error updating handover record: {str(e)}")
            flash(t('Error updating handover record'), 'error')
    
    return render_template('handover/edit.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/cancel', methods=['POST'])
@login_required
def cancel_handover(handover_id):
    """Cancel handover record"""
    company_id = get_current_company_id()
    
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash(t('Handover record not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        reason = request.form.get('reason', '').strip()
        handover_service.cancel_handover(handover_id, handover.order_id, reason)
        flash(t('Handover record canceled successfully'), 'success')
    except Exception as e:
        logger.error(f"Error canceling handover: {str(e)}")
        flash(t(f'Error canceling handover: {str(e)}'), 'error')
    
    return redirect(url_for('dashboard.view_handover', handover_id=handover_id))


# ===== PAYMENT REPORTS =====

@dashboard_bp.route('/payment/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_payment(order_id):
    """Create payment report"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    # Get default payment type from query parameter (advance or final)
    default_type = request.args.get('type', 'advance')

    # Get active contract and company bank accounts for reference
    from app.models.models import Company as _Company
    active_contract = next((c for c in order.contracts if c.is_active and not c.is_canceled), None)
    company = db.session.get(_Company, company_id)

    if request.method == 'POST':
        try:
            # Check for duplicate report number
            report_number = request.form.get('report_number', '').strip()
            from app.models.models import PaymentReport
            from app.repositories.repository import PaymentReportRepository as _PaymentRepo
            existing = _PaymentRepo().get_by_company_and_number(company_id, report_number)
            if existing:
                flash(t(f'Payment report number "{report_number}" is already taken. Please use a different number.'), 'error')
                from app.models.models import PaymentReport as _PR
                _adv = db.session.query(_PR).filter(_PR.order_id==order_id, _PR.payment_type=='advance', _PR.is_confirmed==True, _PR.is_canceled==False).all()
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company,
                                       confirmed_advance_payments=_adv,
                                       confirmed_advance_total=float(sum(p.advance_amount or 0 for p in _adv)),
                                       advance_skipped=bool(order.lifecycle and order.lifecycle.advance_skipped))

            payment_service = PaymentReportService()
            payment_type = request.form.get('payment_type')
            
            # Validate payment sequencing
            if payment_type == 'advance' and not order.lifecycle.contract_signed:
                flash(t('Advance payment can only be recorded after contract is signed'), 'error')
                from app.models.models import PaymentReport as _PR2
                _adv2 = db.session.query(_PR2).filter(_PR2.order_id==order_id, _PR2.payment_type=='advance', _PR2.is_confirmed==True, _PR2.is_canceled==False).all()
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company,
                                       confirmed_advance_payments=_adv2,
                                       confirmed_advance_total=float(sum(p.advance_amount or 0 for p in _adv2)),
                                       advance_skipped=bool(order.lifecycle and order.lifecycle.advance_skipped))

            if payment_type == 'final' and not order.lifecycle.handover_confirmed:
                flash(t('Final payment can only be recorded after handover is confirmed'), 'error')
                from app.models.models import PaymentReport as _PR3
                _adv3 = db.session.query(_PR3).filter(_PR3.order_id==order_id, _PR3.payment_type=='advance', _PR3.is_confirmed==True, _PR3.is_canceled==False).all()
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company,
                                       confirmed_advance_payments=_adv3,
                                       confirmed_advance_total=float(sum(p.advance_amount or 0 for p in _adv3)),
                                       advance_skipped=bool(order.lifecycle and order.lifecycle.advance_skipped))
            
            # Parse work items
            items, subtotal = parse_line_items(request.form)

            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            shipping_fee = float(getattr(active_contract, 'shipping_fee', 0) or 0)
            another_fee = float(getattr(active_contract, 'another_fee', 0) or 0)
            base_amount = subtotal + vat_amount if items else float(request.form.get('amount') or 0)
            amount = base_amount + shipping_fee + another_fee
            
            advance_pct = request.form.get('advance_percentage')
            advance_percentage = float(advance_pct) if advance_pct else None
            advance_amount = float(request.form.get('advance_amount') or 0)
            remaining_amount = amount - advance_amount
            
            # Parse bank accounts JSON from hidden field
            import json as _json
            bank_json = request.form.get('bank_account_info', '[]')
            try:
                bank_account_info = _json.loads(bank_json)
            except Exception:
                bank_account_info = []
            
            # Parse quot ref date
            quot_ref_str = request.form.get('quotation_reference_date', '').strip()
            quot_ref_date = datetime.strptime(quot_ref_str, '%Y-%m-%d').date() if quot_ref_str else None
            
            ext_values = collect_extension_values(company_id, 'payment', request.form)
            payment = payment_service.create_payment_report(
                order_id=order_id,
                report_number=request.form.get('report_number', '').strip(),
                payment_type=payment_type,
                report_date=datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date(),
                payment_date=datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date(),
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                shipping_fee=shipping_fee,
                another_fee=another_fee,
                amount=amount,
                advance_percentage=advance_percentage,
                advance_amount=advance_amount,
                remaining_amount=remaining_amount,
                amount_in_words=request.form.get('amount_in_words', '').strip() or None,
                work_completed_summary=request.form.get('work_completed_summary', '').strip() or None,
                quotation_reference_date=quot_ref_date,
                bank_account_info=bank_account_info,
                payment_method=request.form.get('payment_method', '').strip() or None,
                transaction_reference=request.form.get('transaction_reference', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            apply_extension_values(payment, ext_values)
            db.session.commit()

            flash(t('Payment report created successfully'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(t(f'Error: {str(e)}'), 'error')
        except Exception as e:
            logger.error(f"Error creating payment report: {str(e)}")
            flash(t('Error creating payment report'), 'error')
    
    # Compute confirmed advance payments for final payment advance display
    from app.models.models import PaymentReport as _PaymentReport
    confirmed_advance_payments = db.session.query(_PaymentReport).filter(
        _PaymentReport.order_id == order_id,
        _PaymentReport.payment_type == 'advance',
        _PaymentReport.is_confirmed == True,
        _PaymentReport.is_canceled == False
    ).all()
    confirmed_advance_total = float(sum(p.advance_amount or 0 for p in confirmed_advance_payments))
    advance_skipped = bool(order.lifecycle and order.lifecycle.advance_skipped)

    return render_template('payment/create.html', order=order, default_type=default_type,
                           active_contract=active_contract, company=company,
                           confirmed_advance_payments=confirmed_advance_payments,
                           confirmed_advance_total=confirmed_advance_total,
                           advance_skipped=advance_skipped)


@dashboard_bp.route('/order/<order_id>/skip-advance', methods=['POST'])
@login_required
def skip_advance_payment(order_id):
    """Skip advance payment step and go directly to handover"""
    company_id = get_current_company_id()
    order_service = OrderService()

    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    if not order.lifecycle or not order.lifecycle.contract_signed:
        flash(t('Contract must be signed before skipping advance payment'), 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    if order.lifecycle.advance_paid:
        flash(t('Advance payment step already completed'), 'warning')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    try:
        lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
        lifecycle.advance_skipped = True
        lifecycle.advance_skipped_at = datetime.utcnow()
        # Set advance_paid = True so the rest of the workflow (handover, final payment) unlocks
        lifecycle.advance_paid = True
        lifecycle.advance_paid_at = datetime.utcnow()
        db.session.add(lifecycle)
        db.session.commit()
        flash(t('Đã bỏ qua bước tạm ứng. Bạn có thể tạo chứng từ bàn giao ngay bây giờ.'), 'success')
    except Exception as e:
        logger.error(f'Error skipping advance payment: {e}')
        db.session.rollback()
        flash(t('Lỗi khi bỏ qua tạm ứng'), 'error')

    return redirect(url_for('dashboard.view_order', order_id=order_id))


@dashboard_bp.route('/payment/<payment_id>/confirm', methods=['POST'])
@login_required
def confirm_payment(payment_id):
    """Mark payment as confirmed"""
    company_id = get_current_company_id()
    
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash(t('Payment report not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        # Optional proof of received payment (image/PDF) uploaded from the confirm popup
        proof = request.files.get('proof_file')
        proof_path = _save_item_image(proof) if (proof and proof.filename) else None

        payment_service = PaymentReportService()
        payment_service.mark_confirmed(payment_id, payment.order_id)
        if proof_path:
            payment.proof_path = proof_path
            db.session.add(payment)
            db.session.commit()
        flash(t('Payment marked as confirmed'), 'success')
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        flash(t('Error confirming payment'), 'error')

    return redirect(url_for('dashboard.view_order', order_id=payment.order_id))


@dashboard_bp.route('/payment/<payment_id>', methods=['GET'])
@login_required
def view_payment(payment_id):
    """View payment report details"""
    company_id = get_current_company_id()
    
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash(t('Payment report not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('payments/view.html', payment=payment)


@dashboard_bp.route('/payment/<payment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    """Edit payment report"""
    company_id = get_current_company_id()
    
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash(t('Payment report not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not payment.can_edit():
                flash(t('Payment cannot be edited (already confirmed or canceled)'), 'error')
                return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
            import json as _json

            bank_json = request.form.get('bank_account_info', '[]')
            try:
                bank_account_info = _json.loads(bank_json)
            except Exception:
                bank_account_info = []

            quot_ref_str = request.form.get('quotation_reference_date', '').strip()
            quot_ref_date = datetime.strptime(quot_ref_str, '%Y-%m-%d').date() if quot_ref_str else None

            # Update only editable fields; items/financials are locked to contract values
            payment.report_number = request.form.get('report_number', '').strip()
            payment.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
            payment.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            payment.quotation_reference_date = quot_ref_date
            payment.payment_method = request.form.get('payment_method', '').strip() or None
            payment.amount_in_words = request.form.get('amount_in_words', '').strip() or None
            payment.work_completed_summary = request.form.get('work_completed_summary', '').strip() or None
            payment.bank_account_info = bank_account_info
            payment.transaction_reference = request.form.get('transaction_reference', '').strip() or None
            payment.notes = request.form.get('notes', '').strip() or None
            payment.updated_at = datetime.utcnow()
            
            db.session.add(payment)
            db.session.commit()
            
            flash(t('Payment report updated successfully'), 'success')
            return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
        except ValueError as e:
            flash(t(f'Error: {str(e)}'), 'error')
        except Exception as e:
            logger.error(f"Error updating payment report: {str(e)}")
            flash(t('Error updating payment report'), 'error')
    
    from app.models.models import Company
    company = db.session.get(Company, payment.order.company_id)
    return render_template('payments/edit.html', payment=payment, company=company)


@dashboard_bp.route('/payment/<payment_id>/cancel', methods=['POST'])
@login_required
def cancel_payment(payment_id):
    """Cancel payment report"""
    company_id = get_current_company_id()
    
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash(t('Payment report not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        payment_service = PaymentReportService()
        reason = request.form.get('reason', '').strip()
        payment_service.cancel_payment(payment_id, payment.order_id, reason)
        flash(t('Payment report canceled successfully'), 'success')
    except Exception as e:
        logger.error(f"Error canceling payment: {str(e)}")
        flash(t(f'Error canceling payment: {str(e)}'), 'error')
    
    return redirect(url_for('dashboard.view_payment', payment_id=payment_id))


# ===== DOCUMENTS =====

@dashboard_bp.route('/documents/generate/<doc_type>/<ref_id>', methods=['POST'])
@login_required
def generate_document(doc_type, ref_id):
    """Generate document"""
    company_id = get_current_company_id()
    document_service = DocumentService()
    doc_format = request.form.get('format', 'pdf')
    
    try:
        if doc_type == 'quotation':
            quotation = QuotationRepository().get_by_id(ref_id)
            if not quotation or str(quotation.order.company_id) != str(company_id):
                flash(t('Quotation not found'), 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_quotation_document(ref_id, quotation.order_id, company_id, doc_format)
        
        elif doc_type == 'contract':
            contract = ContractRepository().get_by_id(ref_id)
            if not contract or str(contract.order.company_id) != str(company_id):
                flash(t('Contract not found'), 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_contract_document(
                ref_id, contract.order_id, company_id, 
                quotation_id=contract.quotation_id, format=doc_format
            )
        
        elif doc_type == 'handover':
            handover = HandoverRecordRepository().get_by_id(ref_id)
            if not handover or str(handover.order.company_id) != str(company_id):
                flash(t('Handover record not found'), 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_delivery_document(ref_id, handover.order_id, company_id, doc_format)
        
        elif doc_type == 'payment':
            payment = PaymentReportRepository().get_by_id(ref_id)
            if not payment or str(payment.order.company_id) != str(company_id):
                flash(t('Payment report not found'), 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_payment_document(ref_id, payment.order_id, company_id, doc_format)
            
        elif doc_type == 'payment_request':
            order = OrderRepository().get_by_id(ref_id)
            if not order or str(order.company_id) != str(company_id):
                flash(t('Order not found'), 'error')
                return redirect(request.referrer)
                
            document = document_service.generate_payment_request_document(ref_id, company_id, doc_format)
        
        else:
            flash(t('Unknown document type'), 'error')
            return redirect(request.referrer)

        # Tell the user the real output format. If PDF was requested but the
        # DOCX→PDF conversion was unavailable, the service falls back to DOCX —
        # surface that instead of a misleading "success".
        actual = getattr(document, 'document_format', doc_format)
        if doc_format == 'pdf' and actual != 'pdf':
            flash(t('Đã tạo tài liệu nhưng không chuyển được sang PDF — đã lưu dạng DOCX.'), 'warning')
        else:
            flash(t('Đã tạo tài liệu (%(fmt)s) thành công.') % {'fmt': actual.upper()}, 'success')
        
    except Exception as e:
        logger.error(f"Error generating document: {str(e)}")
        flash(t(f'Error generating document: {str(e)}'), 'error')
    
    return redirect(request.referrer)


@dashboard_bp.route('/documents/<document_id>/download')
@login_required
def download_document(document_id):
    """Download document"""
    company_id = get_current_company_id()
    doc_repo = DocumentRepository()
    
    document = doc_repo.get_by_id(document_id)
    if not document or str(document.company_id) != str(company_id):
        flash(t('Document not found or access denied'), 'error')
        return redirect(request.referrer)
    
    if not os.path.exists(document.file_path):
        flash(t('Document file not found'), 'error')
        return redirect(request.referrer)
    
    try:
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=f"{document.document_name}.{document.document_format}"
        )
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        flash(t('Error downloading document'), 'error')
        return redirect(request.referrer)


@dashboard_bp.route('/uploads/items/<path:filename>')
@login_required
def serve_item_image(filename):
    """Serve uploaded item images."""
    items_folder = current_app.config['ITEMS_FOLDER']
    # Prevent path traversal: ensure the resolved path stays within items_folder
    safe_path = os.path.realpath(os.path.join(items_folder, filename))
    if not safe_path.startswith(os.path.realpath(items_folder) + os.sep):
        abort(403)
    if not os.path.exists(safe_path):
        abort(404)
    return send_file(safe_path)


@dashboard_bp.route('/documents/<order_id>')
@login_required
def list_documents(order_id):
    """List documents for order"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    doc_service = DocumentService()
    documents = doc_service.list_documents_for_order(order_id)
    
    return render_template('documents/list.html', order=order, documents=documents)


@dashboard_bp.route('/documents/delete/<document_id>', methods=['POST'])
@login_required
def delete_document(document_id):
    """Delete a generated document record and its file."""
    company_id = get_current_company_id()

    from app.repositories.repository import DocumentRepository as _DocRepo
    doc_repo = _DocRepo()
    document = doc_repo.get_by_id(document_id)

    if not document or str(document.company_id) != str(company_id):
        flash(t('Document not found or access denied'), 'error')
        return redirect(request.referrer or url_for('dashboard.list_orders'))

    order_id = document.order_id
    try:
        # Remove file from disk if it still exists
        if document.file_path and os.path.exists(document.file_path):
            os.remove(document.file_path)
        db.session.delete(document)
        db.session.commit()
        flash(t('Document deleted successfully'), 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        flash(t('Error deleting document'), 'error')

    return redirect(url_for('dashboard.list_documents', order_id=order_id))
@login_required
def get_contract_detail(contract_id):
    """Get contract details as JSON - for AJAX calls"""
    company_id = get_current_company_id()
    try:
        contract = ContractRepository().get_by_id(contract_id)
        if not contract or str(contract.order.company_id) != str(company_id):
            return {'error': 'Contract not found'}, 404
        items = contract.items if isinstance(contract.items, list) else []
        return {
            'id': str(contract.id),
            'contract_number': contract.contract_number,
            'contract_value': float(contract.contract_value),
            'subtotal': float(contract.subtotal or 0),
            'vat_rate': float(contract.vat_rate or 8),
            'vat_amount': float(contract.vat_amount or 0),
            'advance_percentage': float(contract.advance_percentage or 30),
            'advance_amount': float(contract.advance_amount or 0),
            'items': items,
        }, 200
    except Exception as e:
        logger.error(f"Error getting contract detail {contract_id}: {str(e)}", exc_info=True)
        return {'error': str(e)}, 500


@dashboard_bp.route('/api/quotations/<quotation_id>')
@login_required
def get_quotation_detail(quotation_id):
    """Get quotation details as JSON - for AJAX calls"""
    company_id = get_current_company_id()
    
    try:
        quotation_repo = QuotationRepository()
        quotation = quotation_repo.get_by_id(quotation_id)
        
        if not quotation or str(quotation.order.company_id) != str(company_id):
            logger.warning(f"Quotation {quotation_id} not found or access denied")
            return {'error': 'Quotation not found'}, 404
        
        # Build items list - ensure it's always a list
        items = []
        if quotation.items:
            if isinstance(quotation.items, list):
                items = quotation.items
            elif isinstance(quotation.items, dict):
                items = list(quotation.items.values())
        
        logger.info(f"Quotation {quotation_id}: {len(items)} items, total: {quotation.total_amount}")
        
        # Return quotation details as JSON  
        response = {
            'id': str(quotation.id),
            'quotation_number': quotation.quotation_number,
            'total_amount': float(quotation.total_amount),
            'vat_rate': float(getattr(quotation, 'vat_rate', 8) or 8),
            'shipping_fee': float(getattr(quotation, 'shipping_fee', 0) or 0),
            'another_fee': float(getattr(quotation, 'another_fee', 0) or 0),
            'items': items,
            'is_approved': quotation.is_approved,
            'is_canceled': quotation.is_canceled
        }
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Error getting quotation detail for {quotation_id}: {str(e)}", exc_info=True)
        return {'error': f'Error: {str(e)}'}, 500


@dashboard_bp.route('/api/next-code/<doc_type>')
@login_required
def get_next_code(doc_type):
    """Get next available code for document type"""
    company_id = get_current_company_id()
    
    try:
        from app.repositories.repository import (
            QuotationRepository, ContractRepository, PaymentReportRepository,
            HandoverRecordRepository, CustomerRepository, OrderRepository
        )
        from sqlalchemy import func

        # Map document type to repository and field
        type_config = {
            'quotation': {
                'repo': QuotationRepository(),
                'field': 'quotation_number',
                'prefix': 'QT-'
            },
            'contract': {
                'repo': ContractRepository(),
                'field': 'contract_number',
                'prefix': 'CT-'
            },
            'payment': {
                'repo': PaymentReportRepository(),
                'field': 'report_number',
                'prefix': 'PR-'
            },
            'handover': {
                'repo': HandoverRecordRepository(),
                'field': 'report_number',
                'prefix': 'HR-'
            },
            'customer': {
                'repo': CustomerRepository(),
                'field': 'customer_code',
                'prefix': 'CUST-'
            },
            'order': {
                'repo': OrderRepository(),
                'field': 'order_code',
                'prefix': 'ORD-'
            }
        }
        
        if doc_type not in type_config:
            return {'error': 'Invalid document type'}, 400
        
        config = type_config[doc_type]
        model_class = config['repo'].model
        field_name = config['field']
        prefix = config['prefix']
        
        # Get the highest number for this type
        result = db.session.query(
            func.max(func.cast(
                func.regexp_replace(
                    getattr(model_class, field_name),
                    f'^{prefix}',
                    ''
                ),
                db.Integer
            ))
        ).filter(
            getattr(model_class, field_name).like(f'{prefix}%')
        ).scalar()
        
        next_number = (result or 0) + 1
        next_code = f'{prefix}{next_number:03d}'
        
        return {'next_code': next_code}, 200
        
    except Exception as e:
        logger.error(f"Error getting next code for {doc_type}: {str(e)}", exc_info=True)
        return {'error': f'Error: {str(e)}'}, 500


@dashboard_bp.route('/api/check-code/<doc_type>', methods=['POST'])
@login_required
def check_code(doc_type):
    """Check if code already exists"""
    company_id = get_current_company_id()
    
    try:
        code = request.json.get('code', '').strip()
        if not code:
            return {'exists': False}, 200
        
        from app.repositories.repository import (
            QuotationRepository, ContractRepository, PaymentReportRepository,
            HandoverRecordRepository, CustomerRepository, OrderRepository
        )
        
        # Map document type to repository and field
        type_config = {
            'quotation': {
                'repo': QuotationRepository(),
                'field': 'quotation_number'
            },
            'contract': {
                'repo': ContractRepository(),
                'field': 'contract_number'
            },
            'payment': {
                'repo': PaymentReportRepository(),
                'field': 'report_number'
            },
            'handover': {
                'repo': HandoverRecordRepository(),
                'field': 'report_number'
            },
            'customer': {
                'repo': CustomerRepository(),
                'field': 'customer_code'
            },
            'order': {
                'repo': OrderRepository(),
                'field': 'order_code'
            }
        }
        
        if doc_type not in type_config:
            return {'error': 'Invalid document type'}, 400
        
        config = type_config[doc_type]
        model_class = config['repo'].model
        field_name = config['field']
        
        # Check if code exists
        exists = db.session.query(model_class).filter(
            getattr(model_class, field_name) == code
        ).first() is not None
        
        return {'exists': exists}, 200
        
    except Exception as e:
        logger.error(f"Error checking code for {doc_type}: {str(e)}", exc_info=True)
        return {'error': f'Error: {str(e)}'}, 500


# =====================================================================
# STORE MANAGEMENT  (company_admin: all stores; store_admin: own store)
# =====================================================================

@dashboard_bp.route('/stores', methods=['GET'])
@store_admin_required
def list_stores():
    """List stores — company_admin sees all; store_admin sees only their own."""
    company_id = get_current_company_id()
    store_svc  = StoreService()
    user_svc   = UserService()

    if is_company_admin():
        stores = store_svc.list_stores_for_company(company_id)
    else:
        from app.models.models import Store as _Store
        own_id = get_current_store_id()
        own    = db.session.query(_Store).filter_by(id=own_id, company_id=company_id, is_active=True).first()
        stores = [own] if own else []

    for s in stores:
        s._user_count = len(user_svc.list_users_for_store(s.id))
    return render_template('stores/list.html', stores=stores)


@dashboard_bp.route('/stores/create', methods=['GET', 'POST'])
@company_admin_required
def create_store():
    """Create a new store"""
    company_id = get_current_company_id()
    if request.method == 'POST':
        try:
            store_svc = StoreService()
            store_svc.create_store(
                company_id   = company_id,
                store_code   = request.form.get('store_code', '').strip(),
                name         = request.form.get('name', '').strip(),
                manager_name = request.form.get('manager_name', '').strip() or None,
                phone        = request.form.get('phone', '').strip() or None,
                address      = request.form.get('address', '').strip() or None,
                city         = request.form.get('city', '').strip() or None,
            )
            flash(t('Tạo cửa hàng thành công'), 'success')
            return redirect(url_for('dashboard.list_stores'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating store: {e}", exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi tạo cửa hàng'), 'error')
    return render_template('stores/create.html')


@dashboard_bp.route('/stores/<store_id>/edit', methods=['GET', 'POST'])
@store_admin_required
def edit_store(store_id):
    """Edit store details — store_admin may only edit their own store."""
    company_id = get_current_company_id()
    from app.models.models import Store as _Store
    store = db.session.query(_Store).filter_by(id=store_id, company_id=company_id, is_active=True).first()
    if not store:
        flash(t('Cửa hàng không tìm thấy'), 'error')
        return redirect(url_for('dashboard.list_stores'))

    # store_admin may only edit their own store
    if not is_company_admin() and str(store_id) != str(get_current_store_id()):
        abort(403)

    if request.method == 'POST':
        try:
            store_svc = StoreService()
            store_svc.update_store(
                store_id     = store_id,
                name         = request.form.get('name', '').strip() or None,
                # empty strings pass through so clearing an optional field saves it
                manager_name = request.form.get('manager_name', '').strip(),
                phone        = request.form.get('phone', '').strip(),
                address      = request.form.get('address', '').strip(),
                city         = request.form.get('city', '').strip(),
            )
            flash(t('Cập nhật cửa hàng thành công'), 'success')
            return redirect(url_for('dashboard.list_stores'))
        except Exception as e:
            logger.error(f"Error updating store: {e}", exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi cập nhật cửa hàng'), 'error')
    return render_template('stores/edit.html', store=store)


@dashboard_bp.route('/stores/<store_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_store(store_id):
    """Deactivate a store"""
    company_id = get_current_company_id()
    from app.models.models import Store as _Store
    store = db.session.query(_Store).filter_by(id=store_id, company_id=company_id).first()
    if not store:
        flash(t('Cửa hàng không tìm thấy'), 'error')
    else:
        try:
            StoreService().deactivate_store(store_id)
            flash(t(f'Cửa hàng "{store.name}" đã bị vô hiệu hóa'), 'warning')
        except Exception as e:
            logger.error(f"Error deactivating store: {e}", exc_info=True)
            flash(t('Lỗi khi vô hiệu hóa cửa hàng'), 'error')
    return redirect(url_for('dashboard.list_stores'))


# =====================================================================
# USER MANAGEMENT  (company_admin: all users; store_admin: own store)
# =====================================================================

@dashboard_bp.route('/users', methods=['GET'])
@store_admin_required
def list_users():
    """List users — company_admin sees all; store_admin sees their store only."""
    company_id = get_current_company_id()
    user_svc   = UserService()
    store_svc  = StoreService()

    if is_company_admin():
        users  = user_svc.list_users_for_company(company_id)
        stores = store_svc.list_stores_for_company(company_id)
    else:
        own_id = get_current_store_id()
        users  = user_svc.list_users_for_store(own_id) if own_id else []
        from app.models.models import Store as _Store
        own_store = db.session.query(_Store).filter_by(id=own_id, company_id=company_id).first()
        stores = [own_store] if own_store else []

    store_map = {str(s.id): s.name for s in stores}
    return render_template('users/list.html', users=users, stores=stores, store_map=store_map)


@dashboard_bp.route('/users/create', methods=['GET', 'POST'])
@store_admin_required
def create_user():
    """Create a new user — store_admin may only create users for their own store."""
    company_id = get_current_company_id()
    store_svc  = StoreService()

    if is_company_admin():
        stores = store_svc.list_stores_for_company(company_id)
    else:
        own_id = get_current_store_id()
        from app.models.models import Store as _Store
        own_store = db.session.query(_Store).filter_by(id=own_id, company_id=company_id).first()
        stores = [own_store] if own_store else []

    if request.method == 'POST':
        try:
            role     = request.form.get('role', 'user').strip()
            store_id = request.form.get('store_id', '').strip() or None
            # Prevent store_admin from creating company_admin accounts
            if not is_company_admin() and role == 'company_admin':
                flash(t('Không có quyền tạo tài khoản Quản Trị Công Ty'), 'error')
                return render_template('users/create.html', stores=stores)
            # company_admin must not have a store_id
            if role == 'company_admin':
                store_id = None
            # store_admin always creates inside their own store
            if not is_company_admin():
                store_id = get_current_store_id()
            from app.models.models import FEATURE_KEYS
            feats = [f for f in request.form.getlist('features') if f in FEATURE_KEYS]
            UserService().create_user(
                company_id = company_id,
                username   = request.form.get('username', '').strip(),
                email      = request.form.get('email', '').strip(),
                password   = request.form.get('password', ''),
                full_name  = request.form.get('full_name', '').strip(),
                role       = role,
                store_id   = uuid.UUID(str(store_id)) if store_id else None,
                phone      = request.form.get('phone', '').strip() or None,
                position   = request.form.get('position', '').strip() or None,
                allowed_features = feats,
            )
            flash(t('Tạo người dùng thành công'), 'success')
            return redirect(url_for('dashboard.list_users'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi tạo người dùng'), 'error')
    from app.models.models import FEATURE_LABELS
    return render_template('users/create.html', stores=stores, feature_labels=FEATURE_LABELS)


@dashboard_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@store_admin_required
def edit_user(user_id):
    """Edit user profile / role / store assignment — store_admin may only edit users in their store."""
    company_id = get_current_company_id()
    from app.models.models import User as _User
    target = db.session.query(_User).filter_by(id=user_id, company_id=company_id, is_active=True).first()
    if not target:
        flash(t('Người dùng không tìm thấy'), 'error')
        return redirect(url_for('dashboard.list_users'))

    # store_admin can only edit users in their own store
    if not is_company_admin() and str(target.store_id) != str(get_current_store_id()):
        abort(403)

    store_svc = StoreService()
    if is_company_admin():
        stores = store_svc.list_stores_for_company(company_id)
    else:
        own_id = get_current_store_id()
        from app.models.models import Store as _Store
        own_store = db.session.query(_Store).filter_by(id=own_id, company_id=company_id).first()
        stores = [own_store] if own_store else []

    if request.method == 'POST':
        try:
            role     = request.form.get('role', target.role).strip()
            store_id = request.form.get('store_id', '').strip() or None
            # Prevent store_admin from promoting to company_admin
            if not is_company_admin() and role == 'company_admin':
                flash(t('Không có quyền thiết lập vai trò Quản Trị Công Ty'), 'error')
                return render_template('users/edit.html', target=target, stores=stores)
            if role == 'company_admin':
                store_id = None
            # store_admin always keeps the user in their own store
            if not is_company_admin():
                store_id = get_current_store_id()
            password = request.form.get('password', '').strip() or None
            from app.models.models import FEATURE_KEYS
            feats = [f for f in request.form.getlist('features') if f in FEATURE_KEYS]
            UserService().update_user(
                user_id   = user_id,
                full_name = request.form.get('full_name', '').strip() or None,
                email     = request.form.get('email', '').strip() or None,
                phone     = request.form.get('phone', '').strip() or None,
                position  = request.form.get('position', '').strip() or None,
                role      = role,
                store_id  = uuid.UUID(str(store_id)) if store_id else None,
                password  = password,
                allowed_features = feats,
            )
            flash(t('Cập nhật người dùng thành công'), 'success')
            return redirect(url_for('dashboard.list_users'))
        except Exception as e:
            logger.error(f"Error updating user: {e}", exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi cập nhật người dùng'), 'error')
    from app.models.models import FEATURE_LABELS
    return render_template('users/edit.html', target=target, stores=stores, feature_labels=FEATURE_LABELS)


@dashboard_bp.route('/users/<user_id>/deactivate', methods=['POST'])
@store_admin_required
def deactivate_user(user_id):
    """Deactivate a user account — store_admin may only deactivate users in their store."""
    company_id = get_current_company_id()
    from app.models.models import User as _User
    target = db.session.query(_User).filter_by(id=user_id, company_id=company_id).first()
    if not target:
        flash(t('Người dùng không tìm thấy'), 'error')
    elif str(target.id) == str(g.user.id):
        flash(t('Không thể vô hiệu hóa tài khoản của chính mình'), 'error')
    elif not is_company_admin() and str(target.store_id) != str(get_current_store_id()):
        abort(403)
    else:
        try:
            UserService().deactivate_user(user_id)
            flash(t(f'Tài khoản "{target.full_name}" đã bị vô hiệu hóa'), 'warning')
        except Exception as e:
            logger.error(f"Error deactivating user: {e}", exc_info=True)
            flash(t('Lỗi khi vô hiệu hóa tài khoản'), 'error')
    return redirect(url_for('dashboard.list_users'))


# ═══════════════════════════════════════════════════════════════════════
# MATERIAL MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════

def _get_material_svc():
    return MaterialService()


def _get_supplier_svc():
    return SupplierService()


# ── Suppliers ───────────────────────────────────────────────

@dashboard_bp.route('/materials/suppliers', methods=['GET', 'POST'])
@store_admin_required
def material_suppliers():
    """Manage suppliers (store_admin+)."""
    company_id = get_current_company_id()
    svc = _get_supplier_svc()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'create':
                ext_values = collect_extension_values(company_id, 'supplier', request.form)
                _sup = svc.create_supplier(
                    company_id,
                    name=request.form.get('name', '').strip(),
                    contact_person=request.form.get('contact_person', '').strip() or None,
                    phone=request.form.get('phone', '').strip() or None,
                    email=request.form.get('email', '').strip() or None,
                    address=request.form.get('address', '').strip() or None,
                    tax_code=request.form.get('tax_code', '').strip() or None,
                    payment_terms=request.form.get('payment_terms', 'COD'),
                    lead_time_days=request.form.get('lead_time_days', 0) or 0,
                    rating=request.form.get('rating', 0) or 0,
                    notes=request.form.get('notes', '').strip() or None,
                )
                if _sup is not None and apply_extension_values(_sup, ext_values):
                    db.session.commit()
                flash(t('Nhà cung cấp đã được tạo'), 'success')
            elif action == 'edit':
                svc.update_supplier(
                    request.form.get('supplier_id'), company_id,
                    name=request.form.get('name', '').strip(),
                    contact_person=request.form.get('contact_person', '').strip() or None,
                    phone=request.form.get('phone', '').strip() or None,
                    email=request.form.get('email', '').strip() or None,
                    address=request.form.get('address', '').strip() or None,
                    tax_code=request.form.get('tax_code', '').strip() or None,
                    payment_terms=request.form.get('payment_terms', 'COD'),
                    lead_time_days=int(request.form.get('lead_time_days', 0) or 0),
                    rating=int(request.form.get('rating', 0) or 0),
                    notes=request.form.get('notes', '').strip() or None,
                )
                flash(t('Nhà cung cấp đã được cập nhật'), 'success')
            elif action == 'delete':
                svc.delete_supplier(request.form.get('supplier_id'), company_id)
                flash(t('Nhà cung cấp đã bị vô hiệu hóa'), 'warning')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'material_suppliers error: {e}', exc_info=True)
            db.session.rollback()
            flash(t('Lỗi hệ thống'), 'error')
        return redirect(url_for('dashboard.material_suppliers'))

    suppliers = svc.list_suppliers(company_id, active_only=False)
    return render_template('materials/suppliers.html', suppliers=suppliers)


# ── Units ────────────────────────────────────────────────────────────

@dashboard_bp.route('/materials/units', methods=['GET', 'POST'])
@company_admin_required
def material_units():
    """Manage units of measure (company_admin only)."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'create':
                svc.create_unit(
                    company_id,
                    name=request.form.get('name', '').strip(),
                    abbreviation=request.form.get('abbreviation', '').strip() or None,
                    description=request.form.get('description', '').strip() or None,
                )
                flash(t('Đơn vị đã được tạo'), 'success')
            elif action == 'edit':
                svc.update_unit(
                    request.form.get('unit_id'), company_id,
                    name=request.form.get('name', '').strip(),
                    abbreviation=request.form.get('abbreviation', '').strip() or None,
                    description=request.form.get('description', '').strip() or None,
                )
                flash(t('Đơn vị đã được cập nhật'), 'success')
            elif action == 'delete':
                svc.delete_unit(request.form.get('unit_id'), company_id)
                flash(t('Đơn vị đã bị vô hiệu hóa'), 'warning')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'material_units error: {e}', exc_info=True)
            db.session.rollback()
            flash(t('Lỗi hệ thống'), 'error')
        return redirect(url_for('dashboard.material_units'))

    units = svc.list_units(company_id, active_only=False)
    return render_template('materials/units.html', units=units)


# ── Categories ───────────────────────────────────────────────────────

@dashboard_bp.route('/materials/categories', methods=['GET', 'POST'])
@store_admin_required
def material_categories():
    """Manage material categories (store_admin+)."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    if request.method == 'POST':
        action = request.form.get('action')
        try:
            if action == 'create':
                svc.create_category(
                    company_id,
                    name=request.form.get('name', '').strip(),
                    description=request.form.get('description', '').strip() or None,
                    sort_order=int(request.form.get('sort_order', 0) or 0),
                )
                flash(t('Danh mục đã được tạo'), 'success')
            elif action == 'edit':
                svc.update_category(
                    request.form.get('cat_id'), company_id,
                    name=request.form.get('name', '').strip(),
                    description=request.form.get('description', '').strip() or None,
                    sort_order=int(request.form.get('sort_order', 0) or 0),
                )
                flash(t('Danh mục đã được cập nhật'), 'success')
            elif action == 'delete':
                svc.delete_category(request.form.get('cat_id'), company_id)
                flash(t('Danh mục đã bị vô hiệu hóa'), 'warning')
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'material_categories error: {e}', exc_info=True)
            db.session.rollback()
            flash(t('Lỗi hệ thống'), 'error')
        return redirect(url_for('dashboard.material_categories'))

    cats = svc.list_categories(company_id, active_only=False)
    return render_template('materials/categories.html', categories=cats)


# ── Material List ───────────────────────────────────────────────────

@dashboard_bp.route('/materials/')
@login_required
def list_materials():
    """List all materials for the company."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', '').strip() or None
    materials = svc.list_materials(company_id, category_id=category_id, search=search)
    categories = svc.list_categories(company_id)
    return render_template('materials/list.html',
                           materials=materials,
                           categories=categories,
                           selected_category_id=category_id,
                           search=search)


# ── Create Material ─────────────────────────────────────────────────

@dashboard_bp.route('/materials/create', methods=['GET', 'POST'])
@store_admin_required
def create_material():
    """Create a new material."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    if request.method == 'POST':
        try:
            ext_values = collect_extension_values(company_id, 'material', request.form)  # validate early
            image_file = request.files.get('image')
            image_path = _save_item_image(image_file) if image_file else None

            unit_price_raw = request.form.get('unit_price', '').strip()
            min_stock_raw  = request.form.get('min_stock_level', '').strip()

            def _f(key):  # float or None
                v = request.form.get(key, '').strip()
                return float(v) if v else None

            def _i(key):  # int or None
                v = request.form.get(key, '').strip()
                return int(v) if v else None

            def _s(key):  # stripped string or None
                v = request.form.get(key, '').strip()
                return v or None

            mat = svc.create_material(
                company_id=company_id,
                material_code=request.form.get('material_code', '').strip(),
                name=request.form.get('name', '').strip(),
                category_id=request.form.get('category_id') or None,
                unit_id=request.form.get('unit_id') or None,
                supplier_id=request.form.get('supplier_id') or None,
                description=_s('description'),
                color=_s('color'),
                unit_price=float(unit_price_raw) if unit_price_raw else 0,
                supplier_sku=_s('supplier_sku'),
                min_stock_level=float(min_stock_raw) if min_stock_raw else 0,
                image_path=image_path,
                notes=_s('notes'),
                spec_width_cm=_f('spec_width_cm'),
                spec_thickness_mm=_f('spec_thickness_mm'),
                spec_roll_length_m=_f('spec_roll_length_m'),
                spec_weight_per_unit=_f('spec_weight_per_unit'),
                spec_weight_unit=_s('spec_weight_unit'),
                spec_composition=_s('spec_composition'),
                spec_pattern=_s('spec_pattern'),
                spec_finish=_s('spec_finish'),
                spec_durability_cycles=_i('spec_durability_cycles'),
                spec_density_kg_m3=_f('spec_density_kg_m3'),
                spec_hardness=_s('spec_hardness'),
                spec_fire_resistance=_s('spec_fire_resistance'),
                spec_water_resistance=_s('spec_water_resistance'),
                spec_uv_resistance=_s('spec_uv_resistance'),
                spec_country_of_origin=_s('spec_country_of_origin'),
                spec_certifications=_s('spec_certifications'),
            )
            if apply_extension_values(mat, ext_values):
                db.session.commit()
            # Ensure stock rows exist for all stores
            svc.ensure_stock_entries_for_stores(mat.id, company_id)
            flash(t(f'Nguyên vật liệu "{mat.name}" đã được tạo'), 'success')
            return redirect(url_for('dashboard.view_material', material_id=mat.id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'create_material error: {e}', exc_info=True)
            db.session.rollback()
            flash(t('Lỗi hệ thống khi tạo NVL'), 'error')

    categories = svc.list_categories(company_id)
    units = svc.list_units(company_id)
    suppliers = _get_supplier_svc().list_suppliers(company_id)
    return render_template('materials/create.html', categories=categories, units=units, suppliers=suppliers)


# ── View Material ───────────────────────────────────────────────────

@dashboard_bp.route('/materials/<material_id>')
@login_required
def view_material(material_id):
    """View material detail + stock."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    mat = svc.get_material(material_id, company_id)
    if not mat:
        abort(404)
    # Ensure all stores have a stock entry (so the table is complete)
    svc.ensure_stock_entries_for_stores(mat.id, company_id)
    stock_entries = svc.get_stock_for_material(mat.id)
    return render_template('materials/view.html', material=mat, stock_entries=stock_entries)


# ── Edit Material ───────────────────────────────────────────────────

@dashboard_bp.route('/materials/<material_id>/edit', methods=['GET', 'POST'])
@store_admin_required
def edit_material(material_id):
    """Edit a material."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    mat = svc.get_material(material_id, company_id)
    if not mat:
        abort(404)
    if request.method == 'POST':
        try:
            image_file = request.files.get('image')
            image_path = _save_item_image(image_file, mat.image_path)

            unit_price_raw = request.form.get('unit_price', '').strip()
            min_stock_raw  = request.form.get('min_stock_level', '').strip()

            def _f(key):
                v = request.form.get(key, '').strip()
                return float(v) if v else None

            def _i(key):
                v = request.form.get(key, '').strip()
                return int(v) if v else None

            def _s(key):
                v = request.form.get(key, '').strip()
                return v or None

            svc.update_material(
                material_id, company_id,
                material_code=request.form.get('material_code', '').strip(),
                name=request.form.get('name', '').strip(),
                category_id=request.form.get('category_id') or None,
                unit_id=request.form.get('unit_id') or None,
                supplier_id=request.form.get('supplier_id') or None,
                description=_s('description'),
                color=_s('color'),
                unit_price=float(unit_price_raw) if unit_price_raw else 0,
                supplier_sku=_s('supplier_sku'),
                min_stock_level=float(min_stock_raw) if min_stock_raw else 0,
                image_path=image_path,
                notes=_s('notes'),
                spec_width_cm=_f('spec_width_cm'),
                spec_thickness_mm=_f('spec_thickness_mm'),
                spec_roll_length_m=_f('spec_roll_length_m'),
                spec_weight_per_unit=_f('spec_weight_per_unit'),
                spec_weight_unit=_s('spec_weight_unit'),
                spec_composition=_s('spec_composition'),
                spec_pattern=_s('spec_pattern'),
                spec_finish=_s('spec_finish'),
                spec_durability_cycles=_i('spec_durability_cycles'),
                spec_density_kg_m3=_f('spec_density_kg_m3'),
                spec_hardness=_s('spec_hardness'),
                spec_fire_resistance=_s('spec_fire_resistance'),
                spec_water_resistance=_s('spec_water_resistance'),
                spec_uv_resistance=_s('spec_uv_resistance'),
                spec_country_of_origin=_s('spec_country_of_origin'),
                spec_certifications=_s('spec_certifications'),
            )
            flash(t('Đã cập nhật nguyên vật liệu'), 'success')
            return redirect(url_for('dashboard.view_material', material_id=material_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'edit_material error: {e}', exc_info=True)
            db.session.rollback()
            flash(t('Lỗi hệ thống khi cập nhật NVL'), 'error')

    categories = svc.list_categories(company_id)
    units = svc.list_units(company_id)
    suppliers = _get_supplier_svc().list_suppliers(company_id)
    return render_template('materials/edit.html', material=mat, categories=categories, units=units, suppliers=suppliers)


# ── Deactivate Material ─────────────────────────────────────────────

@dashboard_bp.route('/materials/<material_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_material(material_id):
    """Soft-delete a material (company_admin only)."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    try:
        mat = svc.get_material(material_id, company_id)
        if not mat:
            abort(404)
        svc.deactivate_material(material_id, company_id)
        flash(t(f'NVL "{mat.name}" đã bị vô hiệu hóa'), 'warning')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f'deactivate_material error: {e}', exc_info=True)
        flash(t('Lỗi hệ thống'), 'error')
    return redirect(url_for('dashboard.list_materials'))


# ── Update Stock ────────────────────────────────────────────────────

@dashboard_bp.route('/materials/<material_id>/stock', methods=['POST'])
@store_admin_required
def update_material_stock(material_id):
    """Update stock quantity for a single material+location."""
    company_id = get_current_company_id()
    svc = _get_material_svc()
    mat = svc.get_material(material_id, company_id)
    if not mat:
        abort(404)
    try:
        store_id_raw = request.form.get('store_id', '').strip() or None
        quantity_raw = request.form.get('quantity', '0').strip()
        quantity = float(quantity_raw) if quantity_raw else 0
        svc.update_stock(material_id, company_id, store_id=store_id_raw, quantity=quantity)
        flash(t('Cập nhật tồn kho thành công'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f'update_material_stock error: {e}', exc_info=True)
        db.session.rollback()
        flash(t('Lỗi hệ thống khi cập nhật tồn kho'), 'error')
    return redirect(url_for('dashboard.view_material', material_id=material_id))


# ===== EXTENSION FIELD CONFIGURATION (admin) =====

@dashboard_bp.route('/settings/extension-fields', methods=['GET', 'POST'])
@company_admin_required
def extension_fields_settings():
    """Company-admin page to configure the extend01..extend10 custom fields for
    each document type (label, data type, required, enabled). See AUDIT D9."""
    company_id = get_current_company_id()
    entity = request.args.get('entity', 'quotation')
    if entity not in ExtensionFieldConfig.ENTITY_TYPES:
        entity = 'quotation'

    if request.method == 'POST':
        entity = request.form.get('entity_type', entity)
        if entity not in ExtensionFieldConfig.ENTITY_TYPES:
            entity = 'quotation'
        existing = {c.field_key: c for c in ExtensionFieldConfig.query.filter_by(
            company_id=company_id, entity_type=entity).all()}
        for key in FIELD_KEYS:
            cfg = existing.get(key)
            if cfg is None:
                cfg = ExtensionFieldConfig(company_id=company_id, entity_type=entity, field_key=key)
                db.session.add(cfg)
            cfg.is_enabled = request.form.get(f'{key}_enabled') == 'on'
            cfg.label = request.form.get(f'{key}_label', '').strip() or None
            dt = request.form.get(f'{key}_type', 'text')
            cfg.data_type = dt if dt in ExtensionFieldConfig.DATA_TYPES else 'text'
            cfg.is_required = request.form.get(f'{key}_required') == 'on'
            try:
                cfg.sort_order = int(request.form.get(f'{key}_order') or 0)
            except (TypeError, ValueError):
                cfg.sort_order = 0
        db.session.commit()
        flash(t('Đã lưu cấu hình trường mở rộng'), 'success')
        return redirect(url_for('dashboard.extension_fields_settings', entity=entity))

    existing = {c.field_key: c for c in ExtensionFieldConfig.query.filter_by(
        company_id=company_id, entity_type=entity).all()}
    slots = []
    for key in FIELD_KEYS:
        slots.append(existing.get(key) or ExtensionFieldConfig(
            field_key=key, entity_type=entity, is_enabled=False,
            data_type='text', is_required=False, sort_order=0, label=None))
    return render_template('settings/extension_fields.html',
                           entity=entity, slots=slots,
                           entity_types=ExtensionFieldConfig.ENTITY_TYPES,
                           data_types=ExtensionFieldConfig.DATA_TYPES)


# ===== PRODUCTION PLANNING (Feature 2) =====

def _owned_plan(plan_id, company_id):
    from app.models.models import ProductionPlan
    plan = ProductionPlan.query.get(plan_id)
    if not plan or str(plan.company_id) != str(company_id):
        return None
    return plan


@dashboard_bp.route('/orders/<order_id>/production-plan', methods=['GET'])
@login_required
def view_production_plan(order_id):
    company_id = get_current_company_id()
    from app.models.models import Material
    from app.services.services import ProductionPlanService
    order = OrderService().get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    from app.models.models import MaterialUnit
    plan = ProductionPlanService().get_plan_for_order(order_id)
    materials = Material.query.filter_by(company_id=company_id, is_active=True).order_by(Material.name).all()
    units = MaterialUnit.query.filter_by(company_id=company_id, is_active=True).order_by(MaterialUnit.name).all()
    return render_template('production/plan.html', order=order, plan=plan,
                           materials=materials, units=units)


@dashboard_bp.route('/production-plan/<plan_id>/status/<action>', methods=['POST'])
@login_required
def production_plan_status(plan_id, action):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    from app.services.services import ProductionPlanService
    try:
        ProductionPlanService().transition(plan, action)
        flash(t('Đã cập nhật trạng thái kế hoạch sản xuất'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f'production_plan_status error: {e}')
        db.session.rollback(); flash(t('Lỗi khi cập nhật trạng thái'), 'error')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/production-plan/<plan_id>/delay', methods=['POST'])
@login_required
def production_plan_delay(plan_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    from app.services.services import ProductionPlanService
    delayed = request.form.get('delayed') in ('on', '1', 'true')
    ProductionPlanService().set_delay(plan, delayed, request.form.get('delay_reason', '').strip() or None)
    flash(t('Đã cập nhật tình trạng tiến độ'), 'success')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/production-plan/<plan_id>/materials', methods=['POST'])
@login_required
def add_plan_material(plan_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    if not plan.can_edit():
        flash(t('Kế hoạch đã chốt (đã duyệt) — không thể sửa danh mục vật tư.'), 'error')
        return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))
    from app.models.models import ProductionMaterialLine
    try:
        material_id = request.form.get('material_id')
        qty = float(request.form.get('quantity_required') or 0)
        if not material_id or qty < 0:
            raise ValueError(t('Vui lòng chọn vật tư và số lượng hợp lệ (>= 0)'))
        db.session.add(ProductionMaterialLine(
            plan_id=plan.id, plan_item_id=request.form.get('plan_item_id') or None,
            material_id=material_id, quantity_required=qty,
            unit=request.form.get('unit', '').strip() or None))
        db.session.commit()
        flash(t('Đã thêm vật tư vào kế hoạch'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error(f'add_plan_material error: {e}')
        db.session.rollback(); flash(t('Lỗi khi thêm vật tư'), 'error')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/production-plan/<plan_id>/material/<line_id>/delete', methods=['POST'])
@login_required
def delete_plan_material(plan_id, line_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    if not plan.can_edit():
        flash(t('Kế hoạch đã chốt (đã duyệt) — không thể sửa danh mục vật tư.'), 'error')
        return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))
    from app.models.models import ProductionMaterialLine
    line = ProductionMaterialLine.query.get(line_id)
    if line and str(line.plan_id) == str(plan.id):
        db.session.delete(line); db.session.commit()
        flash(t('Đã xóa vật tư'), 'success')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/production-plan/<plan_id>/issue', methods=['POST'])
@login_required
def issue_plan_materials(plan_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    if not plan.can_issue():
        flash(t('Chỉ cấp phát vật tư sau khi kế hoạch đã được duyệt (chốt).'), 'error')
        return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))
    from app.services.services import ProductionPlanService
    try:
        shortages = ProductionPlanService().issue_materials(plan)
        if shortages:
            flash(t(f'Không đủ tồn kho cho {len(shortages)} vật tư — chưa trừ kho.'), 'error')
        else:
            flash(t('Đã cấp phát và trừ kho vật tư thành công.'), 'success')
    except Exception as e:
        logger.error(f'issue_plan_materials error: {e}')
        db.session.rollback(); flash(t('Lỗi khi cấp phát vật tư'), 'error')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/production-plan/<plan_id>/save-norm/<item_id>', methods=['POST'])
@login_required
def save_plan_norm(plan_id, item_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    from app.models.models import ProductionPlanItem
    from app.services.services import ProductionPlanService
    item = ProductionPlanItem.query.get(item_id)
    if item and str(item.plan_id) == str(plan.id):
        try:
            ProductionPlanService().save_as_norm(item)
            flash(t('Đã lưu định mức để tái sử dụng'), 'success')
        except Exception as e:
            logger.error(f'save_plan_norm error: {e}')
            db.session.rollback(); flash(t('Lỗi khi lưu định mức'), 'error')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))


@dashboard_bp.route('/materials/low-stock', methods=['GET'])
@login_required
def low_stock_materials():
    company_id = get_current_company_id()
    from app.services.services import ProductionPlanService
    materials = ProductionPlanService().low_stock_materials(company_id)
    return render_template('materials/low_stock.html', materials=materials)


@dashboard_bp.route('/materials/purchase-suggestions', methods=['GET'])
@login_required
def purchase_suggestions():
    """Đề xuất mua hàng (PO) — bung định mức kế hoạch SX, trừ tồn, gộp theo NCC."""
    company_id = get_current_company_id()
    from app.services.services import ProductionPlanService
    data = ProductionPlanService().purchase_suggestions(company_id)
    return render_template('materials/purchase_suggestions.html', data=data)


# ===== PROCUREMENT: Purchase Orders (PO) + Goods Receipts (GR) =====

def _parse_date(s):
    """Parse a 'YYYY-MM-DD' form value to a date, or None if empty/invalid."""
    from datetime import datetime as _dt
    s = (s or '').strip()
    try:
        return _dt.strptime(s, '%Y-%m-%d').date() if s else None
    except ValueError:
        return None


def _po_lists(company_id):
    """Suppliers/materials/stores for PO edit dropdowns."""
    from app.models.models import Supplier, Material, Store
    return {
        'suppliers': Supplier.query.filter_by(company_id=company_id, is_active=True).order_by(Supplier.name).all(),
        'materials': Material.query.filter_by(company_id=company_id, is_active=True).order_by(Material.material_code).all(),
        'stores':    Store.query.filter_by(company_id=company_id, is_active=True).order_by(Store.name).all(),
    }


@dashboard_bp.route('/purchase-orders', methods=['GET'])
@login_required
def list_purchase_orders():
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    pos = ProcurementService().list_pos(company_id, status=request.args.get('status') or None)
    return render_template('procurement/po_list.html', pos=pos, status=request.args.get('status') or '')


def _po_header_from_form():
    return {
        'supplier_id': request.form.get('supplier_id') or None,
        'store_id': request.form.get('store_id') or None,
        'order_date': _parse_date(request.form.get('order_date')),
        'expected_date': _parse_date(request.form.get('expected_date')),
        'vat_rate': request.form.get('vat_rate') or 0,
        'notes': request.form.get('notes') or None,
    }


@dashboard_bp.route('/purchase-orders/create', methods=['GET', 'POST'])
@login_required
def create_purchase_order():
    """Document-style PO create — fill header + lines, save once."""
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    from app.utils.extension_fields import collect_extension_values, apply_extension_values
    if request.method == 'POST':
        try:
            ext = collect_extension_values(company_id, 'purchase_order', request.form)
            lines = parse_material_lines(request.form, with_price=True)
            po = ProcurementService().create_po(company_id, _po_header_from_form(), lines)
            if apply_extension_values(po, ext):
                db.session.commit()
            flash(t('Đã tạo đơn mua %(po)s.') % {'po': po.po_number}, 'success')
            return redirect(url_for('dashboard.view_purchase_order', po_id=po.id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'create_purchase_order error: {e}'); db.session.rollback()
            flash(t('Lỗi khi tạo đơn mua.'), 'error')
    return render_template('procurement/po_form.html', po=None, existing_lines=[], **_po_lists(company_id))


@dashboard_bp.route('/purchase-orders/from-suggestions', methods=['POST'])
@login_required
def create_pos_from_suggestions():
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    try:
        pos = ProcurementService().create_pos_from_suggestions(company_id)
        if pos:
            flash(t('Đã tạo %(n)s đơn mua từ đề xuất.') % {'n': len(pos)}, 'success')
        else:
            flash(t('Không có vật tư cần mua để tạo đơn.'), 'info')
    except Exception as e:
        logger.error(f'create_pos_from_suggestions error: {e}')
        db.session.rollback(); flash(t('Lỗi khi tạo đơn mua.'), 'error')
    return redirect(url_for('dashboard.list_purchase_orders'))


def _owned_po(po_id, company_id):
    from app.services.procurement_service import ProcurementService
    return ProcurementService().get_po(company_id, po_id)


@dashboard_bp.route('/purchase-orders/<po_id>', methods=['GET'])
@login_required
def view_purchase_order(po_id):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        flash(t('Không tìm thấy đơn mua hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_purchase_orders'))
    return render_template('procurement/po_view.html', po=po, **_po_lists(company_id))


@dashboard_bp.route('/purchase-orders/<po_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_purchase_order(po_id):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        return redirect(url_for('dashboard.list_purchase_orders'))
    if not po.can_edit():
        flash(t('Đơn mua đã gửi/hủy — không sửa được.'), 'error')
        return redirect(url_for('dashboard.view_purchase_order', po_id=po.id))
    from app.services.procurement_service import ProcurementService
    from app.utils.extension_fields import collect_extension_values, apply_extension_values
    if request.method == 'POST':
        try:
            ext = collect_extension_values(company_id, 'purchase_order', request.form)
            lines = parse_material_lines(request.form, with_price=True)
            ProcurementService().update_po(po, _po_header_from_form(), lines)
            apply_extension_values(po, ext); db.session.commit()
            flash(t('Đã cập nhật đơn mua.'), 'success')
            return redirect(url_for('dashboard.view_purchase_order', po_id=po.id))
        except ValueError as e:
            flash(str(e), 'error')
    existing = [{'material_id': str(l.material_id), 'quantity': float(l.quantity_ordered or 0),
                 'unit': l.unit, 'unit_price': float(l.unit_price or 0)} for l in po.lines]
    return render_template('procurement/po_form.html', po=po, existing_lines=existing, **_po_lists(company_id))


@dashboard_bp.route('/purchase-orders/<po_id>/status/<action>', methods=['POST'])
@login_required
def purchase_order_status(po_id, action):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        return redirect(url_for('dashboard.list_purchase_orders'))
    from app.services.procurement_service import ProcurementService
    try:
        ProcurementService().transition(po, action)
        flash(t('Đã cập nhật trạng thái đơn mua.'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.view_purchase_order', po_id=po.id))


@dashboard_bp.route('/purchase-orders/<po_id>/receive', methods=['POST'])
@login_required
def receive_purchase_order(po_id):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        return redirect(url_for('dashboard.list_purchase_orders'))
    from app.services.procurement_service import ProcurementService
    # quantities: form fields qty_<line_id>
    quantities = {}
    for line in po.lines:
        raw = request.form.get(f'qty_{line.id}')
        if raw:
            quantities[str(line.id)] = raw
    try:
        gr, warns = ProcurementService().receive(
            po, quantities, store_id=(request.form.get('store_id') or None),
            receipt_date=(_parse_date(request.form.get('receipt_date')) if request.form.get('receipt_date') else None),
            notes=request.form.get('notes'))
        flash(t('Đã nhập kho %(gr)s — tồn kho đã tăng.') % {'gr': gr.gr_number}, 'success')
        for w in warns:
            flash(w, 'warning')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.view_purchase_order', po_id=po.id))


@dashboard_bp.route('/purchase-orders/<po_id>/print', methods=['GET'])
@login_required
def print_purchase_order(po_id):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        abort(404)
    from app.models.models import Company
    from app.utils.procurement_doc import build_purchase_order_docx
    company = Company.query.get(company_id)
    bio = build_purchase_order_docx(po, company)
    return send_file(bio, as_attachment=True, download_name=f'{po.po_number}.docx',
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


# ===== PROCUREMENT: Purchase Requisitions (PR) =====

def _pr_header_from_form():
    return {
        'store_id': request.form.get('store_id') or None,
        'request_date': _parse_date(request.form.get('request_date')),
        'expected_date': _parse_date(request.form.get('expected_date')),
        'title': request.form.get('title') or None,
        'notes': request.form.get('notes') or None,
    }


def _owned_pr(pr_id, company_id):
    from app.services.requisition_service import RequisitionService
    return RequisitionService().get_pr(company_id, pr_id)


@dashboard_bp.route('/requisitions', methods=['GET'])
@login_required
def list_requisitions():
    company_id = get_current_company_id()
    from app.services.requisition_service import RequisitionService
    prs = RequisitionService().list_prs(company_id, status=request.args.get('status') or None)
    return render_template('procurement/pr_list.html', prs=prs, status=request.args.get('status') or '')


@dashboard_bp.route('/requisitions/create', methods=['GET', 'POST'])
@login_required
def create_requisition():
    company_id = get_current_company_id()
    from app.services.requisition_service import RequisitionService
    from app.utils.extension_fields import collect_extension_values, apply_extension_values
    svc = RequisitionService()
    if request.method == 'POST':
        try:
            ext = collect_extension_values(company_id, 'purchase_requisition', request.form)
            lines = parse_material_lines(request.form, with_price=False)
            pr = svc.create_pr(company_id, _pr_header_from_form(), lines)
            if apply_extension_values(pr, ext):
                db.session.commit()
            flash(t('Đã tạo đề nghị mua %(pr)s.') % {'pr': pr.pr_number}, 'success')
            return redirect(url_for('dashboard.view_requisition', pr_id=pr.id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f'create_requisition error: {e}'); db.session.rollback()
            flash(t('Lỗi khi tạo đề nghị mua.'), 'error')
    # optional prefill from auto-suggestions (?from=suggestions)
    prefill = svc.suggest_lines(company_id) if request.args.get('from') == 'suggestions' else []
    existing = [{'material_id': str(x['material_id']), 'quantity': x['quantity'], 'unit': x['unit']} for x in prefill]
    return render_template('procurement/pr_form.html', pr=None, existing_lines=existing, **_po_lists(company_id))


@dashboard_bp.route('/requisitions/<pr_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_requisition(pr_id):
    company_id = get_current_company_id()
    pr = _owned_pr(pr_id, company_id)
    if not pr:
        return redirect(url_for('dashboard.list_requisitions'))
    if not pr.can_edit():
        flash(t('PR đã gửi/duyệt/hủy — không sửa được.'), 'error')
        return redirect(url_for('dashboard.view_requisition', pr_id=pr.id))
    from app.services.requisition_service import RequisitionService
    from app.utils.extension_fields import collect_extension_values, apply_extension_values
    if request.method == 'POST':
        try:
            ext = collect_extension_values(company_id, 'purchase_requisition', request.form)
            lines = parse_material_lines(request.form, with_price=False)
            RequisitionService().update_pr(pr, _pr_header_from_form(), lines)
            apply_extension_values(pr, ext); db.session.commit()
            flash(t('Đã cập nhật đề nghị mua.'), 'success')
            return redirect(url_for('dashboard.view_requisition', pr_id=pr.id))
        except ValueError as e:
            flash(str(e), 'error')
    existing = [{'material_id': str(l.material_id), 'quantity': float(l.quantity or 0), 'unit': l.unit}
                for l in pr.lines]
    return render_template('procurement/pr_form.html', pr=pr, existing_lines=existing, **_po_lists(company_id))


@dashboard_bp.route('/requisitions/<pr_id>', methods=['GET'])
@login_required
def view_requisition(pr_id):
    company_id = get_current_company_id()
    pr = _owned_pr(pr_id, company_id)
    if not pr:
        return redirect(url_for('dashboard.list_requisitions'))
    return render_template('procurement/pr_view.html', pr=pr)


@dashboard_bp.route('/requisitions/<pr_id>/status/<action>', methods=['POST'])
@login_required
def requisition_status(pr_id, action):
    company_id = get_current_company_id()
    pr = _owned_pr(pr_id, company_id)
    if not pr:
        return redirect(url_for('dashboard.list_requisitions'))
    from app.services.requisition_service import RequisitionService
    try:
        RequisitionService().transition(pr, action)
        flash(t('Đã cập nhật trạng thái đề nghị mua.'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.view_requisition', pr_id=pr.id))


@dashboard_bp.route('/requisitions/<pr_id>/convert', methods=['POST'])
@login_required
def convert_requisition(pr_id):
    company_id = get_current_company_id()
    pr = _owned_pr(pr_id, company_id)
    if not pr:
        return redirect(url_for('dashboard.list_requisitions'))
    from app.services.requisition_service import RequisitionService
    try:
        pos = RequisitionService().convert_to_pos(pr)
        flash(t('Đã tạo %(n)s đơn mua từ đề nghị.') % {'n': len(pos)}, 'success')
        if len(pos) == 1:
            return redirect(url_for('dashboard.view_purchase_order', po_id=pos[0].id))
        return redirect(url_for('dashboard.list_purchase_orders'))
    except ValueError as e:
        flash(str(e), 'error'); db.session.rollback()
    return redirect(url_for('dashboard.view_requisition', pr_id=pr.id))


# ===== PROCUREMENT: Goods Receipts (GR) management =====

@dashboard_bp.route('/goods-receipts', methods=['GET'])
@login_required
def list_goods_receipts():
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    grs = ProcurementService().list_grs(company_id)
    return render_template('procurement/gr_list.html', grs=grs)


@dashboard_bp.route('/goods-receipts/<gr_id>', methods=['GET'])
@login_required
def view_goods_receipt(gr_id):
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    gr = ProcurementService().get_gr(company_id, gr_id)
    if not gr:
        return redirect(url_for('dashboard.list_goods_receipts'))
    return render_template('procurement/gr_view.html', gr=gr)


@dashboard_bp.route('/production-plan/<plan_id>/print', methods=['GET'])
@login_required
def print_production_plan(plan_id):
    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_orders'))
    from app.models.models import Company, Customer
    from app.utils.production_doc import build_production_plan_docx
    company = db.session.get(Company, company_id)
    order = plan.order
    customer = db.session.get(Customer, order.customer_id)
    bio = build_production_plan_docx(plan, order, customer, company)
    return send_file(bio, as_attachment=True,
                     download_name=f'LenhSanXuat_{plan.plan_number}.docx',
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
