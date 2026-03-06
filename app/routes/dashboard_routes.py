"""
Dashboard and main application routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, send_file, current_app, session
from app.utils.auth_utils import (
    login_required, company_admin_required, store_admin_required,
    ensure_tenant_access, ensure_store_access,
    get_current_company_id, get_current_store_id,
    get_accessible_store_ids, is_company_admin,
)
from app.services.services import (
    StoreService, UserService, CustomerService, OrderService, QuotationService,
    ContractService, HandoverRecordService, PaymentReportService, DocumentService
)
from app.repositories.repository import (
    StoreRepository, CustomerRepository, OrderRepository, DocumentRepository
)
from app.models import Order, Document
from app.config.database import db
from datetime import datetime, date
import logging
import os
import uuid

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


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
        flash('Company not found', 'error')
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
            vat_str = request.form.get('vat_rate', '').strip()
            company.vat_rate = float(vat_str) if vat_str else company.vat_rate
            # Bank accounts from JSON textarea
            bank_json = request.form.get('bank_accounts', '').strip()
            try:
                company.bank_accounts = _json.loads(bank_json) if bank_json else []
            except Exception:
                pass
            db.session.commit()
            flash('Company settings updated successfully', 'success')
        except Exception as e:
            logger.error(f"Error updating company settings: {str(e)}")
            db.session.rollback()
            flash('Error updating company settings', 'error')
    
    return render_template('settings/company.html', company=company)


# ===== DOCUMENT TEMPLATES =====

@dashboard_bp.route('/settings/templates', methods=['GET'])
@company_admin_required
def list_templates():
    """List document templates for the current company"""
    company_id = get_current_company_id()
    from app.repositories.repository import DocumentTemplateRepository
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
        flash('Vui lòng điền đầy đủ tên và loại tài liệu.', 'error')
        return redirect(url_for('dashboard.list_templates'))

    file = request.files.get('template_file')
    if not file or file.filename == '':
        flash('Vui lòng chọn tệp mẫu (.docx).', 'error')
        return redirect(url_for('dashboard.list_templates'))

    allowed_exts = {'.docx', '.rtf', '.txt'}
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_exts:
        flash('Chỉ cho phép tệp .docx, .rtf hoặc .txt.', 'error')
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
        flash(f'Mẫu "{name}" đã được tải lên thành công.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading template: {str(e)}", exc_info=True)
        flash(f'Lỗi khi tải lên mẫu: {str(e)}', 'error')

    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_template(template_id):
    """Deactivate a document template"""
    company_id = get_current_company_id()
    from app.models.models import DocumentTemplate as _DT
    tpl = db.session.get(_DT, template_id)
    if not tpl or str(tpl.company_id) != str(company_id):
        flash('Không tìm thấy mẫu.', 'error')
    else:
        tpl.is_active = False
        db.session.commit()
        flash(f'Mẫu "{tpl.name}" đã được vô hiệu hóa.', 'success')
    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/activate', methods=['POST'])
@company_admin_required
def activate_template(template_id):
    """Activate a document template"""
    company_id = get_current_company_id()
    from app.models.models import DocumentTemplate as _DT
    tpl = db.session.get(_DT, template_id)
    if not tpl or str(tpl.company_id) != str(company_id):
        flash('Không tìm thấy mẫu.', 'error')
    else:
        tpl.is_active = True
        db.session.commit()
        flash(f'Mẫu "{tpl.name}" đã được kích hoạt.', 'success')
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

    customers = None
    total     = 0

    if store_id:
        # Single store — enforce access
        try:
            ensure_store_access(store_id)
        except Exception:
            flash('Không có quyền truy cập cửa hàng này', 'error')
            return redirect(url_for('dashboard.index'))

        store = store_repo.get_active_store(company_id, store_id)
        if not store:
            flash('Cửa hàng không tìm thấy', 'error')
            return redirect(url_for('dashboard.index'))

        if search:
            customers = customer_service.search_customers(store_id, search)
            total     = len(customers)
        else:
            customers = customer_service.list_customers_for_store(store_id, page=page, per_page=20)
            total     = customer_service.count_customers_for_store(store_id)
    else:
        # "All Stores" — company admin sees every accessible store's customers
        from app.repositories.repository import CustomerRepository as _CustRepo
        _repo = _CustRepo()
        if search:
            customers = _repo.search_customers_for_stores(accessible_ids, search)
            total     = len(customers)
        else:
            per_page = 20
            offset   = (page - 1) * per_page
            customers = _repo.get_customers_for_stores(accessible_ids, limit=per_page, offset=offset)
            total     = _repo.count_for_stores(accessible_ids)

    return render_template('customers/list.html',
                           customers=customers,
                           stores=stores,
                           selected_store_id=store_id,
                           page=page,
                           total=total,
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
        flash('Chưa có cửa hàng nào. Vui lòng tạo cửa hàng trước.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Set default store_id if not provided, convert string to UUID if needed
    if not store_id:
        store_id = stores[0].id
    elif isinstance(store_id, str):
        try:
            store_id = uuid.UUID(store_id)
        except ValueError:
            flash('Invalid store ID', 'error')
            return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        try:
            # Validate store_id is provided
            if not store_id:
                flash('Store selection is required', 'error')
                return render_template('customers/create.html', stores=stores, selected_store_id=store_id)
            
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
            flash('Customer created successfully', 'success')
            return redirect(url_for('dashboard.list_customers', store_id=store_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}", exc_info=True)
            flash('Error creating customer', 'error')
    
    return render_template('customers/create.html', stores=stores, selected_store_id=store_id)


@dashboard_bp.route('/customers/<customer_id>')
@login_required
def view_customer(customer_id):
    """View customer details"""
    company_id = get_current_company_id()
    customer_repo = CustomerRepository()
    
    customer = customer_repo.get_by_id(customer_id)
    if not customer or str(customer.store.company_id) != str(company_id):
        flash('Customer not found or access denied', 'error')
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
        flash('Không tìm thấy khách hàng hoặc không có quyền truy cập', 'error')
        return redirect(url_for('dashboard.list_customers'))

    if request.method == 'POST':
        try:
            customer_service = CustomerService()
            customer_service.update_customer(
                customer_id=customer_id,
                name=request.form.get('name', '').strip() or None,
                phone=request.form.get('phone', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                tax_code=request.form.get('tax_code', '').strip() or None,
                representative_name=request.form.get('representative_name', '').strip() or None,
                representative_title=request.form.get('representative_title', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                city=request.form.get('city', '').strip() or None,
                postal_code=request.form.get('postal_code', '').strip() or None,
                country=request.form.get('country', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None,
            )
            flash('Cập nhật thông tin khách hàng thành công!', 'success')
            return redirect(url_for('dashboard.view_customer', customer_id=customer_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error updating customer: {str(e)}", exc_info=True)
            flash('Lỗi khi cập nhật thông tin khách hàng', 'error')

    return render_template('customers/edit.html', customer=customer)


# ===== ORDERS =====

@dashboard_bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    """List orders — scoped to accessible stores"""
    company_id = get_current_company_id()
    page = request.args.get('page', 1, type=int)

    order_service = OrderService()
    if is_company_admin():
        orders = order_service.list_orders_for_company(company_id, page=page, per_page=20)
    else:
        accessible_ids = get_accessible_store_ids(company_id)
        from app.models.models import Order as _Order
        offset = (page - 1) * 20
        orders = _Order.query.filter(
            _Order.company_id == company_id,
            _Order.store_id.in_(accessible_ids),
            _Order.is_active == True
        ).order_by(_Order.created_at.desc()).limit(20).offset(offset).all()

    return render_template('orders/list.html', orders=orders, page=page)


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
            
            # Verify access
            customer = customer_repo.get_by_id(customer_id)
            if not customer or str(customer.store_id) != str(store_id):
                flash('Invalid customer selection', 'error')
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
            
            flash('Order created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order.id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            flash('Error creating order', 'error')
    
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
        flash('Order not found or access denied', 'error')
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
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))

    from app.models.models import Company as _CompanyQ
    _company_q = db.session.get(_CompanyQ, company_id)
    company_vat_rate = getattr(_company_q, 'vat_rate', 8) or 8

    if request.method == 'POST':
        try:
            # Check for duplicate quotation number
            quotation_number = request.form.get('quotation_number', '').strip()
            from app.repositories.repository import QuotationRepository
            quotation_repo = QuotationRepository()
            from app.models.models import Quotation
            existing = db.session.query(Quotation).filter_by(quotation_number=quotation_number).first()
            if existing:
                flash(f'Quotation number "{quotation_number}" is already taken. Please use a different number.', 'error')
                return render_template('quotations/create.html', order=order, company_vat_rate=company_vat_rate)
            
            # Parse items from request
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            subtotal = 0
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'unit': unit,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            total = subtotal + vat_amount
            city = request.form.get('city', '').strip() or None
            payment_terms = request.form.get('payment_terms', '').strip() or None
            amount_in_words = request.form.get('amount_in_words', '').strip() or None
            
            quotation_service = QuotationService()
            quotation = quotation_service.create_quotation(
                order_id=order_id,
                quotation_number=request.form.get('quotation_number', '').strip(),
                quotation_date=datetime.strptime(request.form.get('quotation_date'), '%Y-%m-%d').date(),
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                city=city,
                payment_terms=payment_terms,
                amount_in_words=amount_in_words,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Quotation created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error creating quotation: {str(e)}")
            flash('Error creating quotation', 'error')

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
        flash('Quotation not found or access denied', 'error')
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
        flash('Quotation not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not quotation.can_edit():
        flash('Quotation cannot be edited after approval', 'error')
        return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
    
    if request.method == 'POST':
        try:
            # Parse items from request
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            subtotal = 0
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'unit': unit,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            total = subtotal + vat_amount
            
            quotation_service.update_quotation(
                quotation_id=quotation_id,
                items=items,
                subtotal=subtotal,
                vat_rate=vat_rate,
                vat_amount=vat_amount,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                city=request.form.get('city', '').strip() or None,
                payment_terms=request.form.get('payment_terms', '').strip() or None,
                amount_in_words=request.form.get('amount_in_words', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Quotation updated successfully', 'success')
            return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating quotation: {str(e)}")
            flash('Error updating quotation', 'error')
    
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
            flash('Quotation not found or access denied', 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        quotation_service.approve_quotation(quotation_id, quotation.order_id)
        flash('Quotation approved successfully', 'success')
        
    except ValueError as e:
        flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        logger.error(f"Error approving quotation: {str(e)}")
        flash('Error approving quotation', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))


@dashboard_bp.route('/quotations/<quotation_id>/cancel', methods=['POST'])
@login_required
def cancel_quotation(quotation_id):
    """Cancel quotation"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    try:
        quotation = quotation_service.get_quotation(quotation_id)
        if not quotation or str(quotation.order.company_id) != str(company_id):
            flash('Quotation not found or access denied', 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        reason = request.form.get('reason', '').strip() or 'No reason provided'
        quotation_service.cancel_quotation(quotation_id, reason)
        flash('Quotation canceled successfully', 'success')
        
    except ValueError as e:
        flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        logger.error(f"Error canceling quotation: {str(e)}")
        flash('Error canceling quotation', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))


# ===== CONTRACTS =====

@dashboard_bp.route('/contracts/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_contract(order_id):
    """Create contract"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    # Only show active quotations (not canceled) - typically approved ones for contract
    quotations = [q for q in order.quotations if q.is_active and not q.is_canceled]
    
    if request.method == 'POST':
        try:
            # Check for duplicate contract number
            contract_number = request.form.get('contract_number', '').strip()
            from app.models.models import Contract
            existing = db.session.query(Contract).filter_by(contract_number=contract_number).first()
            if existing:
                flash(f'Contract number "{contract_number}" is already taken. Please use a different number.', 'error')
                return render_template('contracts/create.html', order=order, quotations=quotations)
            
            # Parse items from form
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            subtotal = 0
            for i, name in enumerate(item_names):
                if name.strip():
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    item_total = qty * price
                    items.append({
                        'name': name.strip(),
                        'unit': unit,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            contract_value = subtotal + vat_amount

            advance_percentage = float(request.form.get('advance_percentage') or 30)
            advance_amount = round(contract_value * advance_percentage / 100, 2)
            city = request.form.get('city', '').strip() or None
            
            contract_service = ContractService()
            
            # Create contract with items
            from app.repositories.repository import ContractRepository
            contract_repo = ContractRepository()
            
            quotation_id = request.form.get('quotation_id') or None
            
            # If items are provided from form, use them; otherwise try to copy from quotation
            if not items and quotation_id:
                from app.repositories.repository import QuotationRepository
                quotation = QuotationRepository().get_by_id(quotation_id)
                if quotation and quotation.items:
                    items = list(quotation.items)
            
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
                contract_value=contract_value,
                advance_percentage=advance_percentage,
                advance_amount=advance_amount,
                terms_and_conditions=request.form.get('terms_and_conditions', '').strip() or None
            )
            
            # Update lifecycle
            from app.repositories.repository import LifecycleStatusRepository
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            lifecycle.contract_created = True
            lifecycle.contract_created_at = datetime.utcnow()
            db.session.add(lifecycle)
            db.session.commit()
            
            flash('Contract created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            flash('Error creating contract', 'error')

    # Auto-select first approved quotation to pre-populate items
    selected_quotation = None
    approved_quotes = [q for q in quotations if q.is_approved]
    if approved_quotes:
        selected_quotation = approved_quotes[0]
    elif quotations:
        selected_quotation = quotations[0]

    return render_template('contracts/create.html', order=order, quotations=quotations,
                           selected_quotation=selected_quotation)


@dashboard_bp.route('/contracts/<contract_id>/view', methods=['GET'])
@login_required
def view_contract(contract_id):
    """View contract details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('contracts/view.html', contract=contract, order=contract.order)


@dashboard_bp.route('/contracts/<contract_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contract(contract_id):
    """Edit contract - only if not signed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if contract.is_signed:
        flash('Cannot edit a signed contract', 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    
    if request.method == 'POST':
        try:
            from app.services.services import ContractService
            contract_service = ContractService()
            
            # Parse contract data
            terms_and_conditions = request.form.get('terms_and_conditions', '').strip() or None
            
            # Parse items from form
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            subtotal = 0
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'unit': unit,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            contract_value = subtotal + vat_amount
            advance_percentage = float(request.form.get('advance_percentage') or 30)
            advance_amount = round(contract_value * advance_percentage / 100, 2)
            
            # Update contract
            contract.city = request.form.get('city', '').strip() or None
            contract.contract_value = contract_value
            contract.subtotal = subtotal
            contract.vat_rate = vat_rate
            contract.vat_amount = vat_amount
            contract.advance_percentage = advance_percentage
            contract.advance_amount = advance_amount
            contract.terms_and_conditions = terms_and_conditions
            contract.items = items
            contract.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Contract updated successfully', 'success')
            return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
            
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            flash('Error updating contract', 'error')
    
    return render_template('contracts/edit.html', contract=contract, order=contract.order)


@dashboard_bp.route('/contracts/<contract_id>/sign', methods=['POST'])
@login_required
def sign_contract(contract_id):
    """Mark contract as signed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        contract_service = ContractService()
        contract_service.mark_signed(contract_id, contract.order_id)
        flash('Contract marked as signed', 'success')
    except Exception as e:
        logger.error(f"Error signing contract: {str(e)}")
        flash('Error signing contract', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=contract.order_id))


@dashboard_bp.route('/contracts/<contract_id>/cancel', methods=['POST'])
@login_required
def cancel_contract(contract_id):
    """Cancel contract"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not contract.can_cancel():
        flash('Contract cannot be canceled', 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    
    try:
        canceled_reason = request.form.get('canceled_reason', '').strip()
        if not canceled_reason:
            flash('Cancellation reason is required', 'error')
            return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
        
        # Cancel the contract
        contract.is_canceled = True
        contract.canceled_at = datetime.utcnow()
        contract.canceled_reason = canceled_reason
        contract.is_active = False
        db.session.commit()
        
        flash('Contract has been canceled successfully', 'success')
        logger.info(f"Contract {contract.contract_number} canceled by user. Reason: {canceled_reason}")
    except Exception as e:
        logger.error(f"Error canceling contract: {str(e)}")
        db.session.rollback()
        flash('Error canceling contract', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=contract.order_id))


@dashboard_bp.route('/orders/<order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Cancel order"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import OrderRepository
    order_repo = OrderRepository()
    order = order_repo.get_by_id(order_id)
    
    if not order or str(order.company_id) != str(company_id):
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not order.can_cancel():
        flash('Order cannot be canceled', 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))
    
    try:
        canceled_reason = request.form.get('canceled_reason', '').strip()
        if not canceled_reason:
            flash('Cancellation reason is required', 'error')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
        
        # Cancel the order
        order.is_canceled = True
        order.canceled_at = datetime.utcnow()
        order.canceled_reason = canceled_reason
        db.session.commit()
        
        flash('Order has been canceled successfully', 'success')
        logger.info(f"Order {order.order_code} canceled by user. Reason: {canceled_reason}")
    except Exception as e:
        logger.error(f"Error canceling order: {str(e)}")
        db.session.rollback()
        flash('Error canceling order', 'error')
    
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
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Check for duplicate report number
            report_number = request.form.get('report_number', '').strip()
            from app.models.models import HandoverRecord
            existing = db.session.query(HandoverRecord).filter_by(report_number=report_number).first()
            if existing:
                flash(f'Handover record number "{report_number}" is already taken. Please use a different number.', 'error')
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
                    items.append({
                        'name': name,
                        'unit': unit,
                        'quantity': accepted_qty,
                        'unit_price': unit_price,
                        'delivered_qty': delivered_qty,
                        'accepted_qty': accepted_qty,
                        'total': item_total,
                        'status': status,
                        'rejection_reason': reason if status != 'accepted' else ''
                    })
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            total_amount = subtotal + vat_amount
            
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
                total_amount=total_amount,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Handover record created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating handover record: {str(e)}")
            flash('Error creating handover record', 'error')
    
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
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        handover_service.confirm_handover(handover_id, handover.order_id)
        flash('Handover record confirmed', 'success')
    except Exception as e:
        logger.error(f"Error confirming handover: {str(e)}")
        flash('Error confirming handover', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=handover.order_id))


@dashboard_bp.route('/handover/<handover_id>', methods=['GET'])
@login_required
def view_handover(handover_id):
    """View handover record details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('handover/view.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_handover(handover_id):
    """Edit handover record"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not handover.can_edit():
                flash('Handover record cannot be edited (already confirmed or canceled)', 'error')
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
                
                items = []
                subtotal = 0
                for i, name in enumerate(item_names):
                    if name.strip():
                        delivered_qty = float(item_delivered[i]) if i < len(item_delivered) and item_delivered[i] else 0
                        accepted_qty = float(item_accepted[i]) if i < len(item_accepted) and item_accepted[i] else 0
                        unit_price = float(item_prices[i]) if i < len(item_prices) and item_prices[i] else 0
                        unit = item_units[i].strip() if i < len(item_units) else ''
                        item_total = unit_price * accepted_qty
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
                            'rejection_reason': item_reasons[i].strip() if i < len(item_reasons) and item_reasons[i].strip() else None
                        })
                        subtotal += item_total
                handover.items = items
                vat_rate = float(request.form.get('vat_rate') or 8)
                vat_amount = round(subtotal * vat_rate / 100, 2)
                handover.subtotal = subtotal
                handover.vat_rate = vat_rate
                handover.vat_amount = vat_amount
                handover.total_amount = subtotal + vat_amount
            
            db.session.add(handover)
            db.session.commit()
            
            flash('Handover record updated successfully', 'success')
            return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating handover record: {str(e)}")
            flash('Error updating handover record', 'error')
    
    return render_template('handover/edit.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/cancel', methods=['POST'])
@login_required
def cancel_handover(handover_id):
    """Cancel handover record"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        reason = request.form.get('reason', '').strip()
        handover_service.cancel_handover(handover_id, handover.order_id, reason)
        flash('Handover record canceled successfully', 'success')
    except Exception as e:
        logger.error(f"Error canceling handover: {str(e)}")
        flash(f'Error canceling handover: {str(e)}', 'error')
    
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
        flash('Order not found or access denied', 'error')
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
            existing = db.session.query(PaymentReport).filter_by(report_number=report_number).first()
            if existing:
                flash(f'Payment report number "{report_number}" is already taken. Please use a different number.', 'error')
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company)

            payment_service = PaymentReportService()
            payment_type = request.form.get('payment_type')
            
            # Validate payment sequencing
            if payment_type == 'advance' and not order.lifecycle.contract_signed:
                flash('Advance payment can only be recorded after contract is signed', 'error')
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company)

            if payment_type == 'final' and not order.lifecycle.handover_confirmed:
                flash('Final payment can only be recorded after handover is confirmed', 'error')
                return render_template('payment/create.html', order=order, default_type=default_type,
                                       active_contract=active_contract, company=company)
            
            # Parse work items
            items = []
            item_names = request.form.getlist('item_name[]')
            item_units = request.form.getlist('item_unit[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            subtotal = 0
            for i, name in enumerate(item_names):
                if name.strip():
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    unit = item_units[i].strip() if i < len(item_units) else ''
                    item_total = qty * price
                    items.append({'name': name.strip(), 'unit': unit, 'quantity': qty, 'unit_price': price, 'total': item_total})
                    subtotal += item_total
            
            vat_rate = float(request.form.get('vat_rate') or 8)
            vat_amount = round(subtotal * vat_rate / 100, 2)
            amount = subtotal + vat_amount if items else float(request.form.get('amount') or 0)
            
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
            
            flash('Payment report created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error creating payment report: {str(e)}")
            flash('Error creating payment report', 'error')
    
    return render_template('payment/create.html', order=order, default_type=default_type,
                             active_contract=active_contract, company=company)


@dashboard_bp.route('/payment/<payment_id>/confirm', methods=['POST'])
@login_required
def confirm_payment(payment_id):
    """Mark payment as confirmed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        payment_service = PaymentReportService()
        payment_service.mark_confirmed(payment_id, payment.order_id)
        flash('Payment marked as confirmed', 'success')
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        flash('Error confirming payment', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=payment.order_id))


@dashboard_bp.route('/payment/<payment_id>', methods=['GET'])
@login_required
def view_payment(payment_id):
    """View payment report details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('payments/view.html', payment=payment)


@dashboard_bp.route('/payment/<payment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    """Edit payment report"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not payment.can_edit():
                flash('Payment cannot be edited (already confirmed or canceled)', 'error')
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
            
            flash('Payment report updated successfully', 'success')
            return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating payment report: {str(e)}")
            flash('Error updating payment report', 'error')
    
    return render_template('payments/edit.html', payment=payment)


@dashboard_bp.route('/payment/<payment_id>/cancel', methods=['POST'])
@login_required
def cancel_payment(payment_id):
    """Cancel payment report"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        payment_service = PaymentReportService()
        reason = request.form.get('reason', '').strip()
        payment_service.cancel_payment(payment_id, payment.order_id, reason)
        flash('Payment report canceled successfully', 'success')
    except Exception as e:
        logger.error(f"Error canceling payment: {str(e)}")
        flash(f'Error canceling payment: {str(e)}', 'error')
    
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
            from app.repositories.repository import QuotationRepository
            quotation = QuotationRepository().get_by_id(ref_id)
            if not quotation or str(quotation.order.company_id) != str(company_id):
                flash('Quotation not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_quotation_document(ref_id, quotation.order_id, company_id, doc_format)
        
        elif doc_type == 'contract':
            from app.repositories.repository import ContractRepository
            contract = ContractRepository().get_by_id(ref_id)
            if not contract or str(contract.order.company_id) != str(company_id):
                flash('Contract not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_contract_document(
                ref_id, contract.order_id, company_id, 
                quotation_id=contract.quotation_id, format=doc_format
            )
        
        elif doc_type == 'handover':
            from app.repositories.repository import HandoverRecordRepository
            handover = HandoverRecordRepository().get_by_id(ref_id)
            if not handover or str(handover.order.company_id) != str(company_id):
                flash('Handover record not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_delivery_document(ref_id, handover.order_id, company_id, doc_format)
        
        elif doc_type == 'payment':
            from app.repositories.repository import PaymentReportRepository
            payment = PaymentReportRepository().get_by_id(ref_id)
            if not payment or str(payment.order.company_id) != str(company_id):
                flash('Payment report not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_payment_document(ref_id, payment.order_id, company_id, doc_format)
        
        else:
            flash('Unknown document type', 'error')
            return redirect(request.referrer)
        
        flash('Document generated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error generating document: {str(e)}")
        flash(f'Error generating document: {str(e)}', 'error')
    
    return redirect(request.referrer)


@dashboard_bp.route('/documents/<document_id>/download')
@login_required
def download_document(document_id):
    """Download document"""
    company_id = get_current_company_id()
    doc_repo = DocumentRepository()
    
    document = doc_repo.get_by_id(document_id)
    if not document or str(document.company_id) != str(company_id):
        flash('Document not found or access denied', 'error')
        return redirect(request.referrer)
    
    if not os.path.exists(document.file_path):
        flash('Document file not found', 'error')
        return redirect(request.referrer)
    
    try:
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=f"{document.document_name}.{document.document_format}"
        )
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        flash('Error downloading document', 'error')
        return redirect(request.referrer)


@dashboard_bp.route('/documents/<order_id>')
@login_required
def list_documents(order_id):
    """List documents for order"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    doc_service = DocumentService()
    documents = doc_service.list_documents_for_order(order_id)
    
    return render_template('documents/list.html', order=order, documents=documents)


@dashboard_bp.route('/api/contracts/<contract_id>')
@login_required
def get_contract_detail(contract_id):
    """Get contract details as JSON - for AJAX calls"""
    company_id = get_current_company_id()
    try:
        from app.repositories.repository import ContractRepository
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
@dashboard_bp.route('/api/quotations/<quotation_id>')
@login_required
def get_quotation_detail(quotation_id):
    """Get quotation details as JSON - for AJAX calls"""
    company_id = get_current_company_id()
    
    try:
        from app.repositories.repository import QuotationRepository
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
            flash('Tạo cửa hàng thành công', 'success')
            return redirect(url_for('dashboard.list_stores'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating store: {e}", exc_info=True)
            db.session.rollback()
            flash('Lỗi khi tạo cửa hàng', 'error')
    return render_template('stores/create.html')


@dashboard_bp.route('/stores/<store_id>/edit', methods=['GET', 'POST'])
@store_admin_required
def edit_store(store_id):
    """Edit store details — store_admin may only edit their own store."""
    company_id = get_current_company_id()
    from app.models.models import Store as _Store
    store = db.session.query(_Store).filter_by(id=store_id, company_id=company_id, is_active=True).first()
    if not store:
        flash('Cửa hàng không tìm thấy', 'error')
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
                manager_name = request.form.get('manager_name', '').strip() or None,
                phone        = request.form.get('phone', '').strip() or None,
                address      = request.form.get('address', '').strip() or None,
                city         = request.form.get('city', '').strip() or None,
            )
            flash('Cập nhật cửa hàng thành công', 'success')
            return redirect(url_for('dashboard.list_stores'))
        except Exception as e:
            logger.error(f"Error updating store: {e}", exc_info=True)
            db.session.rollback()
            flash('Lỗi khi cập nhật cửa hàng', 'error')
    return render_template('stores/edit.html', store=store)


@dashboard_bp.route('/stores/<store_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_store(store_id):
    """Deactivate a store"""
    company_id = get_current_company_id()
    from app.models.models import Store as _Store
    store = db.session.query(_Store).filter_by(id=store_id, company_id=company_id).first()
    if not store:
        flash('Cửa hàng không tìm thấy', 'error')
    else:
        try:
            StoreService().deactivate_store(store_id)
            flash(f'Cửa hàng "{store.name}" đã bị vô hiệu hóa', 'warning')
        except Exception as e:
            logger.error(f"Error deactivating store: {e}", exc_info=True)
            flash('Lỗi khi vô hiệu hóa cửa hàng', 'error')
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
                flash('Không có quyền tạo tài khoản Quản Trị Công Ty', 'error')
                return render_template('users/create.html', stores=stores)
            # company_admin must not have a store_id
            if role == 'company_admin':
                store_id = None
            # store_admin always creates inside their own store
            if not is_company_admin():
                store_id = get_current_store_id()
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
            )
            flash('Tạo người dùng thành công', 'success')
            return redirect(url_for('dashboard.list_users'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating user: {e}", exc_info=True)
            db.session.rollback()
            flash('Lỗi khi tạo người dùng', 'error')
    return render_template('users/create.html', stores=stores)


@dashboard_bp.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@store_admin_required
def edit_user(user_id):
    """Edit user profile / role / store assignment — store_admin may only edit users in their store."""
    company_id = get_current_company_id()
    from app.models.models import User as _User
    target = db.session.query(_User).filter_by(id=user_id, company_id=company_id, is_active=True).first()
    if not target:
        flash('Người dùng không tìm thấy', 'error')
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
                flash('Không có quyền thiết lập vai trò Quản Trị Công Ty', 'error')
                return render_template('users/edit.html', target=target, stores=stores)
            if role == 'company_admin':
                store_id = None
            # store_admin always keeps the user in their own store
            if not is_company_admin():
                store_id = get_current_store_id()
            password = request.form.get('password', '').strip() or None
            UserService().update_user(
                user_id   = user_id,
                full_name = request.form.get('full_name', '').strip() or None,
                email     = request.form.get('email', '').strip() or None,
                phone     = request.form.get('phone', '').strip() or None,
                position  = request.form.get('position', '').strip() or None,
                role      = role,
                store_id  = uuid.UUID(str(store_id)) if store_id else None,
                password  = password,
            )
            flash('Cập nhật người dùng thành công', 'success')
            return redirect(url_for('dashboard.list_users'))
        except Exception as e:
            logger.error(f"Error updating user: {e}", exc_info=True)
            db.session.rollback()
            flash('Lỗi khi cập nhật người dùng', 'error')
    return render_template('users/edit.html', target=target, stores=stores)


@dashboard_bp.route('/users/<user_id>/deactivate', methods=['POST'])
@store_admin_required
def deactivate_user(user_id):
    """Deactivate a user account — store_admin may only deactivate users in their store."""
    company_id = get_current_company_id()
    from app.models.models import User as _User
    target = db.session.query(_User).filter_by(id=user_id, company_id=company_id).first()
    if not target:
        flash('Người dùng không tìm thấy', 'error')
    elif str(target.id) == str(g.user.id):
        flash('Không thể vô hiệu hóa tài khoản của chính mình', 'error')
    elif not is_company_admin() and str(target.store_id) != str(get_current_store_id()):
        abort(403)
    else:
        try:
            UserService().deactivate_user(user_id)
            flash(f'Tài khoản "{target.full_name}" đã bị vô hiệu hóa', 'warning')
        except Exception as e:
            logger.error(f"Error deactivating user: {e}", exc_info=True)
            flash('Lỗi khi vô hiệu hóa tài khoản', 'error')
    return redirect(url_for('dashboard.list_users'))
