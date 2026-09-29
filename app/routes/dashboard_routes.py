"""
Dashboard and main application routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, send_file, current_app, session, abort
from app.utils.i18n import t
from app.utils.auth_utils import (
    login_required, company_admin_required, store_admin_required,
    ensure_tenant_access, ensure_store_access,
    get_current_company_id, get_current_store_id, get_current_company,
    get_accessible_store_ids, is_company_admin,
)
from app.services.money import compute_totals, subtotal_from_items, totals_from_form
from app.services.workflow_service import ACTION_HANDOVER_CREATE, WorkflowService
from app.services.services import (
    StoreService, UserService, CustomerService, OrderService, QuotationService,
    ContractService, HandoverRecordService, PaymentReportService, DocumentService,
    MaterialService, SupplierService, order_commitment, plan_lock_reason,
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
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')



def _safe_back_url(default):
    """Where to send the user back to, when the answer is "where you were".

    `redirect(_safe_back_url(url_for('dashboard.index')))` looks harmless and is not. Two ways it goes
    wrong, both invisible to whoever wrote it:

      * a user who opened the link directly, used a bookmark, or whose browser
        strips the header has no referrer, and `redirect(None)` does not fail -
        it emits `Location: None`, so the browser lands on a 404 page named
        "None" straight after being told the action failed;
      * the header is set by whoever sent the user here, so a page on another
        site can bounce them back out through us.

    `_is_safe_redirect_url` already refuses the second for `next` parameters,
    but it requires a relative path and a referrer is absolute, so it cannot be
    reused directly. Same-origin is the test that fits a referrer.
    """
    referrer = request.referrer
    if not referrer:
        return default
    parsed = urlparse(referrer)
    if not parsed.scheme and not parsed.netloc:
        return referrer if referrer.startswith('/') else default
    if parsed.netloc == urlparse(request.host_url).netloc:
        return referrer
    return default


def _is_safe_redirect_url(target):
    """Chỉ cho phép quay lại đường dẫn nội bộ của chính site.

    Dùng cho các route nhận `next`/referrer từ trình duyệt: nếu không kiểm,
    kẻ tấn công có thể dựng link đưa người dùng ra site ngoài sau khi thao
    tác (open redirect). Chỉ nhận đường dẫn tương đối bắt đầu bằng một dấu
    '/' — loại luôn '//evil.com' và mọi thứ có scheme.
    """
    if not target:
        return False
    parsed = urlparse(target)
    return (
        not parsed.scheme
        and not parsed.netloc
        and target.startswith('/')
        and not target.startswith('//')
    )


@dashboard_bp.before_request
def _enforce_feature_permissions():
    """RBAC: block a logged-in regular user from feature areas they weren't granted.

    Admins pass; unauthenticated requests are handled by each view's
    login_required.

    An endpoint nobody has assigned to an area does NOT pass. It used to —
    `feature_for_endpoint` inferred the area from the endpoint's name and
    returned None when no word matched, so a route named unlike its area was
    silently open to every logged-in user. `save_plan_norm` was exactly that.
    Now the map is written out by hand and an absent endpoint raises, which is
    refused and logged loudly enough to be fixed rather than lived with.
    """
    from app.utils.auth_utils import current_user_can
    from app.utils.permission_map import UnmappedEndpoint, feature_for_endpoint
    if 'user_id' not in session:
        return
    try:
        feature = feature_for_endpoint(request.endpoint)
    except UnmappedEndpoint as missing:
        logger.error(
            'Endpoint %s is in no permission area; refusing. Add it to '
            'app/utils/permission_map.py.', missing)
        abort(403)
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
    # Optional: a line may state its own VAT rate. Absent or blank means "use
    # the document's rate", which is what every existing form sends, so
    # nothing changes for a screen that does not offer the field.
    line_vat = form.getlist('item_vat_rate[]')
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
        stated_vat = line_vat[i] if i < len(line_vat) else ''
        if stated_vat not in (None, ''):
            rate = float(stated_vat)
            if rate < 0:
                raise ValueError(t('VAT rate cannot be negative'))
            item['vat_rate'] = rate
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
    return redirect(_safe_back_url(url_for('dashboard.index')))


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
        # is_active matters: every customer LIST and lookup filters it, so
        # counting deactivated customers here made the front page disagree with
        # the page it links to - 4 on the card, 3 in the list.
        total_customers = db.session.query(_Customer).filter_by(
            company_id=company_id, is_active=True).count()
    else:
        # One query rather than one per store, and the same method the
        # company-wide branch uses — so the two paths cannot drift apart.
        all_orders = order_repo.get_orders_for_company(
            company_id, store_ids=accessible_store_ids)
        total_customers = db.session.query(_Customer).filter(
            _Customer.store_id.in_(accessible_store_ids),
            _Customer.is_active == True,
        ).count()

    total_orders = len(all_orders)
    in_progress  = sum(1 for o in all_orders if not o.is_canceled and o.lifecycle and not o.lifecycle.completed)
    completed    = sum(1 for o in all_orders if o.lifecycle and o.lifecycle.completed)
    canceled     = sum(1 for o in all_orders if o.is_canceled)

    # Recent orders (last 10)
    order_service = OrderService()
    recent_orders = order_service.list_orders_for_company(
        company_id, page=1, per_page=10,
        store_ids=None if is_company_admin() else accessible_store_ids)

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
            # Blank CLEARS the closing date rather than leaving it — the other
            # fields here read "blank means unchanged", but for this one that
            # would make reopening a period impossible through the screen that
            # closed it.
            closed_str = request.form.get('books_closed_through', '').strip()
            company.books_closed_through = _parse_date(closed_str) if closed_str else None
            # Bank accounts from JSON textarea
            bank_json = request.form.get('bank_accounts', '').strip()
            bank_error = False
            try:
                company.bank_accounts = _json.loads(bank_json) if bank_json else []
            except Exception:
                # The rows are serialised by JavaScript, so this is rare - but
                # swallowing it meant the bank details were quietly left as they
                # were while the screen reported success. They are printed on
                # payment documents; the user has to know they did not change.
                bank_error = True
            db.session.commit()
            if bank_error:
                flash(t('Đã lưu cài đặt, nhưng KHÔNG đọc được danh sách tài '
                        'khoản ngân hàng nên phần này giữ nguyên như cũ.'),
                      'warning')
            else:
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

    # How many documents each template has printed. A template with any is
    # offered Deactivate rather than Delete, because deleting it would orphan
    # the link recording what those documents came out of.
    from app.models.models import Document as _Doc
    printed = {}
    for tpl in all_templates:
        printed[str(tpl.id)] = _Doc.query.filter_by(template_id=tpl.id).count()

    from app.services.printing import PRINTABLE_TYPES
    return render_template('settings/templates.html', templates=all_templates,
                           printed=printed,
                           printable_types=PRINTABLE_TYPES,
                           printable_labels=dict(PRINTABLE_TYPES))


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

    # Validated against the same list the form renders from. Without this the
    # form could be narrowed and the endpoint would still accept anything,
    # which is how a template ends up under a type no screen can manage.
    from app.services.printing import is_printable_type
    if not is_printable_type(doc_type):
        flash(t('Loại chứng từ không hợp lệ.'), 'error')
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

        # Version N+1 within this company and document type. Counted from
        # the highest number ever used rather than from how many rows exist,
        # for the same reason document numbers are: deleting version 2 of
        # three must not make the next upload version 3 again.
        highest = db.session.query(db.func.max(_DT.version)).filter_by(
            company_id=company_id, document_type=doc_type).scalar() or 0

        new_tpl = _DT(
            company_id=company_id,
            name=name,
            document_type=doc_type,
            description=description,
            template_file=safe_name,
            version=highest + 1,
            is_active=True,
        )
        db.session.add(new_tpl)
        db.session.commit()
        flash(t('Mẫu "%(name)s" đã được tải lên thành công.') % {'name': name}, 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error uploading template: {str(e)}", exc_info=True)
        flash(t('Không tải lên được mẫu. Vui lòng kiểm tra tệp và thử lại.'),
              'error')

    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/seed-default/<doc_type>',
                    methods=['POST'])
@company_admin_required
def seed_default_template(doc_type):
    """Turn a built-in Python layout into an editable template.

    Only the purchase order has one: its layout lived in Python, so becoming
    Cách A meant somebody authoring a .docx from scratch — which is how a
    migration stalls. The generated template REPRODUCES the built-in layout,
    so nothing about the document changes on the day it is created; what
    changes is that it can now be edited, versioned and replaced.
    """
    import os

    from app.models.models import DocumentTemplate as _DT
    from app.utils.procurement_template import (
        build_default_purchase_order_template,
    )
    from app.utils.production_template import (
        build_default_production_plan_template,
    )

    builders = {'purchase_order': build_default_purchase_order_template,
                'production_plan': build_default_production_plan_template}
    if doc_type not in builders:
        flash(t('Không có mẫu mặc định cho loại chứng từ này'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    company_id = get_current_company_id()
    try:
        templates_base = current_app.config.get(
            'TEMPLATES_FOLDER',
            os.path.join(current_app.root_path, 'uploads', 'templates'))
        from app.models.models import Company as _Co
        company = db.session.get(_Co, company_id)
        folder = (company.company_code if company else str(company_id))
        folder = folder.replace('/', '_').replace(chr(92), '_')
        company_dir = os.path.join(templates_base, folder)
        os.makedirs(company_dir, exist_ok=True)

        safe_name = f'{doc_type}_mac_dinh_{uuid.uuid4().hex[:8]}.docx'
        builders[doc_type](os.path.join(company_dir, safe_name))

        highest = db.session.query(db.func.max(_DT.version)).filter_by(
            company_id=company_id, document_type=doc_type).scalar() or 0
        db.session.query(_DT).filter_by(
            company_id=company_id, document_type=doc_type, is_active=True
        ).update({'is_active': False})
        db.session.add(_DT(
            company_id=company_id, name='Mẫu mặc định (sinh từ bản in sẵn có)',
            document_type=doc_type,
            description='Sinh tự động từ bố cục đang dùng. Sửa được, có phiên bản.',
            template_file=safe_name, version=highest + 1, is_active=True))
        db.session.commit()
        flash(t('Đã tạo mẫu mặc định — sửa lại tuỳ ý, bản in không đổi.'),
              'success')
    except Exception as exc:
        db.session.rollback()
        logger.error('Could not seed the default %s template: %s',
                     doc_type, exc, exc_info=True)
        flash(t('Không tạo được mẫu mặc định'), 'error')

    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/edit', methods=['POST'])
@company_admin_required
def edit_template(template_id):
    """Rename a template, or describe it. NOT replace what it prints.

    The name and description describe the ROW; the file is the shape of every
    document already produced from it. Swapping the file under a template that
    has printed something rewrites what we claim we sent, silently, and a
    `Document` pointing at that row would now point at a layout it never used.

    Uploading a replacement is the supported path: it makes version N+1 and
    leaves N intact, so the old paper stays reproducible.
    """
    from app.models.models import Document as _Doc
    from app.models.models import DocumentTemplate as _DT

    company_id = get_current_company_id()
    tpl = _DT.query.filter_by(id=template_id, company_id=company_id).first()
    if not tpl:
        flash(t('Không tìm thấy mẫu hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    name = (request.form.get('name') or '').strip()
    if name:
        tpl.name = name
    description = request.form.get('description')
    if description is not None:
        tpl.description = description.strip() or None

    replacement = request.files.get('template_file')
    if replacement and replacement.filename:
        flash(t('Muốn đổi nội dung mẫu thì tải lên bản mới — bản cũ vẫn được giữ lại.'),
              'warning')

    db.session.commit()
    flash(t('Đã cập nhật mẫu'), 'success')
    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/download',
                    methods=['GET'])
@company_admin_required
def download_template(template_id):
    """Open the template itself.

    There was no way to see what a template contained. An admin with four
    contract templates and four names had to print a real contract to find out
    which was which.
    """
    from app.models.models import DocumentTemplate as _DT
    from app.services.services import DocumentService

    company_id = get_current_company_id()
    tpl = _DT.query.filter_by(id=template_id, company_id=company_id).first()
    if not tpl:
        abort(404)

    path = DocumentService()._get_template_file_path(tpl)
    if not path or not os.path.exists(path):
        flash(t('Tệp mẫu không còn trên máy chủ'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    return send_file(path, as_attachment=True,
                     download_name=f'{tpl.name}_v{tpl.version}'
                                   f'{os.path.splitext(tpl.template_file)[1]}')


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
        flash(t('Mẫu "%(name)s" đã được vô hiệu hóa.') % {'name': tpl.name}, 'success')
    return redirect(url_for('dashboard.list_templates'))


@dashboard_bp.route('/settings/templates/<template_id>/delete', methods=['POST'])
@company_admin_required
def delete_template(template_id):
    """Remove a template that has never produced a document.

    Uploading to the wrong document type, or trying a draft, used to be
    permanent: deactivating hides a template from the generator but leaves it
    on the screen, so the list only ever grew.

    Deletion stops at the one place it would break something. Document.template_id
    records what each document was printed from, so removing a template that has
    produced documents would orphan that link and lose the answer to "what did
    this contract come out of". Those are refused, with the reason and the
    operation that does fit - deactivate.
    """
    company_id = get_current_company_id()
    from app.models.models import Document as _Doc
    from app.models.models import DocumentTemplate as _DT

    tpl = db.session.get(_DT, template_id)
    if not tpl or str(tpl.company_id) != str(company_id):
        flash(t('Không tìm thấy mẫu.'), 'error')
        return redirect(url_for('dashboard.list_templates'))

    used = _Doc.query.filter_by(template_id=tpl.id).count()
    if used:
        flash(t('Mẫu "%(name)s" đã dùng để in %(count)d chứng từ nên không '
                'xóa được — hãy vô hiệu hóa mẫu này thay vì xóa.')
              % {'name': tpl.name, 'count': used}, 'error')
        return redirect(url_for('dashboard.list_templates'))

    name = tpl.name
    stored = tpl.template_file
    db.session.delete(tpl)
    db.session.commit()

    # The row is what matters; a file that will not unlink is not worth
    # failing the request over, and the record is already gone.
    try:
        if stored and os.path.exists(stored):
            os.remove(stored)
    except OSError:
        logger.warning('Could not remove template file %s', stored)

    flash(t('Mẫu "%(name)s" đã xóa.') % {'name': name}, 'success')
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
        # Exclusive per document type: the screen shows one "Active" badge per
        # row and the generator asks for THE template of a type, so letting two
        # be active at once made the printed result depend on row order.
        replaced = _DT.query.filter(
            _DT.company_id == tpl.company_id,
            _DT.document_type == tpl.document_type,
            _DT.is_active.is_(True),
            _DT.id != tpl.id,
        ).all()
        for other in replaced:
            other.is_active = False
        tpl.is_active = True
        db.session.commit()
        if replaced:
            # Say what was retired, or the user cannot tell an exclusive
            # switch from an additive one.
            names = ', '.join(o.name for o in replaced)
            flash(t('Mẫu "%(name)s" đã được kích hoạt, thay cho: %(replaced)s.')
                  % {'name': tpl.name, 'replaced': names},
                  'success')
        else:
            flash(t('Mẫu "%(name)s" đã được kích hoạt.') % {'name': tpl.name}, 'success')
    return redirect(url_for('dashboard.list_templates'))


# ===== CUSTOMERS =====

def _apply_customer_search(query, search):
    """Narrow a customer query by name, code or phone.

    Search used to be a different code path from browsing: it called
    search_customers(), whose signature carries limit=20, and then set
    pagination to None. A shop with 25 customers named Nguyen saw twenty of
    them with no next-page link and nothing to say the list had been cut.

    Filtering the SAME query the browse path paginates removes the special case
    instead of adding a second one to keep in step.
    """
    if not search:
        return query
    from app.models.models import Customer as _C
    like = f'%{search}%'
    return query.filter(db.or_(_C.name.ilike(like),
                               _C.customer_code.ilike(like),
                               _C.phone.ilike(like)))


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

        q = _Customer.query.filter_by(store_id=store_id, is_active=True)
        q = _apply_customer_search(q, search)
        q = q.order_by(_Customer.customer_code)
        pagination = db.paginate(q, page=page, per_page=per_page, error_out=False)
        customers, total = pagination.items, pagination.total
    else:
        # "All Stores" — company admin sees every accessible store's customers
        q = _Customer.query.filter(
            _Customer.store_id.in_(accessible_ids), _Customer.is_active == True
        )
        q = _apply_customer_search(q, search)
        q = q.order_by(_Customer.customer_code)
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


@dashboard_bp.route('/customers/<customer_id>/deactivate', methods=['POST'])
@store_admin_required
def deactivate_customer(customer_id):
    """Retire a customer who has stopped buying.

    Customer.is_active already existed and every customer query honoured it;
    nothing ever set it, so a closed-down customer or a duplicate made by a
    typo stayed in the picker for good.

    Deactivate rather than delete for the same reason a template that printed
    documents cannot be deleted: orders, quotations and contracts point here,
    and removing the row would lose the name on paperwork already issued.
    Nothing can be orphaned by deactivating, so nothing blocks it.
    """
    company_id = get_current_company_id()
    customer = CustomerRepository().get_for_company(customer_id, company_id)
    if not customer:
        flash(t('Customer not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_customers'))

    customer.is_active = False
    db.session.commit()
    flash(t('Khách hàng "%(name)s" đã ngừng hoạt động. Chứng từ cũ giữ nguyên.')
          % {'name': customer.name}, 'success')
    return redirect(url_for('dashboard.list_customers'))


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
    search = (request.args.get('search') or '').strip()
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    from app.models.models import Customer as _Customer
    from app.models.models import Order as _Order
    query = _Order.query.filter(_Order.company_id == company_id, _Order.is_active == True)
    if not is_company_admin():
        accessible_ids = get_accessible_store_ids(company_id)
        query = query.filter(_Order.store_id.in_(accessible_ids))

    if search:
        # What a user has in hand when they go looking: the code on the
        # paperwork, what the job was called, whose it was — and, very often,
        # the number printed on a document rather than on the order itself. A
        # customer rings about "hợp đồng HĐ-2026-014"; that number lives on the
        # contract, and the search used to ignore it.
        #
        # The document numbers go in as subqueries rather than four more joins:
        # an order with two quotations would otherwise appear twice.
        from app.models.models import (
            Contract as _Contract, HandoverRecord as _Handover,
            PaymentReport as _Payment, Quotation as _Quotation,
        )
        like = f'%{search}%'
        document_matches = [
            db.session.query(model.order_id).filter(column.ilike(like))
            for model, column in (
                (_Quotation, _Quotation.quotation_number),
                (_Contract, _Contract.contract_number),
                (_Handover, _Handover.report_number),
                (_Payment, _Payment.report_number),
            )
        ]
        # The customer name needs the join, which is why this is an outerjoin -
        # an order with no customer must not vanish from an unrelated search.
        query = query.outerjoin(_Customer, _Order.customer_id == _Customer.id).filter(
            db.or_(
                _Order.order_code.ilike(like),
                _Order.title.ilike(like),
                _Customer.name.ilike(like),
                *[_Order.id.in_(sub) for sub in document_matches],
            )
        )

    # Where the order has got to. "Which are not paid yet" and "what is still
    # waiting to be handed over" are the daily questions, and the only way to
    # answer them was to page through reading badges.
    status = (request.args.get('status') or '').strip()
    if status:
        from app.models.models import LifecycleStatus as _Lifecycle
        query = query.outerjoin(_Lifecycle, _Lifecycle.order_id == _Order.id)
        conditions = {
            # Signed, so the money is owed, and not yet settled. A cancelled
            # order owes nothing, so it is not "unpaid".
            'unpaid': db.and_(_Lifecycle.contract_signed == True,
                              _Lifecycle.fully_paid != True,
                              _Order.is_canceled != True),
            'awaiting_handover': db.and_(_Lifecycle.handover_confirmed != True,
                                         _Order.is_canceled != True),
            'in_progress': db.and_(_Lifecycle.completed != True,
                                   _Order.is_canceled != True),
            'completed': _Lifecycle.completed == True,
            'canceled': _Order.is_canceled == True,
        }
        if status in conditions:
            query = query.filter(conditions[status])

    query = query.options(
        joinedload(_Order.customer),
        joinedload(_Order.lifecycle),
    ).order_by(_Order.created_at.desc())

    # error_out=False → an out-of-range page renders empty instead of 404.
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    return render_template('orders/list.html', orders=pagination.items,
                           pagination=pagination, page=page, search=search,
                           selected_status=status)


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

    # Does a framework agreement (HĐNT) cover this customer? If so the order's
    # "contract" step issues an Đơn đặt hàng citing it, instead of a whole new
    # contract. No agreement => nothing changes for this order.
    from app.models.models import OrderConfirmation
    from app.services.agreement_service import (
        DOC_ORDER_CONFIRMATION, AgreementService,
    )
    _order = order_details.get('order')
    doc_kind, agreement = AgreementService.resolve_document_kind(_order)
    order_details['document_kind'] = doc_kind
    order_details['master_agreement'] = agreement
    order_details['uses_agreement'] = (doc_kind == DOC_ORDER_CONFIRMATION)
    order_details['order_confirmation'] = OrderConfirmation.query.filter_by(
        order_id=_order.id, is_active=True).first()

    # Optional workflow rules are advice, not gates: show them where the user
    # decides, never as a dialog. An empty list renders nothing at all.
    from app.services.workflow_service import (
        ACTION_HANDOVER_CREATE as _A_HANDOVER,
        ACTION_PAYMENT_ADVANCE as _A_ADVANCE,
        ACTION_PAYMENT_FINAL as _A_FINAL,
        WorkflowService as _WF,
    )
    order_details['workflow_advisories'] = _WF.advisories(_order)

    # What the page OFFERS must be the same question the service ANSWERS when
    # the form arrives. The screen used to read lifecycle.advance_paid itself,
    # so a contract agreed at 0% never showed the handover or final payment
    # button at all, and a rule relaxed on the settings screen changed nothing
    # here.
    order_details['can_create_handover'] = _WF.can(_order, _A_HANDOVER)
    order_details['can_record_advance'] = _WF.can(_order, _A_ADVANCE)
    order_details['can_record_final'] = _WF.can(_order, _A_FINAL)

    # Read here, on the screen, because a ledger nobody can see answers no
    # question. This repo has six instances of finished work that nothing
    # reaches — a write-only stock movement table among them — and an audit
    # trail is exactly the kind of thing that becomes the seventh.
    from app.services.transitions import history_for_order, label_for
    order_details['document_history'] = history_for_order(order_id)
    order_details['action_label'] = label_for

    return render_template('orders/view.html', **order_details)


@dashboard_bp.route('/orders/<order_id>/order-confirmation', methods=['POST'])
@login_required
def issue_order_confirmation(order_id):
    """Issue an ĐƠN ĐẶT HÀNG for an order covered by a framework agreement.

    Replaces the full-contract step for that order. Item prices come from the
    agreement's price list where it covers them, and are snapshotted onto the
    document so a later price revision cannot rewrite it.
    """
    from app.services.agreement_service import (
        DOC_ORDER_CONFIRMATION, AgreementService,
    )

    company_id = get_current_company_id()
    order = OrderService().get_order(order_id, company_id)
    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    doc_kind, agreement = AgreementService.resolve_document_kind(order)
    if doc_kind != DOC_ORDER_CONFIRMATION or agreement is None:
        flash(t('This customer has no active framework agreement — create a contract instead'),
              'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    quotation = next((q for q in order.quotations
                      if q.is_active and not q.is_canceled and q.is_approved), None)
    if quotation is None:
        flash(t('An approved quotation is needed to issue an order confirmation'),
              'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    try:
        confirmation = AgreementService.create_confirmation(
            order=order,
            agreement=agreement,
            items=list(quotation.items or []),
            confirmation_number=(request.form.get('confirmation_number') or '').strip()
                                or f"DDH-{order.order_code}",
            confirmation_date=_parse_date(request.form.get('confirmation_date')),
            quotation_id=quotation.id,
            vat_rate=quotation.vat_rate,
            shipping_fee=quotation.shipping_fee or 0,
            another_fee=quotation.another_fee or 0,
            delivery_date=_parse_date(request.form.get('delivery_date')),
            delivery_address=request.form.get('delivery_address') or None,
            company=get_current_company(),
        )
        AgreementService.confirm(confirmation)
        flash(t('Order confirmation issued under framework agreement %(n)s')
              .replace('%(n)s', agreement.agreement_number), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error("Error issuing order confirmation: %s", e)
        db.session.rollback()
        flash(t('Error issuing order confirmation'), 'error')

    return redirect(url_for('dashboard.view_order', order_id=order_id))


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
                flash(t('Số báo giá "%(number)s" đã được dùng. Vui lòng chọn số khác.')
                      % {'number': quotation_number}, 'error')
                return render_template('quotations/create.html', order=order, company_vat_rate=company_vat_rate)
            
            # Parse items from request
            items, subtotal = parse_line_items(request.form, request.files, with_images=True)

            totals = totals_from_form(request.form, company=get_current_company(),
                                      subtotal=subtotal, items=items)
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            total = totals['total_amount']
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
            flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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

            totals = totals_from_form(request.form, company=get_current_company(),
                                      subtotal=subtotal, items=items)
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            total = totals['total_amount']
            
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
            flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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
        flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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
        flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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
                flash(t('Số hợp đồng "%(number)s" đã được dùng. Vui lòng chọn số khác.')
                      % {'number': contract_number}, 'error')
                from app.models.models import Company as _CompanyC
                _co = db.session.get(_CompanyC, order.company_id)
                return render_template('contracts/create.html', order=order, quotations=quotations, company=_co)
            
            # Parse items from form
            items, subtotal = parse_line_items(request.form)

            # Shipping/other fees come from quotation when referenced
            totals = totals_from_form(request.form, company=get_current_company(),
                                      subtotal=subtotal, items=items)
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            contract_value = totals['total_amount']

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
                    # The totals above were derived from the (empty) form, so they
                    # must be re-derived from the items actually being stored —
                    # otherwise the contract carries line items worth X while its
                    # contract_value column says 0.
                    totals = compute_totals(
                        subtotal=subtotal_from_items(items),
                        vat_rate=request.form.get('vat_rate'),
                        shipping_fee=shipping_fee,
                        another_fee=another_fee,
                        company=get_current_company(),
                        # A contract copying a quotation's lines must copy the
                        # rates on them; otherwise signing re-taxes a mixed
                        # quotation at one rate and the two documents disagree.
                        items=items,
                    )
                    subtotal = totals['subtotal']
                    vat_rate = totals['vat_rate']
                    vat_amount = totals['vat_amount']
                    contract_value = totals['total_amount']
                    advance_amount = round(contract_value * advance_percentage / 100, 2)

            # Single-active-contract invariant (mirrors ContractService.create_contract,
            # which this route bypasses by writing through the repository): a new
            # contract supersedes any previously active one on the same order.
            # Without this, downstream fee lookups — `next((c for c in
            # order.contracts if c.is_active ...))` — pick an arbitrary contract.
            superseded = db.session.query(Contract).filter(
                Contract.order_id == order_id,
                Contract.is_active == True,  # noqa: E712  (SQLAlchemy column comparison)
            ).all()
            for old_contract in superseded:
                old_contract.is_active = False
                logger.info(
                    "Deactivated previous contract %s superseded by %s",
                    old_contract.contract_number, contract_number,
                )
            
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
            
        except ValueError as e:
            # A business rule refusing the action carries the sentence that explains it
            # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
            # left the user with a red bar and nothing to act on.
            logger.info(f"Refused - creating contract: {str(e)}")
            flash(str(e), 'error')
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

            totals = totals_from_form(request.form, company=get_current_company(),
                                      subtotal=subtotal, items=items)
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            contract_value = totals['total_amount']
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
            
        except ValueError as e:
            # A business rule refusing the action carries the sentence that explains it
            # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
            # left the user with a red bar and nothing to act on.
            logger.info(f"Refused - updating contract: {str(e)}")
            flash(str(e), 'error')
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
    except ValueError as e:
        # A business rule refusing the action carries the sentence that explains it
        # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
        # left the user with a red bar and nothing to act on.
        logger.info(f"Refused - signing contract: {str(e)}")
        flash(str(e), 'error')
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
    
    order_id = contract.order_id
    try:
        # Through the service. This route used to set the four flags itself
        # and never called `ContractService.cancel_contract`, so the lifecycle
        # rollback in there ran only in tests — and cancelling the only
        # contract left the order believing it still had one.
        ContractService().cancel_contract(
            contract_id, order_id,
            reason=request.form.get('canceled_reason', ''))
        flash(t('Contract has been canceled successfully'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    except Exception as e:
        logger.error(f"Error canceling contract: {str(e)}")
        db.session.rollback()
        flash(t('Error canceling contract'), 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=order_id))


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
    
    try:
        OrderService().cancel_order(
            order_id, company_id,
            reason=request.form.get('canceled_reason', ''))
        flash(t('Order has been canceled successfully'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))
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
                flash(t('Số biên bản bàn giao "%(number)s" đã được dùng. Vui lòng chọn số khác.')
                      % {'number': report_number}, 'error')
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
                                       commitment=order_commitment(order),
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
            
            active_contract = next((c for c in order.contracts if c.is_active and not c.is_canceled), None)
            # A framework-agreement order has no contract; its commitment is
            # the confirmed Đơn đặt hàng, and that is where its fees live.
            _commitment = order_commitment(order) or active_contract
            totals = compute_totals(
                subtotal=subtotal,
                vat_rate=request.form.get('vat_rate'),
                # From the COMMITMENT, not from `active_contract`: that is
                # None on the framework path, and getattr(None, ...) is 0, so
                # the fees the customer agreed were dropped without a word.
                shipping_fee=getattr(_commitment, 'shipping_fee', 0) or 0,
                another_fee=getattr(_commitment, 'another_fee', 0) or 0,
                company=get_current_company(),
                items=items,
            )
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            total_amount = totals['total_amount']
            
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
            
        except ValueError as e:
            # A business rule refusing the action carries the sentence that explains it
            # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
            # left the user with a red bar and nothing to act on.
            logger.info(f"Refused - creating handover record: {str(e)}")
            flash(str(e), 'error')
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
                                       commitment=order_commitment(order),
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
    except ValueError as e:
        # A business rule refusing the action carries the sentence that explains it
        # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
        # left the user with a red bar and nothing to act on.
        logger.info(f"Refused - confirming handover: {str(e)}")
        flash(str(e), 'error')
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
                totals = compute_totals(
                    subtotal=subtotal,
                    vat_rate=request.form.get('vat_rate'),
                    shipping_fee=handover.shipping_fee or 0,
                    another_fee=handover.another_fee or 0,
                    company=get_current_company(),
                    items=items,
                )
                handover.subtotal = totals['subtotal']
                handover.vat_rate = totals['vat_rate']
                handover.vat_amount = totals['vat_amount']
                handover.total_amount = totals['total_amount']
            
            db.session.add(handover)
            db.session.commit()
            
            flash(t('Handover record updated successfully'), 'success')
            return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
        except ValueError as e:
            flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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
        logger.error("Error canceling handover: %s", e, exc_info=True)
        flash(t('Không hủy được biên bản bàn giao. Vui lòng thử lại.'), 'error')
    
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
    _commitment = order_commitment(order) or active_contract
    company = db.session.get(_Company, company_id)

    if request.method == 'POST':
        try:
            # Check for duplicate report number
            report_number = request.form.get('report_number', '').strip()
            from app.models.models import PaymentReport
            from app.repositories.repository import PaymentReportRepository as _PaymentRepo
            existing = _PaymentRepo().get_by_company_and_number(company_id, report_number)
            if existing:
                flash(t('Số phiếu thanh toán "%(number)s" đã được dùng. Vui lòng chọn số khác.')
                      % {'number': report_number}, 'error')
                from app.models.models import PaymentReport as _PR
                _adv = db.session.query(_PR).filter(_PR.order_id==order_id, _PR.payment_type=='advance', _PR.is_confirmed==True, _PR.is_canceled==False).all()
                return render_template('payments/create.html', order=order, default_type=default_type,
                                       commitment=order_commitment(order),
                                       active_contract=active_contract, company=company,
                                       confirmed_advance_payments=_adv,
                                       confirmed_advance_total=float(sum(p.advance_amount or 0 for p in _adv)),
                                       advance_skipped=bool(order.lifecycle and order.lifecycle.advance_skipped))

            payment_service = PaymentReportService()
            payment_type = request.form.get('payment_type')
            
            # Payment sequencing is NOT decided here. This screen used to
            # carry its own copy of the rules — advance after signing, final
            # after handover — which meant switching a rule off at
            # /settings/workflow changed nothing on the busiest money screen.
            # A setting that does nothing teaches people the settings do not
            # work. `PaymentReportService.create_payment_report` asks
            # `WorkflowService.require()`, which is the configurable gate, and
            # raises WorkflowBlocked (a ValueError) that the handler below
            # already turns into a message.
            
            # Parse work items
            items, subtotal = parse_line_items(request.form)

            totals = compute_totals(
                subtotal=subtotal,
                vat_rate=request.form.get('vat_rate'),
                # From the COMMITMENT, not from `active_contract`: that is
                # None on the framework path, and getattr(None, ...) is 0, so
                # the fees the customer agreed were dropped without a word.
                shipping_fee=getattr(_commitment, 'shipping_fee', 0) or 0,
                another_fee=getattr(_commitment, 'another_fee', 0) or 0,
                company=get_current_company(),
                items=items,
            )
            vat_rate = totals['vat_rate']
            vat_amount = totals['vat_amount']
            shipping_fee = totals['shipping_fee']
            another_fee = totals['another_fee']
            # A payment report may be raised with no line items, in which case
            # the operator types the amount directly.
            base_amount = (totals['subtotal'] + vat_amount) if items                 else float(request.form.get('amount') or 0)
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
            flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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

    return render_template('payments/create.html', order=order, default_type=default_type,
                                       commitment=order_commitment(order),
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
        # Record an audited waiver first: who skipped the step, when, and why.
        # This is the workflow engine's first-class replacement for the bare
        # `advance_skipped` boolean, which recorded that a step was skipped but
        # never by whom or for what reason.
        reason = (request.form.get('skip_reason') or '').strip()             or t('Advance payment skipped by agreement with the customer')
        try:
            WorkflowService.waive(
                order, ACTION_HANDOVER_CREATE, 'advance_paid',
                reason=reason, user_id=session.get('user_id'),
            )
        except ValueError as waiver_error:
            # A company that has configured advance_paid as `required` has
            # deliberately disallowed skipping; respect that configuration.
            flash(t('Không thể bỏ qua tạm ứng: %(message)s') % {'message': waiver_error}, 'error')
            return redirect(url_for('dashboard.view_order', order_id=order_id))

        lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
        lifecycle.advance_skipped = True
        lifecycle.advance_skipped_at = datetime.utcnow()
        # NOTE (2026-09): advance_paid is also set so that everything already
        # reading this flag (templates, reports, the old guards) keeps working.
        # It overstates reality — no money was received — so advance-payment
        # reporting counts skipped orders as paid. Superseding this with the
        # waiver alone is a business decision; see REFACTOR-2026Q3.md F23.
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

        # A branch manager confirms; anybody else raises a request. NOT a
        # refusal: somebody holding cash with nothing they can record borrows
        # the manager's password, and then the control is theatre.
        from app.services.approvals import request_or_do
        outcome = request_or_do(
            company_id=company_id, action='payment.confirm',
            target_type='payment_report', target_id=payment.id,
            user_role=session.get('role'), user_id=session.get('user_id'),
            reason=(request.form.get('reason') or '').strip() or None)

        if proof_path:
            # Attached either way. The proof is evidence of what the clerk saw,
            # and it is most useful to the person deciding.
            payment.proof_path = proof_path
            db.session.add(payment)
            db.session.commit()

        if outcome.performed:
            flash(t('Payment marked as confirmed'), 'success')
        else:
            flash(outcome.message, 'info')
    except ValueError as e:
        # A business rule refusing the action carries the sentence that explains it
        # (WorkflowBlocked subclasses ValueError). Flattening that to "Error"
        # left the user with a red bar and nothing to act on.
        logger.info(f"Refused - confirming payment: {str(e)}")
        flash(str(e), 'error')
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

            from app.services.books import may_change
            allowed, why = may_change(payment)
            if not allowed:
                flash(why, 'error')
                return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
            import json as _json

            bank_json = request.form.get('bank_account_info', '[]')
            try:
                bank_account_info = _json.loads(bank_json)
            except Exception:
                bank_account_info = []

            quot_ref_str = request.form.get('quotation_reference_date', '').strip()
            quot_ref_date = datetime.strptime(quot_ref_str, '%Y-%m-%d').date() if quot_ref_str else None

            # A DRAFT's lines can be corrected; a confirmed payment's cannot.
            # An accounting record that can be silently edited is worth less
            # than one that shows it was corrected — but a draft is not an
            # accounting record yet, and a clerk who typed the wrong quantity
            # had to cancel the slip and raise another, burning a document
            # number and leaving a cancellation somebody has to explain.
            #
            # No `item_name[]` at all means "I did not touch the lines", not
            # "delete them": this form is reached from more than one place.
            if payment.can_edit() and request.form.getlist('item_name[]'):
                items, subtotal = parse_line_items(request.form)
                totals = totals_from_form(request.form,
                                          company=get_current_company(),
                                          subtotal=subtotal, items=items)
                payment.items = items
                payment.subtotal = totals['subtotal']
                payment.vat_rate = totals['vat_rate']
                payment.vat_amount = totals['vat_amount']
                payment.shipping_fee = totals['shipping_fee']
                payment.another_fee = totals['another_fee']
                payment.amount = totals['total_amount']

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
            flash(t('Không lưu được: %(message)s') % {'message': e}, 'error')
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
        from app.services.approvals import request_or_do
        reason = request.form.get('reason', '').strip()
        outcome = request_or_do(
            company_id=company_id, action='payment.cancel',
            target_type='payment_report', target_id=payment.id,
            user_role=session.get('role'), user_id=session.get('user_id'),
            reason=reason or None)
        if outcome.performed:
            flash(t('Payment report canceled successfully'), 'success')
        else:
            flash(outcome.message, 'info')
    except Exception as e:
        logger.error("Error canceling payment: %s", e, exc_info=True)
        flash(t('Không hủy được phiếu thanh toán. Vui lòng thử lại.'), 'error')
    
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
                return redirect(_safe_back_url(url_for('dashboard.list_orders')))
            
            document = document_service.generate_quotation_document(ref_id, quotation.order_id, company_id, doc_format)
        
        elif doc_type == 'contract':
            contract = ContractRepository().get_by_id(ref_id)
            if not contract or str(contract.order.company_id) != str(company_id):
                flash(t('Contract not found'), 'error')
                return redirect(_safe_back_url(url_for('dashboard.list_orders')))
            
            document = document_service.generate_contract_document(
                ref_id, contract.order_id, company_id, 
                quotation_id=contract.quotation_id, format=doc_format
            )
        
        elif doc_type == 'handover':
            handover = HandoverRecordRepository().get_by_id(ref_id)
            if not handover or str(handover.order.company_id) != str(company_id):
                flash(t('Handover record not found'), 'error')
                return redirect(_safe_back_url(url_for('dashboard.list_orders')))
            
            document = document_service.generate_delivery_document(ref_id, handover.order_id, company_id, doc_format)
        
        elif doc_type == 'payment':
            payment = PaymentReportRepository().get_by_id(ref_id)
            if not payment or str(payment.order.company_id) != str(company_id):
                flash(t('Payment report not found'), 'error')
                return redirect(_safe_back_url(url_for('dashboard.list_orders')))
            
            document = document_service.generate_payment_document(ref_id, payment.order_id, company_id, doc_format)
            
        elif doc_type == 'payment_request':
            order = OrderRepository().get_by_id(ref_id)
            if not order or str(order.company_id) != str(company_id):
                flash(t('Order not found'), 'error')
                return redirect(_safe_back_url(url_for('dashboard.list_orders')))
                
            document = document_service.generate_payment_request_document(ref_id, company_id, doc_format)
        
        elif doc_type == 'agreement':
            # Both of these had a variable collector and no branch, so nothing
            # could reach them. A HĐNT is what the customer signs; an ĐĐH is
            # what a VAT invoice is raised against.
            document = document_service.generate_agreement_document(
                ref_id, company_id, doc_format)

        elif doc_type == 'order_confirmation':
            document = document_service.generate_order_confirmation_document(
                ref_id, company_id, doc_format)

        else:
            flash(t('Unknown document type'), 'error')
            return redirect(_safe_back_url(url_for('dashboard.list_orders')))

        # Tell the user the real output format. If PDF was requested but the
        # DOCX→PDF conversion was unavailable, the service falls back to DOCX —
        # surface that instead of a misleading "success".
        actual = getattr(document, 'document_format', doc_format)
        if doc_format == 'pdf' and actual != 'pdf':
            flash(t('Đã tạo tài liệu nhưng không chuyển được sang PDF — đã lưu dạng DOCX.'), 'warning')
        else:
            flash(t('Đã tạo tài liệu (%(fmt)s) thành công.') % {'fmt': actual.upper()}, 'success')
        
    except Exception as e:
        logger.error("Error generating document: %s", e, exc_info=True)
        flash(t('Không tạo được tài liệu. Vui lòng kiểm tra mẫu và thử lại.'),
              'error')
    
    return redirect(_safe_back_url(url_for('dashboard.list_orders')))


@dashboard_bp.route('/documents/<document_id>/download')
@login_required
def download_document(document_id):
    """Download document"""
    company_id = get_current_company_id()
    doc_repo = DocumentRepository()
    
    document = doc_repo.get_by_id(document_id)
    if not document or str(document.company_id) != str(company_id):
        flash(t('Document not found or access denied'), 'error')
        return redirect(_safe_back_url(url_for('dashboard.list_orders')))
    
    if not os.path.exists(document.file_path):
        flash(t('Document file not found'), 'error')
        return redirect(_safe_back_url(url_for('dashboard.list_orders')))
    
    try:
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=f"{document.document_name}.{document.document_format}"
        )
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        flash(t('Error downloading document'), 'error')
        return redirect(_safe_back_url(url_for('dashboard.list_orders')))


@dashboard_bp.route('/reports/receivables')
@login_required
def customer_receivables():
    """Who owes us money — a work queue, not a number.

    The dashboard already showed a single company-wide "receivable" figure,
    which tells you that money is owed but not by whom, so it could not be
    acted on. Chasing debt is a weekly job.
    """
    from app.services.report_service import ReportService

    company_id = get_current_company_id()
    rows = ReportService().customer_receivables(company_id)

    if request.args.get('only') == 'owing':
        rows = [r for r in rows if not r['settled']]

    # The footnote on this screen already said that money promised but not
    # confirmed still shows as owed. Listing those payments here turns that
    # caveat into something the reader can act on without leaving the page.
    pending = ReportService().unconfirmed_payments(company_id)

    return render_template(
        'reports/receivables.html',
        rows=rows,
        pending=pending,
        only=request.args.get('only') or '',
        total_outstanding=sum(r['outstanding'] for r in rows),
        owing_count=sum(1 for r in rows if not r['settled']))


@dashboard_bp.route('/reports')
@login_required
def reports():
    """Admin BI/KPI dashboard split by domain (sales / purchasing / accounting) — item 9."""
    from app.services.report_service import ReportService
    company_id = get_current_company_id()
    data = ReportService().dashboard(company_id)
    return render_template('reports/index.html', **data)


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
        return redirect(_safe_back_url(url_for('dashboard.list_orders')))

    order_id = document.order_id
    # Nút xoá giờ có mặt cả trên màn hình xem báo giá / hợp đồng / bàn giao /
    # thanh toán, nên phải quay lại đúng chỗ vừa bấm thay vì luôn nhảy về danh
    # sách tài liệu của đơn hàng. `next` do template gửi kèm; referrer là dự
    # phòng; danh sách tài liệu là chốt cuối.
    return_to = request.form.get('next')
    if not return_to and request.referrer:
        ref = urlparse(request.referrer)
        if ref.netloc == urlparse(request.host_url).netloc:
            return_to = ref.path + (('?' + ref.query) if ref.query else '')

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

    if return_to and _is_safe_redirect_url(return_to):
        return redirect(return_to)
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
        
        # Highest number for this type, WITHIN THE CALLER'S COMPANY ONLY.
        #
        # The algorithm — and the two defects fixed out of it in 2026-09 (a
        # company filter that was loaded but never applied, and a
        # PostgreSQL-only `regexp_replace`) — now lives in
        # `app/services/numbering.py`, because a second copy of it had grown
        # in `transfers.py` and had got it wrong a third way.
        from app.services.numbering import next_document_number

        return {'next_code': next_document_number(
            model_class, field_name, prefix, company_id, width=3)}, 200
        
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
        
        # Check if code exists — WITHIN THE CALLER'S COMPANY ONLY.
        # Document numbers are unique per company (see AUDIT D8), so an
        # unscoped check both leaked the existence of another tenant's
        # documents and wrongly rejected numbers this company may legitimately
        # use.
        exists = db.session.query(model_class).filter(
            model_class.company_id == company_id,
            getattr(model_class, field_name) == code,
        ).first() is not None
        
        return {'exists': exists}, 200
        
    except Exception as e:
        logger.error(f"Error checking code for {doc_type}: {str(e)}", exc_info=True)
        return {'error': f'Error: {str(e)}'}, 500


# =====================================================================
# =====================================================================
# WAREHOUSE MANAGEMENT
#
# Stock is counted per warehouse; a warehouse belongs to one branch. Until
# these screens existed, the model, the migration and the receiving path were
# all real and all unreachable — nobody could create a second warehouse, so the
# choice never appeared and every receipt resolved to the one the migration
# made. Recorded as §8.14; the third time that shape has turned up here.
# =====================================================================

@dashboard_bp.route('/warehouses', methods=['GET'])
@store_admin_required
def list_warehouses():
    """Warehouses, with the branch each one belongs to."""
    from app.models.models import Warehouse

    company_id = get_current_company_id()
    warehouses = (Warehouse.query
                  .filter_by(company_id=company_id)
                  .order_by(Warehouse.is_active.desc(),
                            Warehouse.warehouse_code)
                  .all())
    return render_template('warehouses/list.html', warehouses=warehouses)


@dashboard_bp.route('/approvals', methods=['GET'])
@store_admin_required
def list_approvals():
    """What is waiting on a decision, oldest first.

    Oldest first on purpose: the thing somebody has been waiting on longest is
    the thing most likely to have been worked around by now.
    """
    from app.models.models import ApprovalRequest
    from app.services.approvals import pending_for

    company_id = get_current_company_id()

    # A company admin oversees every branch; a branch manager sees their own.
    # `None` means unfiltered, so the two cases stay visibly different here
    # rather than a company admin being handed a list of all store ids that
    # happens to match everything.
    store_ids = None if is_company_admin() else get_accessible_store_ids(company_id)

    decided_query = ApprovalRequest.query.filter(
        ApprovalRequest.company_id == company_id,
        ApprovalRequest.status != ApprovalRequest.STATUS_PENDING)
    if store_ids is not None:
        decided_query = decided_query.filter(
            ApprovalRequest.store_id.in_(list(store_ids)))
    decided = (decided_query
               .order_by(ApprovalRequest.decided_at.desc())
               .limit(30).all())
    return render_template('approvals/list.html',
                           pending=pending_for(company_id, store_ids),
                           decided=decided)


@dashboard_bp.route('/approvals/<request_id>/<decision>', methods=['POST'])
@store_admin_required
def decide_approval(request_id, decision):
    from app.models.models import ApprovalRequest
    from app.services.approvals import approve, reject

    company_id = get_current_company_id()
    query = ApprovalRequest.query.filter_by(id=request_id,
                                            company_id=company_id)
    if not is_company_admin():
        # Same narrowing as the queue itself. Without it the screen hides the
        # request and the URL still decides it — which is the whole reason
        # this repo stopped treating a hidden button as a rule.
        query = query.filter(ApprovalRequest.store_id.in_(
            list(get_accessible_store_ids(company_id))))
    row = query.first()
    if not row:
        flash(t('Không tìm thấy đề nghị hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_approvals'))

    note = (request.form.get('note') or '').strip() or None
    try:
        if decision == 'approve':
            approve(row, user_id=session.get('user_id'), note=note)
            flash(t('Đã duyệt và thực hiện'), 'success')
        elif decision == 'reject':
            reject(row, user_id=session.get('user_id'), note=note)
            flash(t('Đã từ chối đề nghị'), 'success')
        else:
            flash(t('Quyết định không hợp lệ'), 'error')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error('Error deciding approval: %s', e, exc_info=True)
        db.session.rollback()
        flash(t('Lỗi khi xử lý đề nghị'), 'error')
    return redirect(url_for('dashboard.list_approvals'))


@dashboard_bp.route('/warehouses/transfers', methods=['GET'])
@store_admin_required
def list_stock_transfers():
    from app.models.models import StockTransfer

    company_id = get_current_company_id()
    transfers = (StockTransfer.query
                 .filter_by(company_id=company_id)
                 .order_by(StockTransfer.transfer_date.desc(),
                           StockTransfer.created_at.desc())
                 .all())
    return render_template('warehouses/transfers.html', transfers=transfers)


@dashboard_bp.route('/warehouses/transfers/create', methods=['GET', 'POST'])
@store_admin_required
def create_stock_transfer():
    """Move material from one warehouse to another, in one step.

    The alternative people fall back on is editing two quantities by hand,
    which is two chances to mistype and no record of why.
    """
    from app.models.models import Material
    from app.services.transfers import transfer_stock
    from app.services.warehouses import warehouses_of

    company_id = get_current_company_id()
    warehouses = warehouses_of(company_id)
    materials = (Material.query
                 .filter_by(company_id=company_id, is_active=True)
                 .order_by(Material.material_code).all())

    if request.method == 'POST':
        try:
            lines = []
            for material_id, quantity in zip(
                    request.form.getlist('material_id[]'),
                    request.form.getlist('quantity[]')):
                if not material_id or not quantity:
                    continue
                material = next((m for m in materials
                                 if str(m.id) == material_id), None)
                lines.append({
                    'material_id': material_id,
                    'quantity': quantity,
                    'unit': (material.unit.name
                             if material and material.unit else None),
                })
            transfer = transfer_stock(
                company_id=company_id,
                from_warehouse_id=request.form.get('from_warehouse_id'),
                to_warehouse_id=request.form.get('to_warehouse_id'),
                lines=lines,
                transfer_date=_parse_date(request.form.get('transfer_date'))
                or date.today(),
                notes=(request.form.get('notes') or '').strip() or None)
            flash(t('Đã điều chuyển kho: %(n)s') % {
                'n': transfer.transfer_number}, 'success')
            return redirect(url_for('dashboard.list_stock_transfers'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error('Error transferring stock: %s', e, exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi điều chuyển kho'), 'error')

    return render_template('warehouses/transfer_form.html',
                           warehouses=warehouses, materials=materials)


@dashboard_bp.route('/warehouses/create', methods=['GET', 'POST'])
@company_admin_required
def create_warehouse():
    from app.models import Store
    from app.models.models import Warehouse

    company_id = get_current_company_id()
    stores = Store.query.filter_by(company_id=company_id,
                                   is_active=True).order_by(Store.name).all()
    if request.method == 'POST':
        try:
            code = (request.form.get('warehouse_code') or '').strip()
            name = (request.form.get('name') or '').strip()
            store_id = request.form.get('store_id') or None
            if not code or not name or not store_id:
                raise ValueError(t('Mã kho, tên kho và chi nhánh đều bắt buộc'))
            if Warehouse.query.filter_by(company_id=company_id,
                                         warehouse_code=code).first():
                raise ValueError(t('Mã kho này đã được dùng'))
            if not Store.query.filter_by(id=store_id,
                                         company_id=company_id).first():
                raise ValueError(t('Chi nhánh không thuộc công ty này'))

            warehouse = Warehouse(company_id=company_id, store_id=store_id,
                                  warehouse_code=code, name=name,
                                  is_active=True)
            db.session.add(warehouse)
            db.session.flush()
            _set_default_warehouse(warehouse,
                                   bool(request.form.get('is_default')))
            db.session.commit()
            flash(t('Đã tạo kho'), 'success')
            return redirect(url_for('dashboard.list_warehouses'))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'error')
        except Exception as e:
            logger.error('Error creating warehouse: %s', e, exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi tạo kho'), 'error')
    return render_template('warehouses/form.html', warehouse=None,
                           stores=stores)


@dashboard_bp.route('/warehouses/<warehouse_id>/edit', methods=['GET', 'POST'])
@company_admin_required
def edit_warehouse(warehouse_id):
    from app.models import Store
    from app.models.models import Warehouse

    company_id = get_current_company_id()
    warehouse = Warehouse.query.filter_by(id=warehouse_id,
                                          company_id=company_id).first()
    if not warehouse:
        flash(t('Không tìm thấy kho hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_warehouses'))

    stores = Store.query.filter_by(company_id=company_id,
                                   is_active=True).order_by(Store.name).all()
    if request.method == 'POST':
        try:
            name = (request.form.get('name') or '').strip()
            if not name:
                raise ValueError(t('Tên kho là bắt buộc'))
            warehouse.name = name
            store_id = request.form.get('store_id')
            if store_id and Store.query.filter_by(
                    id=store_id, company_id=company_id).first():
                warehouse.store_id = store_id
            _set_default_warehouse(warehouse,
                                   bool(request.form.get('is_default')))
            db.session.commit()
            flash(t('Đã lưu kho'), 'success')
            return redirect(url_for('dashboard.list_warehouses'))
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'error')
        except Exception as e:
            logger.error('Error editing warehouse: %s', e, exc_info=True)
            db.session.rollback()
            flash(t('Lỗi khi lưu kho'), 'error')
    return render_template('warehouses/form.html', warehouse=warehouse,
                           stores=stores)


@dashboard_bp.route('/warehouses/<warehouse_id>/deactivate', methods=['POST'])
@company_admin_required
def deactivate_warehouse(warehouse_id):
    """Close a warehouse — refused while it still holds stock.

    Hiding a warehouse that holds material does not move the material: the
    quantity stays in the database, disappears from every screen, and the
    company's stock silently drops by that much. Refusing, and saying how many
    materials are in there, leaves the user something they can act on.
    """
    from app.models.models import MaterialStock, Warehouse

    company_id = get_current_company_id()
    warehouse = Warehouse.query.filter_by(id=warehouse_id,
                                          company_id=company_id).first()
    if not warehouse:
        flash(t('Không tìm thấy kho hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_warehouses'))

    holding = (MaterialStock.query
               .filter(MaterialStock.warehouse_id == warehouse.id,
                       MaterialStock.current_quantity > 0)
               .count())
    if holding:
        flash(t('Kho này còn tồn vật tư. Hãy chuyển hết đi trước khi ngừng dùng kho.'),
              'error')
        return redirect(url_for('dashboard.list_warehouses'))

    warehouse.is_active = False
    warehouse.is_default = False
    db.session.commit()
    flash(t('Đã ngừng dùng kho'), 'success')
    return redirect(url_for('dashboard.list_warehouses'))


def _set_default_warehouse(warehouse, wanted):
    """At most one default per branch, and never a default that is closed."""
    from app.models.models import Warehouse

    if not wanted:
        warehouse.is_default = False
        return
    (Warehouse.query
     .filter(Warehouse.store_id == warehouse.store_id,
             Warehouse.id != warehouse.id)
     .update({'is_default': False}, synchronize_session=False))
    warehouse.is_default = True


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
            flash(t('Cửa hàng "%(name)s" đã bị vô hiệu hóa') % {'name': store.name}, 'warning')
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
    # `stores` itself is not rendered; the template resolves names through
    # store_map. Passing both invites the next edit to use the wrong one.
    return render_template('users/list.html', users=users, store_map=store_map)


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
            flash(t('Tài khoản "%(name)s" đã bị vô hiệu hóa') % {'name': target.full_name}, 'warning')
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
    page = request.args.get('page', 1, type=int)
    low_only = request.args.get('low_stock') in ('1', 'true', 'on')
    pagination = svc.list_materials(company_id, category_id=category_id,
                                    search=search, page=page)

    # "Show me only the ones running out" was a whole second screen
    # (/materials/low-stock) that displayed four columns this list already
    # shows. The screen is gone; the capability is not, because it is the
    # reason people opened that menu item.
    #
    # Filtered in Python, like `ProductionPlanService.low_stock_materials`
    # does, because `is_low_stock` compares a total assembled across stores
    # and is not a column SQL can filter on.
    items = [m for m in pagination.items if m.is_low_stock] if low_only         else pagination.items

    categories = svc.list_categories(company_id)
    return render_template('materials/list.html',
                           materials=items,
                           pagination=pagination,
                           categories=categories,
                           selected_category_id=category_id,
                           low_only=low_only,
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
            flash(t('Nguyên vật liệu "%(name)s" đã được tạo') % {'name': mat.name}, 'success')
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

    # The history, on the screen where "why does it say this?" is asked. A
    # ledger nobody can read is a ledger that only costs writes.
    from app.models.models import StockMovement
    movements = (StockMovement.query
                 .filter_by(company_id=company_id, material_id=mat.id)
                 .order_by(StockMovement.created_at.desc())
                 .limit(50).all())
    return render_template('materials/view.html', material=mat,
                           stock_entries=stock_entries, movements=movements)


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
        flash(t('NVL "%(name)s" đã bị vô hiệu hóa') % {'name': mat.name}, 'warning')
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


# ===== WORKFLOW RULES (configurable order process) =====

@dashboard_bp.route('/settings/workflow', methods=['GET', 'POST'])
@company_admin_required
def workflow_settings():
    """Company-admin page for the order workflow.

    This is the screen that makes the workflow engine usable: the rules
    already exist per company, but until now only a developer could change
    them. An operator can now relax a step to `optional`, mark it `waivable`
    (skippable with a recorded reason), or turn it off entirely — the exact
    scenarios the business raised, such as taking a deposit before the
    contract is formally signed.
    """
    from app.models.models import WorkflowRule
    from app.services.workflow_service import (
        ACTION_LABELS_VI, ALL_ACTIONS, PREREQUISITE_LABELS,
        PREREQUISITE_LABELS_VI, WorkflowService,
    )

    company_id = get_current_company_id()

    if request.method == 'POST':
        if request.form.get('action') == 'reset':
            WorkflowService.seed_defaults(company_id, overwrite=True)
            flash(t('Workflow rules reset to the standard process'), 'success')
            return redirect(url_for('dashboard.workflow_settings'))

        if request.form.get('action') == 'save_matrix':
            # The grid names a cell for every action/prerequisite pairing the
            # engine can express, so setting a cell creates the rule and
            # blanking it deletes the rule. Nothing outside those pairings is
            # accepted: anything else arriving here was hand-made.
            existing = {
                (rule.action, rule.prerequisite): rule
                for rule in WorkflowRule.query.filter_by(
                    company_id=company_id).all()
            }
            for action in ALL_ACTIONS:
                for prerequisite in PREREQUISITE_LABELS:
                    mode = (request.form.get(f'cell_{action}_{prerequisite}')
                            or '').strip()
                    rule = existing.get((action, prerequisite))

                    if mode not in WorkflowRule.MODES:
                        if rule is not None:
                            db.session.delete(rule)
                        continue

                    if rule is None:
                        rule = WorkflowRule(company_id=company_id,
                                            action=action,
                                            prerequisite=prerequisite)
                        rule.is_active = True     # a brand-new rule applies
                        db.session.add(rule)
                    # The grid owns the MODE and nothing else. It used to write
                    # is_active=True on every cell it touched, so saving it
                    # silently switched back on any rule the administrator had
                    # turned off in the list below — and the next person to hit
                    # that step was blocked by a rule its owner believed was
                    # off. Blanking a cell still deletes the rule: that is what
                    # "no rule here" means, and it is the grid's to say.
                    rule.mode = mode
            db.session.commit()
            flash(t('Workflow rules saved'), 'success')
            return redirect(url_for('dashboard.workflow_settings'))

        rules = WorkflowRule.query.filter_by(company_id=company_id).all()
        for rule in rules:
            mode = request.form.get(f'mode_{rule.id}')
            if mode in WorkflowRule.MODES:
                rule.mode = mode
            rule.is_active = request.form.get(f'active_{rule.id}') == 'on'
            message = (request.form.get(f'message_{rule.id}') or '').strip()
            rule.message = message or None
        db.session.commit()
        flash(t('Workflow rules saved'), 'success')
        return redirect(url_for('dashboard.workflow_settings'))

    rules = WorkflowRule.query.filter_by(company_id=company_id).order_by(
        WorkflowRule.action, WorkflowRule.sort_order).all()
    if not rules:
        # First visit: install the standard process so the page is never empty.
        WorkflowService.seed_defaults(company_id)
        rules = WorkflowRule.query.filter_by(company_id=company_id).order_by(
            WorkflowRule.action, WorkflowRule.sort_order).all()

    # The grid: rows are actions, columns are prerequisites, and the cell holds
    # how strictly that pairing applies. Every pairing has a cell whether or not
    # a rule exists, which is what removes the need for a create form.
    grid = {(rule.action, rule.prerequisite): rule.mode
            for rule in rules if rule.is_active}

    return render_template('settings/workflow.html',
                           rules=rules,
                           actions=ALL_ACTIONS,
                           # The English map is what the block MESSAGES are
                           # built from; the screen itself is read by
                           # Vietnamese users, and t() cannot translate a key
                           # that only exists as a variable.
                           prerequisite_labels=PREREQUISITE_LABELS_VI,
                           action_labels=ACTION_LABELS_VI,
                           grid=grid,
                           modes=WorkflowRule.MODES)


# ===== DATA STANDARDIZATION RULES =====

@dashboard_bp.route('/settings/standardization', methods=['GET', 'POST'])
@company_admin_required
def standardization_settings():
    """Company-admin page for input standardisation.

    Lets an administrator decide the house style per field — and, importantly,
    preview what a rule would do to a sample value before enabling it, since
    an automatic rule rewrites what users typed.
    """
    from app.models.models import NormalizationRule
    from app.services.normalization_service import NormalizationService
    from app.utils.text_normalize import PRIMITIVES, is_protected_field

    company_id = get_current_company_id()

    if request.method == 'POST':
        if request.form.get('action') == 'reset':
            NormalizationService.seed_defaults(company_id, overwrite=True)
            flash(t('Standardization rules reset to the defaults'), 'success')
            return redirect(url_for('dashboard.standardization_settings'))

        if request.form.get('action') == 'save_matrix':
            entity = (request.form.get('entity') or '').strip()
            fields = NormalizationService.configurable_fields(entity)
            if not fields:
                flash(t('Không tìm thấy nhóm dữ liệu này'), 'error')
                return redirect(url_for('dashboard.standardization_settings'))

            existing = {
                rule.field_name: rule
                for rule in NormalizationRule.query.filter_by(
                    company_id=company_id, entity_type=entity).all()
            }

            for field in fields:
                name = field['field_name']
                rule = existing.get(name)

                # An identifier is never normalized, whatever arrives in the
                # form. The screen locks these; this refuses a hand-made post.
                if field['protected']:
                    if rule is not None:
                        db.session.delete(rule)
                    continue

                chosen = [p for p in request.form.getlist(f'primitives_{entity}_{name}')
                          if p in PRIMITIVES]
                if not chosen:
                    # Clearing every cell on a row means "do not normalize this
                    # field". It used to DELETE the row — and the screen seeds
                    # the defaults whenever a company has no rows at all, so a
                    # company that deliberately cleared everything had it all
                    # switched back on the next time anyone opened the page.
                    # Keeping an empty, inactive row says "configured, and the
                    # answer is none", which is a different thing from "never
                    # configured" and is what stops the defaults returning.
                    if rule is not None:
                        rule.primitives = []
                        rule.is_active = False
                    continue

                mode = request.form.get(f'mode_{entity}_{name}')
                if mode not in NormalizationRule.MODES:
                    mode = NormalizationRule.MODE_AUTO

                if rule is None:
                    rule = NormalizationRule(company_id=company_id,
                                             entity_type=entity,
                                             field_name=name)
                    rule.is_active = True     # a brand-new rule applies
                    db.session.add(rule)
                # The grid owns which transforms and how strictly, and nothing
                # else. Writing is_active=True here meant saving the grid for
                # one field silently resumed rewriting text on another that
                # the administrator had switched off — and rewriting happens
                # at the moment a record is saved, where nobody is watching.
                rule.primitives = chosen
                rule.mode = mode

            db.session.commit()
            flash(t('Standardization rules saved'), 'success')
            return redirect(url_for('dashboard.standardization_settings',
                                    entity=entity))

        rules = NormalizationRule.query.filter_by(company_id=company_id).all()
        for rule in rules:
            mode = request.form.get(f'mode_{rule.id}')
            if mode in NormalizationRule.MODES:
                rule.mode = mode
            rule.is_active = request.form.get(f'active_{rule.id}') == 'on'
            chosen = request.form.getlist(f'primitives_{rule.id}')
            rule.primitives = [p for p in chosen if p in PRIMITIVES]
        db.session.commit()
        flash(t('Standardization rules saved'), 'success')
        return redirect(url_for('dashboard.standardization_settings'))

    rules = NormalizationRule.query.filter_by(company_id=company_id).order_by(
        NormalizationRule.entity_type, NormalizationRule.sort_order).all()
    if not rules:
        NormalizationService.seed_defaults(company_id)
        rules = NormalizationRule.query.filter_by(company_id=company_id).order_by(
            NormalizationRule.entity_type, NormalizationRule.sort_order).all()

    sample = request.args.get('sample') or 'cty tnhh  nội thất an phát'
    previews = {
        str(rule.id): NormalizationService.preview(sample, rule.primitives or [])
        for rule in rules
    }

    # The matrix: one row per text field of the chosen entity, one column per
    # primitive. Every field is present whether or not it has a rule, which is
    # why there is no "create rule" form - the row is already there.
    from app.services.normalization_service import NORMALIZED_ENTITIES
    entity = request.args.get('entity') or 'customer'
    if entity not in NORMALIZED_ENTITIES:
        entity = 'customer'
    matrix_fields = NormalizationService.configurable_fields(entity, company_id)
    for field in matrix_fields:
        field['preview'] = NormalizationService.preview(sample,
                                                        field['primitives'])

    return render_template('settings/standardization.html',
                           rules=rules,
                           primitives=PRIMITIVES,
                           sample=sample,
                           previews=previews,
                           entities=NORMALIZED_ENTITIES,
                           entity=entity,
                           matrix_fields=matrix_fields,
                           protected=is_protected_field)


# ===== HỢP ĐỒNG NGUYÊN TẮC (framework agreements) =====

def _owned_agreement(agreement_id, company_id):
    from app.models.models import MasterAgreement
    ma = MasterAgreement.query.get(agreement_id)
    if not ma or str(ma.company_id) != str(company_id):
        return None
    return ma


@dashboard_bp.route('/agreements', methods=['GET'])
@login_required
def list_agreements():
    """Framework agreements for the company."""
    from app.models.models import MasterAgreement

    company_id = get_current_company_id()
    status = request.args.get('status') or None
    search = (request.args.get('search') or '').strip() or None
    page = request.args.get('page', 1, type=int)

    q = MasterAgreement.query.filter_by(company_id=company_id)
    if status:
        q = q.filter_by(status=status)
    if search:
        q = q.filter(MasterAgreement.agreement_number.ilike(f'%{search}%'))
    pagination = q.order_by(MasterAgreement.effective_from.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('agreements/list.html',
                           agreements=pagination.items, pagination=pagination,
                           status=status or '', search=search or '',
                           statuses=(MasterAgreement.STATUS_DRAFT,
                                     MasterAgreement.STATUS_ACTIVE,
                                     MasterAgreement.STATUS_SUSPENDED,
                                     MasterAgreement.STATUS_EXPIRED,
                                     MasterAgreement.STATUS_TERMINATED))


@dashboard_bp.route('/agreements/create', methods=['GET', 'POST'])
@login_required
def create_agreement():
    from app.models.models import Customer, MasterAgreement

    company_id = get_current_company_id()
    customers = Customer.query.filter_by(company_id=company_id,
                                         is_active=True).order_by(Customer.name).all()

    if request.method == 'POST':
        try:
            number = (request.form.get('agreement_number') or '').strip()
            if not number:
                raise ValueError(t('Agreement number is required'))
            if MasterAgreement.query.filter_by(company_id=company_id,
                                               agreement_number=number).first():
                raise ValueError(t('Agreement number already exists'))

            effective_from = _parse_date(request.form.get('effective_from'))
            if not effective_from:
                raise ValueError(t('Effective from date is required'))

            # LTM 2005 Đ.301 caps a contractual penalty at 8% of the value of
            # the breached portion; refuse to record more than the law allows.
            penalty = float(request.form.get('penalty_pct') or 8)
            if penalty > 8:
                raise ValueError(
                    t('Penalty cannot exceed 8% (Điều 301 Luật Thương mại 2005)'))

            agreement = MasterAgreement(
                company_id=company_id,
                customer_id=request.form.get('customer_id'),
                agreement_number=number,
                signed_date=_parse_date(request.form.get('signed_date')),
                effective_from=effective_from,
                effective_to=_parse_date(request.form.get('effective_to')),
                auto_renew=request.form.get('auto_renew') == 'on',
                renewal_notice_days=int(request.form.get('renewal_notice_days') or 30),
                scope_description=request.form.get('scope_description') or None,
                payment_terms=request.form.get('payment_terms') or None,
                quality_terms=request.form.get('quality_terms') or None,
                delivery_terms=request.form.get('delivery_terms') or None,
                penalty_pct=penalty,
                dispute_resolution=request.form.get('dispute_resolution') or None,
                seller_representative=request.form.get('seller_representative') or None,
                buyer_representative=request.form.get('buyer_representative') or None,
                notes=request.form.get('notes') or None,
                status=MasterAgreement.STATUS_DRAFT,
            )
            db.session.add(agreement)
            db.session.commit()
            flash(t('Framework agreement created'), 'success')
            return redirect(url_for('dashboard.view_agreement',
                                    agreement_id=agreement.id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error("Error creating agreement: %s", e)
            db.session.rollback()
            flash(t('Error creating framework agreement'), 'error')

    return render_template('agreements/create.html', customers=customers)


@dashboard_bp.route('/agreements/<agreement_id>', methods=['GET'])
@login_required
def view_agreement(agreement_id):
    company_id = get_current_company_id()
    agreement = _owned_agreement(agreement_id, company_id)
    if not agreement:
        flash(t('Framework agreement not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_agreements'))
    # What has already been printed from this HĐNT. Possible only since
    # `source_type` started being written: a framework agreement has no
    # per-kind foreign key on Document, which is why this screen showed no
    # history at all while the four order-document screens did.
    from app.services.printing import documents_for
    return render_template('agreements/view.html', agreement=agreement,
                           documents=documents_for(agreement))


@dashboard_bp.route('/agreements/<agreement_id>/status', methods=['POST'])
@company_admin_required
def change_agreement_status(agreement_id):
    """Activate / suspend / terminate a framework agreement."""
    from app.services.agreement_service import AgreementService

    company_id = get_current_company_id()
    agreement = _owned_agreement(agreement_id, company_id)
    if not agreement:
        flash(t('Framework agreement not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_agreements'))

    action = request.form.get('action')
    reason = (request.form.get('reason') or '').strip() or None
    try:
        if action == 'activate':
            AgreementService.activate(agreement)
            flash(t('Framework agreement activated'), 'success')
        elif action == 'suspend':
            AgreementService.suspend(agreement, reason)
            flash(t('Framework agreement suspended — no new orders can cite it'),
                  'warning')
        elif action == 'terminate':
            AgreementService.terminate(agreement, reason)
            flash(t('Framework agreement terminated'), 'warning')
        else:
            flash(t('Unknown action'), 'error')
    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('dashboard.view_agreement', agreement_id=agreement_id))


@dashboard_bp.route('/agreements/<agreement_id>/prices', methods=['POST'])
@login_required
def add_agreement_price(agreement_id):
    """Add an agreed price line.

    A revision closes the previous line rather than overwriting it, so a past
    order can still be explained by the price that applied on its date.
    """
    from app.models.models import MasterAgreementPriceLine
    from app.services.agreement_service import product_key

    company_id = get_current_company_id()
    agreement = _owned_agreement(agreement_id, company_id)
    if not agreement:
        flash(t('Framework agreement not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_agreements'))

    try:
        name = (request.form.get('product_name') or '').strip()
        if not name:
            raise ValueError(t('Product name is required'))

        price = request.form.get('agreed_unit_price') or None
        discount = request.form.get('discount_pct') or None
        if not price and not discount:
            raise ValueError(t('Enter either an agreed price or a discount'))

        effective_from = _parse_date(request.form.get('effective_from'))
        key = product_key(name)

        # Close any currently-open line for the same product.
        for line in agreement.price_lines:
            if line.product_key == key and line.effective_to is None:
                line.effective_to = effective_from

        db.session.add(MasterAgreementPriceLine(
            agreement_id=agreement.id, product_key=key, product_name=name,
            unit=request.form.get('unit') or None,
            agreed_unit_price=price or None,
            discount_pct=discount or None,
            effective_from=effective_from))
        db.session.commit()
        flash(t('Price line added'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error("Error adding price line: %s", e)
        db.session.rollback()
        flash(t('Error adding price line'), 'error')

    return redirect(url_for('dashboard.view_agreement', agreement_id=agreement_id))


# ===== SUPPLIER INVOICES & PAYMENTS (closing the P2P loop) =====

def _owned_supplier_invoice(invoice_id, company_id):
    from app.models.models import SupplierInvoice
    inv = SupplierInvoice.query.get(invoice_id)
    if not inv or str(inv.company_id) != str(company_id):
        return None
    return inv


@dashboard_bp.route('/supplier-invoices', methods=['GET'])
@login_required
def list_supplier_invoices():
    from app.models.models import SupplierInvoice

    company_id = get_current_company_id()
    status = request.args.get('status') or None
    search = (request.args.get('search') or '').strip() or None
    page = request.args.get('page', 1, type=int)

    q = SupplierInvoice.query.filter_by(company_id=company_id)
    if status:
        q = q.filter_by(status=status)
    if search:
        q = q.filter(SupplierInvoice.invoice_number.ilike(f'%{search}%'))
    pagination = q.order_by(SupplierInvoice.invoice_date.desc()).paginate(
        page=page, per_page=20, error_out=False)

    return render_template('payables/list.html',
                           invoices=pagination.items, pagination=pagination,
                           status=status or '', search=search or '')


@dashboard_bp.route('/purchase-orders/<po_id>/invoice', methods=['GET', 'POST'])
@login_required
def create_supplier_invoice(po_id):
    """Record the supplier's hóa đơn GTGT against a purchase order."""
    from app.services.payables_service import PayablesService
    from app.services.procurement_service import ProcurementService

    company_id = get_current_company_id()
    po = ProcurementService().get_po(company_id, po_id)
    if not po:
        flash(t('Purchase order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_purchase_orders'))

    if request.method == 'POST':
        try:
            lines = []
            for line in po.lines:
                qty = request.form.get(f'qty_{line.id}')
                if not qty:
                    continue
                qty = float(qty)
                if qty <= 0:
                    continue
                lines.append({
                    'po_line_id': str(line.id),
                    'quantity': qty,
                    'unit_price': request.form.get(f'price_{line.id}')
                                  or line.unit_price,
                })

            invoice = PayablesService.create_invoice(
                po=po,
                invoice_number=(request.form.get('invoice_number') or '').strip(),
                invoice_series=(request.form.get('invoice_series') or '').strip() or None,
                invoice_date=_parse_date(request.form.get('invoice_date')),
                lines=lines,
                vat_rate=request.form.get('vat_rate'),
                seller_tax_code=(request.form.get('seller_tax_code') or '').strip() or None,
                notes=request.form.get('notes') or None,
                stated_total=(request.form.get('stated_total') or '').strip()
                or None,
            )
            if invoice.match_status != 'ok':
                flash(t('Invoice recorded with a matching discrepancy: ')
                      + (invoice.match_notes or ''), 'warning')
            else:
                flash(t('Supplier invoice recorded'), 'success')
            return redirect(url_for('dashboard.view_supplier_invoice',
                                    invoice_id=invoice.id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error("Error recording supplier invoice: %s", e)
            db.session.rollback()
            flash(t('Error recording supplier invoice'), 'error')

    return render_template('payables/create.html', po=po)


@dashboard_bp.route('/supplier-invoices/<invoice_id>', methods=['GET'])
@login_required
def view_supplier_invoice(invoice_id):
    from app.services.payables_service import PayablesService

    company_id = get_current_company_id()
    invoice = _owned_supplier_invoice(invoice_id, company_id)
    if not invoice:
        flash(t('Supplier invoice not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_supplier_invoices'))

    return render_template('payables/view.html', invoice=invoice,
                           payment_status=PayablesService.payment_status(invoice.po))


@dashboard_bp.route('/supplier-invoices/<invoice_id>/confirm', methods=['POST'])
@login_required
def confirm_supplier_invoice(invoice_id):
    from app.services.payables_service import PayablesService

    company_id = get_current_company_id()
    invoice = _owned_supplier_invoice(invoice_id, company_id)
    if not invoice:
        flash(t('Supplier invoice not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_supplier_invoices'))
    try:
        PayablesService.confirm_invoice(invoice)
        flash(t('Supplier invoice confirmed'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('dashboard.view_supplier_invoice', invoice_id=invoice_id))


@dashboard_bp.route('/supplier-invoices/<invoice_id>/pay', methods=['POST'])
@login_required
def pay_supplier_invoice(invoice_id):
    """Record a payment and allocate it to this invoice."""
    from app.models.models import SupplierPayment
    from app.services.payables_service import PayablesService

    company_id = get_current_company_id()
    invoice = _owned_supplier_invoice(invoice_id, company_id)
    if not invoice:
        flash(t('Supplier invoice not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_supplier_invoices'))

    try:
        method = request.form.get('method') or SupplierPayment.METHOD_TRANSFER
        payment = PayablesService.create_payment(
            company_id=company_id,
            supplier_id=invoice.supplier_id,
            payment_number=(request.form.get('payment_number') or '').strip(),
            payment_date=_parse_date(request.form.get('payment_date')),
            amount=request.form.get('amount') or 0,
            method=method,
            reference_number=(request.form.get('reference_number') or '').strip() or None,
        )
        PayablesService.allocate(payment, invoice, payment.amount)
        PayablesService.confirm_payment(payment)

        if method == SupplierPayment.METHOD_CASH:
            # Input-VAT deduction depends on non-cash payment evidence; the
            # rule has changed recently, so surface the fact rather than
            # enforce a threshold that may move again.
            flash(t('Payment recorded in CASH — check input-VAT deductibility with your accountant'),
                  'warning')
        else:
            flash(t('Payment recorded'), 'success')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error("Error recording supplier payment: %s", e)
        db.session.rollback()
        flash(t('Error recording payment'), 'error')

    return redirect(url_for('dashboard.view_supplier_invoice', invoice_id=invoice_id))


@dashboard_bp.route('/orders/<order_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    """Correct an order's descriptive fields.

    There was previously NO way to edit an order at all, so a typo in the
    title was permanent — it then printed on every document generated from
    that order.

    Deliberately narrow: only title, description and notes. The money is
    derived from the order's documents, and the customer/store determine which
    documents and permissions apply, so neither is editable here — changing
    them after documents exist would silently invalidate those documents.
    """
    company_id = get_current_company_id()
    order_service = OrderService()
    order = order_service.get_order(order_id, company_id)

    if not order:
        flash(t('Order not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    if order.is_canceled:
        flash(t('A canceled order cannot be edited'), 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    if request.method == 'POST':
        try:
            title = (request.form.get('title') or '').strip()
            if not title:
                raise ValueError(t('Title is required'))

            order.title = title
            order.description = (request.form.get('description') or '').strip() or None
            order.notes = (request.form.get('notes') or '').strip() or None
            order.updated_at = datetime.utcnow()
            db.session.commit()

            flash(t('Order updated'), 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error("Error updating order: %s", e)
            db.session.rollback()
            flash(t('Error updating order'), 'error')

    return render_template('orders/edit.html', order=order)


@dashboard_bp.route('/agreements/<agreement_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_agreement(agreement_id):
    """Correct a framework agreement.

    Allowed while the agreement is a DRAFT or ACTIVE (``can_edit``); an
    expired or terminated agreement is history and must not be rewritten,
    because orders were issued citing its terms.
    """
    from app.models.models import Customer, MasterAgreement

    company_id = get_current_company_id()
    agreement = _owned_agreement(agreement_id, company_id)
    if not agreement:
        flash(t('Framework agreement not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_agreements'))

    if not agreement.can_edit():
        flash(t('This agreement can no longer be edited'), 'error')
        return redirect(url_for('dashboard.view_agreement',
                                agreement_id=agreement_id))

    customers = Customer.query.filter_by(company_id=company_id,
                                         is_active=True).order_by(Customer.name).all()

    if request.method == 'POST':
        try:
            number = (request.form.get('agreement_number') or '').strip()
            if not number:
                raise ValueError(t('Agreement number is required'))
            clash = MasterAgreement.query.filter(
                MasterAgreement.company_id == company_id,
                MasterAgreement.agreement_number == number,
                MasterAgreement.id != agreement.id).first()
            if clash:
                raise ValueError(t('Agreement number already exists'))

            penalty = float(request.form.get('penalty_pct') or 8)
            if penalty > 8:
                raise ValueError(
                    t('Penalty cannot exceed 8% (Điều 301 Luật Thương mại 2005)'))

            effective_from = _parse_date(request.form.get('effective_from'))
            if not effective_from:
                raise ValueError(t('Effective from date is required'))

            agreement.agreement_number = number
            agreement.customer_id = request.form.get('customer_id') or agreement.customer_id
            agreement.signed_date = _parse_date(request.form.get('signed_date'))
            agreement.effective_from = effective_from
            agreement.effective_to = _parse_date(request.form.get('effective_to'))
            agreement.auto_renew = request.form.get('auto_renew') == 'on'
            agreement.renewal_notice_days = int(
                request.form.get('renewal_notice_days') or 30)
            agreement.scope_description = request.form.get('scope_description') or None
            agreement.payment_terms = request.form.get('payment_terms') or None
            agreement.quality_terms = request.form.get('quality_terms') or None
            agreement.delivery_terms = request.form.get('delivery_terms') or None
            agreement.penalty_pct = penalty
            agreement.dispute_resolution = request.form.get('dispute_resolution') or None
            agreement.seller_representative = request.form.get('seller_representative') or None
            agreement.buyer_representative = request.form.get('buyer_representative') or None
            agreement.notes = request.form.get('notes') or None
            db.session.commit()

            flash(t('Framework agreement updated'), 'success')
            return redirect(url_for('dashboard.view_agreement',
                                    agreement_id=agreement_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error("Error updating agreement: %s", e)
            db.session.rollback()
            flash(t('Error updating framework agreement'), 'error')

    return render_template('agreements/edit.html', agreement=agreement,
                           customers=customers)


@dashboard_bp.route('/order-confirmations/<confirmation_id>/cancel', methods=['POST'])
@login_required
def cancel_order_confirmation(confirmation_id):
    """Void an issued ĐƠN ĐẶT HÀNG.

    Every other document in the system (quotation, contract, handover,
    payment, purchase order) can be cancelled with a reason. This one could
    not, which meant a mis-issued order confirmation was permanent — the worst
    combination for a non-technical user, since issuing it is a single click.

    Cancelling also rolls back the lifecycle flags it set, but only if no
    later step has happened: once a handover is confirmed the order has moved
    on, and silently un-signing it would misrepresent history.
    """
    from app.models.models import OrderConfirmation
    from app.services.agreement_service import AgreementService

    company_id = get_current_company_id()
    confirmation = OrderConfirmation.query.get(confirmation_id)
    if not confirmation or str(confirmation.company_id) != str(company_id):
        flash(t('Order confirmation not found or access denied'), 'error')
        return redirect(url_for('dashboard.list_orders'))

    order_id = confirmation.order_id
    reason = (request.form.get('reason') or '').strip()
    if not reason:
        flash(t('Please give a reason for cancelling'), 'error')
        return redirect(url_for('dashboard.view_order', order_id=order_id))

    try:
        AgreementService.cancel(confirmation, reason)

        lifecycle = LifecycleStatusRepository().get_for_order(order_id)
        if lifecycle and not lifecycle.handover_confirmed and not lifecycle.advance_paid:
            lifecycle.contract_signed = False
            lifecycle.contract_created = False
            db.session.add(lifecycle)
            db.session.commit()
            flash(t('Order confirmation cancelled. The order is back to the agreement step.'),
                  'success')
        else:
            flash(t('Order confirmation cancelled. Later steps already happened, so the order status was left as it is.'),
                  'warning')
    except ValueError as e:
        flash(str(e), 'error')
    except Exception as e:
        logger.error("Error cancelling order confirmation: %s", e)
        db.session.rollback()
        flash(t('Error cancelling order confirmation'), 'error')

    return redirect(url_for('dashboard.view_order', order_id=order_id))


# ===== PRODUCTION PLANNING (Feature 2) =====

def _owned_plan(plan_id, company_id):
    """The plan, if this user may act on it.

    Company alone was not enough: issuing materials deducts from the ORDER's
    store, so a user at one branch could take fabric off another branch's
    shelves — and nothing in the record would say who did.
    """
    from app.models.models import ProductionPlan
    from app.services.services import user_may_access_store
    plan = ProductionPlan.query.get(plan_id)
    if not plan or str(plan.company_id) != str(company_id):
        return None
    if plan.order is not None and not user_may_access_store(
            plan.order.store_id, company_id):
        return None
    return plan


@dashboard_bp.route('/production')
@login_required
def list_production_plans():
    """What the workshop is building, and what is running late.

    A plan used to be reachable only through its own order, so answering "what
    is in production this week" meant opening orders one at a time. Production
    was the only working area of the product with no way in from the menu.
    """
    from app.models.models import ProductionPlan as _Plan
    from app.models.models import Order as _Order

    company_id = get_current_company_id()
    page = request.args.get('page', 1, type=int)
    status = (request.args.get('status') or '').strip()
    per_page = current_app.config.get('ITEMS_PER_PAGE', 20)

    query = _Plan.query.filter(_Plan.company_id == company_id).join(
        _Order, _Order.id == _Plan.order_id)
    if not is_company_admin():
        query = query.filter(_Order.store_id.in_(get_accessible_store_ids(company_id)))

    if status == 'delayed':
        query = query.filter(_Plan.is_delayed == True)
    elif status == 'processing':
        # What is on the floor right now: approved and being worked, not
        # finished and not yet started.
        query = query.filter(_Plan.status.in_((_Plan.STATUS_APPROVED,
                                               _Plan.STATUS_PROCESSING)))
    elif status:
        query = query.filter(_Plan.status == status)

    # Late first. A list ordered only by date buries the rows that need a
    # decision today under the ones that do not.
    query = query.options(joinedload(_Plan.order)).order_by(
        _Plan.is_delayed.desc(), _Plan.created_at.desc())

    pagination = db.paginate(query, page=page, per_page=per_page,
                             error_out=False)
    return render_template('production/list.html', plans=pagination.items,
                           pagination=pagination, selected_status=status)


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
    # What this job has consumed so far, and how that compares with what it
    # sold for. Only meaningful once a plan exists.
    margin = ProductionPlanService().order_margin(plan) if plan else None
    cost = ProductionPlanService().material_cost(plan) if plan else None
    # What the store actually holds, so a shortage is visible while the manager
    # is still reading the plan rather than only when Cấp phát refuses.
    stock = ProductionPlanService().stock_levels(plan) if plan else {}

    lock_message, _unlock_action = (
        plan_lock_reason(plan.status) if plan else (None, None))
    # Offered only when there is something to choose between — the same rule
    # as the receiving screen. One warehouse means an empty question.
    from app.services.warehouses import must_choose, warehouses_of
    company_id = get_current_company_id()
    from app.services.printing import documents_for
    return render_template('production/plan.html', order=order, plan=plan,
                           lock_message=lock_message,
                           materials=materials, units=units,
                           warehouses=(warehouses_of(company_id)
                                       if must_choose(company_id) else []),
                           documents=documents_for(plan),
                           margin=margin, cost=cost, stock=stock)


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
        # A zero-quantity line looks like a plan but issues nothing, which
        # misleads staff into thinking the material was accounted for.
        if not material_id or qty <= 0:
            raise ValueError(t('Vui lòng chọn vật tư và nhập số lượng lớn hơn 0'))
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


@dashboard_bp.route('/production-plan/<plan_id>/materials/<line_id>/warehouse',
                    methods=['POST'])
@login_required
def set_plan_material_warehouse(plan_id, line_id):
    """Say which warehouse one material line is drawn from.

    Its own route rather than a field on the add-material form: the choice is
    made while looking at the line, often after the plan exists, and folding it
    into creation would mean deleting and re-adding a line to change it.
    """
    from app.models.models import ProductionMaterialLine, Warehouse

    company_id = get_current_company_id()
    plan = _owned_plan(plan_id, company_id)
    if not plan:
        flash(t('Không tìm thấy kế hoạch hoặc không có quyền'), 'error')
        return redirect(url_for('dashboard.list_production_plans'))

    line = ProductionMaterialLine.query.filter_by(id=line_id,
                                                  plan_id=plan.id).first()
    if not line:
        flash(t('Không tìm thấy dòng vật tư'), 'error')
        return redirect(url_for('dashboard.view_production_plan',
                                order_id=plan.order_id))

    chosen = (request.form.get('warehouse_id') or '').strip()
    if not chosen:
        # Blank means "back to the plan's production site" — the state every
        # line starts in. Without this the choice would be one-way.
        line.warehouse_id = None
    else:
        warehouse = Warehouse.query.filter_by(id=chosen,
                                              company_id=company_id).first()
        if not warehouse:
            flash(t('Kho không thuộc công ty này'), 'error')
            return redirect(url_for('dashboard.view_production_plan',
                                    order_id=plan.order_id))
        line.warehouse_id = warehouse.id
    db.session.commit()
    flash(t('Đã đổi kho lấy vật tư cho dòng này'), 'success')
    return redirect(url_for('dashboard.view_production_plan',
                            order_id=plan.order_id))


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
        # The screen decides whether a partial handover is wanted; the service
        # never assumes it. Without this the feature had no way in at all —
        # the third time in this programme that finished work sat unreachable.
        partial = bool(request.form.get('allow_partial'))
        shortages = ProductionPlanService().issue_materials(
            plan, allow_partial=partial)
        if shortages and partial:
            detail = '; '.join(
                '{name} ({code}): {missing}{unit}'.format(
                    name=item['name'] or item['material_code'],
                    code=item['material_code'],
                    missing=f"{item['missing']:g}",
                    unit=f" {item['unit']}" if item['unit'] else '')
                for item in shortages[:5])
            if len(shortages) > 5:
                detail += t(' … và %(n)d vật tư khác') % {
                    'n': len(shortages) - 5}
            # Says BOTH halves: what went out, and what is still missing. A
            # success message alone would leave the foreman to find the gap.
            flash(t('Đã cấp phát phần có sẵn. Vẫn còn thiếu: %(detail)s')
                  % {'detail': detail}, 'warning')
        elif shortages:
            # Name what is short and by how much. Interpolating the value
            # into the key would build a different key on every call, so the
            # sentence stays constant and the data is passed in.
            detail = '; '.join(
                '{name} ({code}): {missing}{unit}'.format(
                    name=item['name'] or item['material_code'],
                    code=item['material_code'],
                    missing=f"{item['missing']:g}",
                    unit=f" {item['unit']}" if item['unit'] else '')
                for item in shortages[:5])
            if len(shortages) > 5:
                detail += t(' … và %(n)d vật tư khác') % {
                    'n': len(shortages) - 5}
            flash(t('Không đủ tồn kho — chưa trừ kho. Còn thiếu: %(detail)s')
                  % {'detail': detail}, 'error')
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
    if not item or str(item.plan_id) != str(plan.id):
        # Previously this fell through with no message at all: the user pressed
        # the button and nothing happened, which reads as a broken screen.
        flash(t('Không tìm thấy hạng mục trong kế hoạch này'), 'error')
    else:
        try:
            written = ProductionPlanService().save_as_norm(item)
            if written:
                flash(t('Đã lưu định mức để tái sử dụng'), 'success')
            else:
                # Claiming a save that did not happen is worse than saying
                # there was nothing to save.
                flash(t('Hạng mục này chưa khai vật tư nên chưa có định mức để lưu'),
                      'warning')
        except Exception as e:
            logger.error(f'save_plan_norm error: {e}')
            db.session.rollback(); flash(t('Lỗi khi lưu định mức'), 'error')
    return redirect(url_for('dashboard.view_production_plan', order_id=plan.order_id))




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
    status = request.args.get('status') or None
    search = request.args.get('search') or None
    page = request.args.get('page', 1, type=int)
    pagination = ProcurementService().list_pos(
        company_id, status=status, search=search, page=page)
    return render_template('procurement/po_list.html',
                           pos=pagination.items, pagination=pagination,
                           status=status or '', search=search or '')


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


# There is deliberately NO route creating purchase orders straight from the
# suggestion list. Such a route existed, reachable from no screen, and it made
# POs with no requisition behind them and nobody's approval — while the
# supported path refuses exactly that ("Chỉ tạo PO từ PR đã được duyệt"). An
# action nothing offers is not safe for being hidden: the permission and the
# URL are enough. Suggestions lead to a requisition, and the requisition, once
# approved, leads to the orders.
#
# `ProcurementService.create_pos_from_suggestions` stays: it is a building
# block, and the tests use it to set a scene.


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
    # Only offered when there is something to choose between. One warehouse
    # means an empty question, and a field with a single option is worse than
    # no field: it asks the user to confirm a fact they cannot change.
    from app.services.warehouses import must_choose, warehouses_of
    # What has already been printed and sent to this supplier. The PO print
    # used to keep nothing at all, so this list was empty by construction.
    from app.services.printing import documents_for
    return render_template(
        'procurement/po_view.html', po=po,
        warehouses=warehouses_of(company_id) if must_choose(company_id) else [],
        documents=documents_for(po),
        **_po_lists(company_id))


@dashboard_bp.route('/purchase-orders/<po_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_purchase_order(po_id):
    company_id = get_current_company_id()
    po = _owned_po(po_id, company_id)
    if not po:
        flash(t('Không tìm thấy đơn mua hoặc không có quyền truy cập'), 'error')
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
        flash(t('Không tìm thấy đơn mua hoặc không có quyền truy cập'), 'error')
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
        flash(t('Không tìm thấy đơn mua hoặc không có quyền truy cập'), 'error')
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
            notes=request.form.get('notes'),
            warehouse_id=(request.form.get('warehouse_id') or None))
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
    company = Company.query.get(company_id)

    # TEMPLATE FIRST. A company that has uploaded (or generated) a
    # purchase-order template prints from it, like every other document in
    # this product — editable, versioned, and reproducible.
    try:
        bio, _document = DocumentService().generate_purchase_order_document(
            po, company)
        if bio is not None:
            return send_file(
                bio, as_attachment=True,
                download_name=f'{po.po_number}.docx',
                mimetype='application/vnd.openxmlformats-officedocument'
                         '.wordprocessingml.document')
    except Exception as exc:
        # A broken or mis-edited template must not stop a purchase order
        # reaching a supplier. Fall through to the built-in layout and say so
        # in the log, rather than handing the buyer an error page.
        logger.warning('Purchase-order template failed for %s, using the '
                       'built-in layout: %s', po.po_number, exc)

    # No template yet — the built-in layout, unchanged. This is the migration
    # path, not a second mechanism to keep: `Tạo mẫu mặc định` on the template
    # screen turns this very layout into an editable template, after which the
    # branch above is what runs.
    from app.utils.procurement_doc import build_purchase_order_docx
    bio = build_purchase_order_docx(po, company)

    # Recorded, not just streamed. This used to hand the file to the browser
    # and keep nothing: no file, no Document row, so the PO screen could show
    # no printing history and nobody could answer which version the supplier
    # was sent. Recording failures must not stop the print — the person is
    # standing there waiting for the file.
    try:
        DocumentService().record_prebuilt_document(
            company_id=company_id, source=po, document_type='purchase_order',
            content=bio.getvalue(), filename=f'{po.po_number}.docx',
            folder_hint=getattr(po.supplier, 'supplier_code', None))
    except Exception as exc:
        logger.warning('Could not record the printed PO %s: %s',
                       po.po_number, exc)
    bio.seek(0)

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
    status = request.args.get('status') or None
    search = request.args.get('search') or None
    page = request.args.get('page', 1, type=int)
    pagination = RequisitionService().list_prs(
        company_id, status=status, search=search, page=page)
    return render_template('procurement/pr_list.html',
                           prs=pagination.items, pagination=pagination,
                           status=status or '', search=search or '')


@dashboard_bp.route('/requisitions/create', methods=['GET', 'POST'])
@login_required
def create_requisition():
    company_id = get_current_company_id()
    from app.services.requisition_service import RequisitionService
    from app.utils.extension_fields import collect_extension_values, apply_extension_values
    svc = RequisitionService()
    if request.method == 'POST':
        # "Fill from auto suggestions" used to be a LINK inside the form, so
        # clicking it navigated away and discarded the title, the branch, the
        # date, the notes and every hand-typed line — silently, because a link
        # is not a submit and the browser has nothing to warn about. It posts
        # now, and the suggestions are MERGED into what is already there,
        # which is what the label always said.
        if request.form.get('action') == 'fill_suggestions':
            typed = parse_material_lines(request.form, with_price=False)
            already = {str(line.get('material_id')) for line in typed
                       if line.get('material_id')}
            merged = list(typed)
            for suggestion in svc.suggest_lines(company_id):
                # A material somebody typed by hand keeps THEIR quantity: they
                # looked at the shelf, the suggestion is arithmetic. And it
                # must appear once, or the supplier is asked for it twice.
                if str(suggestion['material_id']) in already:
                    continue
                merged.append({'material_id': str(suggestion['material_id']),
                               'quantity': suggestion['quantity'],
                               'unit': suggestion['unit']})
            return render_template(
                'procurement/pr_form.html', pr=None, existing_lines=merged,
                form=request.form, **_po_lists(company_id))

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
        flash(t('Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập'), 'error')
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
        flash(t('Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập'), 'error')
        return redirect(url_for('dashboard.list_requisitions'))
    return render_template('procurement/pr_view.html', pr=pr)


@dashboard_bp.route('/requisitions/<pr_id>/status/<action>', methods=['POST'])
@login_required
def requisition_status(pr_id, action):
    company_id = get_current_company_id()
    pr = _owned_pr(pr_id, company_id)
    if not pr:
        flash(t('Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập'), 'error')
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
        flash(t('Không tìm thấy đề nghị mua hàng hoặc không có quyền truy cập'), 'error')
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
    page = request.args.get('page', 1, type=int)
    gr_pagination = ProcurementService().list_grs(company_id, page=page)
    grs = gr_pagination.items
    # The template includes _pagination.html, which renders nothing unless
    # `pagination` is in the context — so without this the nav silently never
    # appeared and receipt 21 onwards could not be reached from the screen.
    return render_template('procurement/gr_list.html', grs=grs,
                           pagination=gr_pagination, page=page)


@dashboard_bp.route('/goods-receipts/<gr_id>', methods=['GET'])
@login_required
def view_goods_receipt(gr_id):
    company_id = get_current_company_id()
    from app.services.procurement_service import ProcurementService
    gr = ProcurementService().get_gr(company_id, gr_id)
    if not gr:
        flash(t('Không tìm thấy phiếu nhập kho hoặc không có quyền truy cập'), 'error')
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
    # Template first, same as the purchase order.
    try:
        bio, _doc = DocumentService().generate_production_plan_document(
            plan, order, customer, company)
        if bio is not None:
            return send_file(
                bio, as_attachment=True,
                download_name=f'LenhSanXuat_{plan.plan_number}.docx',
                mimetype='application/vnd.openxmlformats-officedocument'
                         '.wordprocessingml.document')
    except Exception as exc:
        logger.warning('Production-plan template failed for %s, using the '
                       'built-in layout: %s', plan.plan_number, exc)

    bio = build_production_plan_docx(plan, order, customer, company)

    try:
        DocumentService().record_prebuilt_document(
            company_id=company_id, source=plan,
            document_type='production_plan', content=bio.getvalue(),
            filename=f'LenhSanXuat_{plan.plan_number}.docx',
            order_id=order.id,
            folder_hint=getattr(customer, 'customer_code', None))
    except Exception as exc:
        logger.warning('Could not record the printed production plan %s: %s',
                       plan.plan_number, exc)
    bio.seek(0)

    return send_file(bio, as_attachment=True,
                     download_name=f'LenhSanXuat_{plan.plan_number}.docx',
                     mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
