"""
Database models for SaaS application
"""
from datetime import datetime
from app.config.database import db
from app.models.types import GUID
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import declared_attr
from sqlalchemy import event, select
import uuid


# Per-user feature permissions (RBAC). Admins (company/store) always have all;
# regular users only get the features an admin grants them.
FEATURE_KEYS = ('customers', 'orders', 'inventory', 'purchasing', 'reports')
FEATURE_LABELS = {
    'customers':  'Khách hàng',
    'orders':     'Đơn hàng & chứng từ',
    'inventory':  'Kho & Vật tư',
    'purchasing': 'Mua hàng (PR/PO/GR)',
    'reports':    'Báo cáo',
}


# Number of admin-configurable extension columns per document table.
EXTENSION_SLOTS = 10
EXTENSION_FIELD_KEYS = [f'extend{i:02d}' for i in range(1, EXTENSION_SLOTS + 1)]


class ExtendFieldsMixin:
    """Reserved admin-configurable flexfield columns ``extend01``..``extend10``.

    Stored as text; per company an admin enables a slot, gives it a label, data
    type and required-flag via ``ExtensionFieldConfig``. Used by master-data and
    procurement tables that already carry their own ``company_id``.
    """
    extend01 = db.Column(db.Text)
    extend02 = db.Column(db.Text)
    extend03 = db.Column(db.Text)
    extend04 = db.Column(db.Text)
    extend05 = db.Column(db.Text)
    extend06 = db.Column(db.Text)
    extend07 = db.Column(db.Text)
    extend08 = db.Column(db.Text)
    extend09 = db.Column(db.Text)
    extend10 = db.Column(db.Text)


class DocExtensionMixin:
    """Adds a per-tenant ``company_id`` plus ``extend01``..``extend10`` columns to
    document tables (quotations, contracts, handover_records, payment_reports).

    - ``company_id`` (NR3/D8): direct tenant column so document numbers are unique
      per company at the DB level and tenant queries need no join. It is
      auto-populated from the document's order by a ``before_insert`` listener.
    - ``extend01``..``extend10`` (D9): reserved "flexfield" columns. Stored as text;
      whether each is shown, its label, data type and whether it is required are
      configured per company via ``ExtensionFieldConfig`` and validated/cast at the
      application layer.
    """

    @declared_attr
    def company_id(cls):
        return db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)

    extend01 = db.Column(db.Text)
    extend02 = db.Column(db.Text)
    extend03 = db.Column(db.Text)
    extend04 = db.Column(db.Text)
    extend05 = db.Column(db.Text)
    extend06 = db.Column(db.Text)
    extend07 = db.Column(db.Text)
    extend08 = db.Column(db.Text)
    extend09 = db.Column(db.Text)
    extend10 = db.Column(db.Text)


class Company(db.Model):
    """Company/Tenant model"""
    __tablename__ = 'companies'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)          # Registered/head office address
    production_address = db.Column(db.Text)  # Manufacturing / production address
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
    tax_code = db.Column(db.String(50))   # Mã số thuế
    representative_name = db.Column(db.String(255))  # Legal representative (Giám Đốc)
    representative_title = db.Column(db.String(100), default='Giám Đốc')
    business_registration_number = db.Column(db.String(100))  # Số ĐKKD / GPKD (cần cho hộ KD)
    website = db.Column(db.String(255))
    logo_path = db.Column(db.String(500))
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00)  # Default VAT % (e.g. 8.00)
    # Bank accounts: [{"bank_name": ..., "account_number": ..., "account_holder": ...}]
    bank_accounts = db.Column(db.JSON, default=list)
    timezone = db.Column(db.String(50), default='UTC')
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stores = db.relationship('Store', backref='company', lazy=True, cascade='all, delete-orphan')
    users = db.relationship('User', backref='company', lazy=True, cascade='all, delete-orphan')
    customers = db.relationship('Customer', backref='company', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='company', lazy=True, cascade='all, delete-orphan')
    templates = db.relationship('DocumentTemplate', backref='company', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='company', lazy=True, cascade='all, delete-orphan')
    material_units = db.relationship('MaterialUnit', backref='company', lazy=True, cascade='all, delete-orphan')
    material_categories = db.relationship('MaterialCategory', backref='company', lazy=True, cascade='all, delete-orphan')
    suppliers = db.relationship('Supplier', backref='company', lazy=True, cascade='all, delete-orphan')
    materials = db.relationship('Material', backref='company', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Company {self.company_code}>'


class Store(ExtendFieldsMixin, db.Model):
    """Store model - each company can have multiple stores"""
    __tablename__ = 'stores'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    manager_name = db.Column(db.String(255))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on store_code per company
    __table_args__ = (db.UniqueConstraint('company_id', 'store_code', name='uq_company_store_code'),)
    
    # Relationships
    users = db.relationship('User', backref='store', lazy=True, foreign_keys='User.store_id')
    customers = db.relationship('Customer', backref='store', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='store', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Store {self.store_code}>'


class User(db.Model):
    """User model.

    Roles (hierarchy):
      - company_admin : Full control over company, stores, users. No store assignment.
      - store_admin   : Manages one store and its data. Cannot edit company-level settings.
      - user          : End-user assigned to one store. Creates/edits operational docs.
    """
    __tablename__ = 'users'

    # Role constants
    ROLE_COMPANY_ADMIN = 'company_admin'
    ROLE_STORE_ADMIN   = 'store_admin'
    ROLE_USER          = 'user'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    # NULL for company_admin; required for store_admin and user
    store_id = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=True, index=True)
    username = db.Column(db.String(100), nullable=False, index=True)
    # Email is the login identifier — globally unique across all companies.
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    position = db.Column(db.String(100))  # Job title / chức vụ
    role = db.Column(db.String(50), default='user')  # company_admin | store_admin | user
    # Per-user feature permissions (JSON list of feature keys). Only meaningful for
    # role='user'; admins have full access. See FEATURE_KEYS.
    allowed_features = db.Column(db.JSON, default=list)
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Unique username per company
    __table_args__ = (db.UniqueConstraint('company_id', 'username', name='uq_company_username'),)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)

    @property
    def is_company_admin(self):
        return self.role == self.ROLE_COMPANY_ADMIN

    @property
    def is_store_admin(self):
        return self.role == self.ROLE_STORE_ADMIN

    @property
    def is_admin(self):
        """True for both company_admin and store_admin"""
        return self.role in (self.ROLE_COMPANY_ADMIN, self.ROLE_STORE_ADMIN)

    def can_feature(self, feature):
        """RBAC check: admins have every feature; regular users only granted ones."""
        if self.is_admin:
            return True
        return feature in (self.allowed_features or [])

    @property
    def role_label(self):
        labels = {
            'company_admin': 'Quản Trị Công Ty',
            'store_admin':   'Quản Trị Cửa Hàng',
            'user':          'Nhân Viên',
        }
        return labels.get(self.role, self.role)

    def __repr__(self):
        return f'<User {self.username}>'


class Customer(ExtendFieldsMixin, db.Model):
    """Customer model"""
    __tablename__ = 'customers'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=False, index=True)
    customer_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    tax_code = db.Column(db.String(50))           # Mã số thuế
    representative_name = db.Column(db.String(255))   # Customer representative name
    representative_title = db.Column(db.String(100))  # Customer representative title
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on customer_code per store
    __table_args__ = (
        db.UniqueConstraint('store_id', 'customer_code', name='uq_store_customer_code'),
        db.Index('ix_customers_company_active', 'company_id', 'is_active'),
        db.Index('ix_customers_company_created', 'company_id', 'created_at'),
    )
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Customer {self.customer_code}>'


class LifecycleStatus(db.Model):
    """Order lifecycle status tracking"""
    __tablename__ = 'lifecycle_statuses'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    # Lifecycle steps
    quotation_created = db.Column(db.Boolean, default=False)
    quotation_created_at = db.Column(db.DateTime)
    
    quotation_approved = db.Column(db.Boolean, default=False)
    quotation_approved_at = db.Column(db.DateTime)
    
    contract_created = db.Column(db.Boolean, default=False)
    contract_created_at = db.Column(db.DateTime)
    
    contract_signed = db.Column(db.Boolean, default=False)
    contract_signed_at = db.Column(db.DateTime)
    
    handover_confirmed = db.Column(db.Boolean, default=False)
    handover_confirmed_at = db.Column(db.DateTime)
    
    advance_paid = db.Column(db.Boolean, default=False)
    advance_paid_at = db.Column(db.DateTime)

    advance_skipped = db.Column(db.Boolean, default=False)
    advance_skipped_at = db.Column(db.DateTime)
    
    fully_paid = db.Column(db.Boolean, default=False)
    fully_paid_at = db.Column(db.DateTime)
    
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<LifecycleStatus {self.order_id}>'


class Order(ExtendFieldsMixin, db.Model):
    """Order model - represents customer lifecycle"""
    __tablename__ = 'orders'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=False, index=True)
    customer_id = db.Column(GUID(), db.ForeignKey('customers.id'), nullable=False, index=True)
    
    order_code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    
    # Financial tracking
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    advance_amount = db.Column(db.Numeric(15, 2), default=0)
    final_amount = db.Column(db.Numeric(15, 2), default=0)
    
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on order_code per store
    __table_args__ = (
        db.UniqueConstraint('store_id', 'order_code', name='uq_store_order_code'),
        db.Index('ix_orders_company_created', 'company_id', 'created_at'),
        db.Index('ix_orders_company_active', 'company_id', 'is_active'),
    )
    
    # Relationships (order.store is provided by Store.orders backref below)
    lifecycle = db.relationship('LifecycleStatus', backref='order', uselist=False, lazy=True, cascade='all, delete-orphan', foreign_keys='LifecycleStatus.order_id')
    quotations = db.relationship('Quotation', backref='order', lazy=True, cascade='all, delete-orphan')
    contracts = db.relationship('Contract', backref='order', lazy=True, cascade='all, delete-orphan')
    handover_records = db.relationship('HandoverRecord', backref='order', lazy=True, cascade='all, delete-orphan')
    payment_reports = db.relationship('PaymentReport', backref='order', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='order', order_by='Document.generated_at.desc()', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Order {self.order_code}>'
    
    def can_cancel(self):
        """Check if order can be canceled - cannot cancel if already canceled or completed"""
        if not self.is_active or self.is_canceled:
            return False
        
        # Cannot cancel completed orders
        if self.lifecycle and self.lifecycle.completed:
            return False
        
        return True


class Quotation(DocExtensionMixin, db.Model):
    """Quotation model"""
    __tablename__ = 'quotations'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    quotation_number = db.Column(db.String(50), nullable=False)
    quotation_date = db.Column(db.Date, nullable=False)
    validity_days = db.Column(db.Integer, default=30)
    city = db.Column(db.String(100))          # City for date header (e.g. TP. Hồ Chí Minh)
    
    # Items - stored as JSON
    items = db.Column(db.JSON, default=list)  # [{name, unit, quantity, unit_price, total}]
    
    subtotal = db.Column(db.Numeric(15, 2), default=0)   # Before VAT
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00) # VAT percentage
    vat_amount = db.Column(db.Numeric(15, 2), default=0) # VAT amount
    shipping_fee = db.Column(db.Numeric(15, 2), default=0)   # Phí vận chuyển (không VAT)
    another_fee  = db.Column(db.Numeric(15, 2), default=0)   # Chi phí khác (không VAT)
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    amount_in_words = db.Column(db.String(500))  # Total amount in words
    payment_terms = db.Column(db.Text)        # Payment terms / Hình thức thanh toán
    notes = db.Column(db.Text)
    
    # Status tracking
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)  # False when canceled
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Document numbers are unique per company (NR3/D8).
    __table_args__ = (db.UniqueConstraint('company_id', 'quotation_number',
                                          name='uq_company_quotation_number'),)

    # Relationships
    documents = db.relationship('Document', backref='quotation', order_by='Document.generated_at.desc()', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Quotation {self.quotation_number}>'
    
    def can_edit(self):
        return not self.is_approved
    
    def can_approve(self):
        return self.is_active and not self.is_canceled and not self.is_approved
    
    def can_cancel(self):
        return self.is_active and not self.is_canceled and not self.is_approved


class Contract(DocExtensionMixin, db.Model):
    """Contract model"""
    __tablename__ = 'contracts'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    quotation_id = db.Column(GUID(), db.ForeignKey('quotations.id'))
    
    contract_number = db.Column(db.String(50), nullable=False)
    contract_date = db.Column(db.Date, nullable=False)
    city = db.Column(db.String(100))          # Signing location city
    
    # Items - can differ from quotation as products can be added
    items = db.Column(db.JSON, default=list)  # [{name, unit, quantity, unit_price, total}]
    
    subtotal = db.Column(db.Numeric(15, 2), default=0)       # Before VAT
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00)     # VAT percentage
    vat_amount = db.Column(db.Numeric(15, 2), default=0)     # VAT amount
    shipping_fee = db.Column(db.Numeric(15, 2), default=0)   # Phí vận chuyển (không VAT)
    another_fee  = db.Column(db.Numeric(15, 2), default=0)   # Chi phí khác (không VAT)
    contract_value = db.Column(db.Numeric(15, 2), nullable=False)  # Total incl. VAT
    advance_percentage = db.Column(db.Numeric(5, 2), default=30.00)  # % tạm ứng
    advance_amount = db.Column(db.Numeric(15, 2), default=0)  # Advance amount
    
    amount_in_words = db.Column(db.Text)               # Số tiền bằng chữ
    contract_start_date = db.Column(db.Date)            # Ngày bắt đầu thực hiện
    contract_days_complete = db.Column(db.Integer, default=30)  # Số ngày cam kết hoàn thiện
    selected_bank_index = db.Column(db.Integer, default=0)  # Index trong company.bank_accounts
    num_date_notice_cancel = db.Column(db.Integer, default=7)  # Số ngày báo trước khi hủy

    warranty_months = db.Column(db.Integer)  # Thời gian bảo hành (tháng)
    delivery_terms = db.Column(db.Text)      # Điều khoản giao hàng
    terms_and_conditions = db.Column(db.Text)
    is_signed = db.Column(db.Boolean, default=False, index=True)
    signed_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, index=True)  # Only one active contract per order
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Document numbers unique per company (NR3/D8).
    __table_args__ = (db.UniqueConstraint('company_id', 'contract_number',
                                          name='uq_company_contract_number'),)

    # Relationships
    quotation = db.relationship('Quotation', backref='contracts', foreign_keys='Contract.quotation_id', lazy=True)
    documents = db.relationship('Document', backref='contract', order_by='Document.generated_at.desc()', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Contract {self.contract_number}>'
    
    def can_edit(self):
        """Contract can be edited if not signed and not canceled"""
        return not self.is_signed and not self.is_canceled
    
    def can_sign(self):
        """Check if contract can be signed"""
        return not self.is_signed and not self.is_canceled
    
    def can_cancel(self):
        """Check if contract can be canceled"""
        return self.is_active and not self.is_canceled and not self.is_signed


class HandoverRecord(DocExtensionMixin, db.Model):
    """Handover Record (Biên Bản Bàn Giao) - confirms customer acceptance of product/service"""
    __tablename__ = 'handover_records'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    report_number = db.Column(db.String(50), nullable=False)
    report_date = db.Column(db.Date, nullable=False)
    handover_date = db.Column(db.Date, nullable=False)
    handover_location = db.Column(db.Text)    # Address where handover takes place
    start_time = db.Column(db.String(10))     # e.g. "08:00"
    end_time = db.Column(db.String(10))       # e.g. "10:00"
    copies_count = db.Column(db.Integer, default=2)  # Number of document copies
    
    # Items acceptance - tracks which items the customer accepts
    # [{name, unit, quantity, unit_price, total, delivered_qty, accepted_qty, accepted, rejection_reason}]
    items = db.Column(db.JSON, default=list)
    
    subtotal = db.Column(db.Numeric(15, 2), default=0)    # Before VAT
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00)  # VAT percentage
    vat_amount = db.Column(db.Numeric(15, 2), default=0)  # VAT amount
    shipping_fee = db.Column(db.Numeric(15, 2), default=0)   # Phí vận chuyển (không VAT)
    another_fee  = db.Column(db.Numeric(15, 2), default=0)   # Chi phí khác (không VAT)
    total_amount = db.Column(db.Numeric(15, 2), default=0)  # Total incl. VAT
    
    customer_representative = db.Column(db.String(200))         # Customer representative name
    customer_representative_title = db.Column(db.String(100))   # Customer rep title
    company_representative = db.Column(db.String(200))          # Company representative name
    company_representative_title = db.Column(db.String(100))    # Company rep title
    product_condition = db.Column(db.Text)  # Description of product condition at handover
    customer_signature_confirmed = db.Column(db.Boolean, default=False)  # Customer confirmed receipt
    
    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=False, index=True)
    confirmed_date = db.Column(db.DateTime)
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Document numbers unique per company (NR3/D8).
    __table_args__ = (db.UniqueConstraint('company_id', 'report_number',
                                          name='uq_company_handover_report_number'),)

    # Relationships
    documents = db.relationship('Document', backref='handover_record', order_by='Document.generated_at.desc()', lazy=True)
    
    def __repr__(self):
        return f'<HandoverRecord {self.report_number}>'
    
    def can_edit(self):
        """Handover record can be edited if not confirmed and not canceled"""
        return not self.is_confirmed and not self.is_canceled
    
    def can_confirm(self):
        """Check if handover can be confirmed"""
        return not self.is_confirmed and not self.is_canceled
    
    def can_cancel(self):
        """Check if handover can be canceled"""
        return not self.is_confirmed and not self.is_canceled


class PaymentReport(DocExtensionMixin, db.Model):
    """Payment report model"""
    __tablename__ = 'payment_reports'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    report_number = db.Column(db.String(50), nullable=False)
    payment_type = db.Column(db.String(50), nullable=False)  # 'advance' or 'final'
    report_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    
    # Work items covered by this payment
    items = db.Column(db.JSON, default=list)  # [{name, unit, quantity, unit_price, total}]
    subtotal = db.Column(db.Numeric(15, 2), default=0)    # Before VAT
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00)  # VAT percentage
    vat_amount = db.Column(db.Numeric(15, 2), default=0)  # VAT amount
    shipping_fee = db.Column(db.Numeric(15, 2), default=0)   # Phí vận chuyển (không VAT)
    another_fee  = db.Column(db.Numeric(15, 2), default=0)   # Chi phí khác (không VAT)
    
    amount = db.Column(db.Numeric(15, 2), nullable=False) # Total amount incl. VAT & fees
    advance_percentage = db.Column(db.Numeric(5, 2))      # % tạm ứng (e.g. 30.00)
    advance_amount = db.Column(db.Numeric(15, 2), default=0)   # Amount already paid
    remaining_amount = db.Column(db.Numeric(15, 2), default=0) # Remaining to pay
    amount_in_words = db.Column(db.String(500))   # Remaining amount in Vietnamese words
    work_completed_summary = db.Column(db.Text)   # Summary of completed work
    quotation_reference_date = db.Column(db.Date) # Date of the referenced quotation
    
    payment_method = db.Column(db.String(100))    # cash, check, bank transfer, etc.
    transaction_reference = db.Column(db.String(100))
    # Bank accounts for this payment: [{bank_name, account_number, account_holder}]
    bank_account_info = db.Column(db.JSON, default=list)

    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=False, index=True)
    confirmed_date = db.Column(db.DateTime)
    # Proof of received payment (image/PDF) uploaded at confirmation time — item 5
    proof_path = db.Column(db.String(300))
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Document numbers unique per company (NR3/D8).
    __table_args__ = (db.UniqueConstraint('company_id', 'report_number',
                                          name='uq_company_payment_report_number'),)

    # Relationships
    documents = db.relationship('Document', backref='payment_report', order_by='Document.generated_at.desc()', lazy=True)
    
    def __repr__(self):
        return f'<PaymentReport {self.report_number}>'
    
    def can_edit(self):
        """Payment can be edited if not confirmed and not canceled"""
        return not self.is_confirmed and not self.is_canceled
    
    def can_confirm(self):
        """Check if payment can be confirmed"""
        return not self.is_confirmed and not self.is_canceled
    
    def can_cancel(self):
        """Check if payment can be canceled"""
        return not self.is_confirmed and not self.is_canceled


class DocumentTemplate(db.Model):
    """Document template model - stores RTF templates"""
    __tablename__ = 'document_templates'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    
    name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # quotation, contract, delivery, payment
    description = db.Column(db.Text)
    
    template_file = db.Column(db.String(255), nullable=False)  # Path to template file
    template_content = db.Column(db.Text)  # RTF content
    
    variables = db.Column(db.JSON, default=dict)  # {var_name: description}
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='template', lazy=True)
    
    def __repr__(self):
        return f'<DocumentTemplate {self.name}>'


class Document(db.Model):
    """Generated document model"""
    __tablename__ = 'documents'
    
    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, index=True)
    template_id = db.Column(GUID(), db.ForeignKey('document_templates.id'))
    quotation_id = db.Column(GUID(), db.ForeignKey('quotations.id'))
    contract_id = db.Column(GUID(), db.ForeignKey('contracts.id'))
    handover_record_id = db.Column(GUID(), db.ForeignKey('handover_records.id'))
    payment_report_id = db.Column(GUID(), db.ForeignKey('payment_reports.id'))
    
    document_name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # quotation, contract, delivery, payment
    document_format = db.Column(db.String(10), nullable=False)  # pdf, docx
    
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    
    variables_used = db.Column(db.JSON, default=dict)  # {"var_name": value}

    # Document lifecycle.
    #
    # Every regeneration writes a NEW file (the name carries a timestamp), so
    # one contract can own several files. Without a marker the user has to
    # read timestamps to work out which one to send the customer — a real
    # question for staff who are not confident with computers.
    #
    # This is also the seam a signing step will hook into later: `signed`
    # belongs on this same axis, and a signed document must never be silently
    # superseded by a regeneration.
    STATUS_CURRENT = 'current'
    STATUS_SUPERSEDED = 'superseded'
    STATUS_SIGNED = 'signed'

    status = db.Column(db.String(16), default=STATUS_CURRENT, nullable=False,
                       index=True)
    superseded_at = db.Column(db.DateTime)

    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @property
    def is_current(self):
        return self.status in (self.STATUS_CURRENT, self.STATUS_SIGNED)

    @property
    def is_signed(self):
        return self.status == self.STATUS_SIGNED

    def __repr__(self):
        return f'<Document {self.document_name} ({self.status})>'


class MaterialUnit(db.Model):
    """Unit of measure for materials — scoped per company."""
    __tablename__ = 'material_units'

    id         = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    name         = db.Column(db.String(50), nullable=False)    # e.g. "m²", "kg", "cái", "cuộn"
    abbreviation = db.Column(db.String(20))                    # Optional short form displayed on forms
    description  = db.Column(db.String(255))
    is_active    = db.Column(db.Boolean, default=True, index=True)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'name', name='uq_company_unit_name'),)

    # Relationships
    materials = db.relationship('Material', backref='unit', lazy=True, foreign_keys='Material.unit_id')

    def __repr__(self):
        return f'<MaterialUnit {self.name}>'


class MaterialCategory(db.Model):
    """Category / group for materials — scoped per company."""
    __tablename__ = 'material_categories'

    id         = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    name        = db.Column(db.String(100), nullable=False)   # e.g. "Vải bọc", "Da", "Mút xốp", "Gỗ khung"
    description = db.Column(db.Text)
    sort_order  = db.Column(db.Integer, default=0)
    is_active   = db.Column(db.Boolean, default=True, index=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'name', name='uq_company_category_name'),)

    # Relationships
    materials = db.relationship('Material', backref='category', lazy=True, foreign_keys='Material.category_id')

    def __repr__(self):
        return f'<MaterialCategory {self.name}>'


class Supplier(ExtendFieldsMixin, db.Model):
    """Supplier / Nhà cung cấp — scoped per company."""
    __tablename__ = 'suppliers'

    id         = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)

    supplier_code   = db.Column(db.String(50), nullable=False)   # e.g. NCC-001
    name            = db.Column(db.String(255), nullable=False, index=True)
    contact_person  = db.Column(db.String(255))   # Tên người liên hệ
    phone           = db.Column(db.String(20))
    email           = db.Column(db.String(255))
    address         = db.Column(db.Text)
    tax_code        = db.Column(db.String(50))    # Mã số thuế
    payment_terms   = db.Column(db.String(20), default='COD')  # COD / NET15 / NET30 / NET60
    lead_time_days  = db.Column(db.Integer, default=0)   # Thời gian giao hàng mặc định (ngày)
    rating          = db.Column(db.Integer, default=0)   # 0-5 star rating
    notes           = db.Column(db.Text)
    is_active       = db.Column(db.Boolean, default=True, index=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'supplier_code', name='uq_company_supplier_code'),)

    # Relationships
    materials = db.relationship('Material', backref='supplier', lazy=True, foreign_keys='Material.supplier_id')

    def __repr__(self):
        return f'<Supplier {self.supplier_code}>'


class Material(ExtendFieldsMixin, db.Model):
    """Raw material / nguyên vật liệu — company-level catalog with optional per-store stock."""
    __tablename__ = 'materials'

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id  = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    category_id = db.Column(GUID(), db.ForeignKey('material_categories.id'), nullable=True, index=True)
    unit_id     = db.Column(GUID(), db.ForeignKey('material_units.id'), nullable=True, index=True)
    supplier_id = db.Column(GUID(), db.ForeignKey('suppliers.id'), nullable=True, index=True)

    material_code = db.Column(db.String(50), nullable=False)
    name          = db.Column(db.String(255), nullable=False, index=True)
    description   = db.Column(db.Text)
    color         = db.Column(db.String(100))
    unit_price    = db.Column(db.Numeric(15, 2), default=0)   # Reference purchase price
    supplier_sku  = db.Column(db.String(100))                 # Mã SKU bên nhà cung cấp
    min_stock_level = db.Column(db.Numeric(10, 2), default=0) # Alert threshold
    image_path    = db.Column(db.String(500))                 # Relative path under uploads/
    notes         = db.Column(db.Text)

    # ── Technical Specifications (structured) ──────────────────────────
    # Kích thước & Trọng lượng
    spec_width_cm          = db.Column(db.Numeric(10, 2))   # Khổ rộng (cm)
    spec_thickness_mm      = db.Column(db.Numeric(10, 2))   # Độ dày (mm)
    spec_roll_length_m     = db.Column(db.Numeric(10, 2))   # Chiều dài cuộn (m)
    spec_weight_per_unit   = db.Column(db.Numeric(10, 3))   # Trọng lượng / đơn vị
    spec_weight_unit       = db.Column(db.String(20))       # g/m², g/m, kg/m³, kg/cái
    # Thành phần & Ngoại quan
    spec_composition       = db.Column(db.String(255))      # Thành phần vật liệu
    spec_pattern           = db.Column(db.String(50))       # Trơn / Kẻ sọc / Hoa văn / Vân gỗ / Khác
    spec_finish            = db.Column(db.String(50))       # Matt / Bóng / Nhám / Nhung / Wax
    # Chất lượng & Hiệu năng
    spec_durability_cycles = db.Column(db.Integer)          # Martindale cycles (vải/da)
    spec_density_kg_m3     = db.Column(db.Numeric(8, 2))    # Mật độ mút (kg/m³)
    spec_hardness          = db.Column(db.String(50))       # Độ cứng: ILD 28, Grade A …
    spec_fire_resistance   = db.Column(db.String(50))       # Không / BS5852 / TB117 / EN-1021
    spec_water_resistance  = db.Column(db.String(30))       # Không / Kháng nước / Chống thấm
    spec_uv_resistance     = db.Column(db.String(30))       # Không / Trung bình / Cao
    # Xuất xứ & Tuân thủ
    spec_country_of_origin = db.Column(db.String(100))      # Xuất xứ
    spec_certifications    = db.Column(db.Text)             # Chứng nhận (OEKO-TEX, ISO ...)

    is_active  = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Moving-average cost, updated on every goods receipt.
    #
    # Without it the system could see what a bespoke job SOLD for but not what
    # it COST: material issues are already tracked per production plan
    # (ProductionMaterialLine.quantity_issued), they just had no price. In a
    # bespoke business there is no catalogue price to compare against, so this
    # is the only way to tell whether a job made money.
    #
    # Deliberately moving-average rather than FIFO or standard cost: this is a
    # workshop, not a valuation system.
    avg_cost = db.Column(db.Numeric(15, 2), default=0)

    __table_args__ = (db.UniqueConstraint('company_id', 'material_code', name='uq_company_material_code'),)

    # Relationships
    stock_entries = db.relationship('MaterialStock', backref='material', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Material {self.material_code}>'

    @property
    def total_stock(self):
        """Sum of current_quantity across all stock entries."""
        return sum(s.current_quantity or 0 for s in self.stock_entries)

    @property
    def is_low_stock(self):
        """True when total stock falls below min_stock_level."""
        if self.min_stock_level and self.min_stock_level > 0:
            return self.total_stock < self.min_stock_level
        return False


class MaterialStock(db.Model):
    """Per-location stock entry for a material.
    
    store_id = NULL  → company-level / main warehouse
    store_id = <id>  → specific store stock
    """
    __tablename__ = 'material_stock'

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    material_id = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    company_id  = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id    = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=True, index=True)

    current_quantity = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    notes            = db.Column(db.Text)
    last_updated     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('material_id', 'store_id', name='uq_material_store_stock'),
        # The constraint above does NOT cover company-level rows: store_id is
        # NULLable and SQL treats two NULLs as distinct, so a material could
        # hold several "main warehouse" rows. ProcurementService.receive()
        # finds the row with .first(), so duplicates make a goods receipt
        # increment one row while a reader sees another. A partial unique
        # index closes the NULL case (supported by PostgreSQL and SQLite).
        db.Index('uq_material_stock_company_level', 'material_id',
                 unique=True,
                 postgresql_where=db.text('store_id IS NULL'),
                 sqlite_where=db.text('store_id IS NULL')),
    )

    def __repr__(self):
        return f'<MaterialStock material={self.material_id} store={self.store_id}>'


class MasterAdmin(db.Model):
    """System-level master administrator — not tied to any company."""
    __tablename__ = 'master_admins'

    id            = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    username      = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email         = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name     = db.Column(db.String(255), nullable=False)
    is_active     = db.Column(db.Boolean, default=True, index=True)
    last_login    = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<MasterAdmin {self.username}>'


class ExtensionFieldConfig(db.Model):
    """Per-company configuration for a document type's extend01..extend10 columns.

    One row per (company, entity_type, field_key). Controls whether the slot is
    shown on forms, its display label, its data type and whether it is required.
    See AUDIT D9.
    """
    __tablename__ = 'extension_field_configs'

    ENTITY_TYPES = ('quotation', 'contract', 'handover', 'payment',
                    'customer', 'supplier', 'material', 'store', 'order',
                    'purchase_requisition', 'purchase_order', 'goods_receipt')
    DATA_TYPES = ('text', 'number', 'date', 'boolean')

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id  = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=False)   # quotation|contract|handover|payment
    field_key   = db.Column(db.String(20), nullable=False)   # extend01..extend10
    is_enabled  = db.Column(db.Boolean, default=False, nullable=False)
    label       = db.Column(db.String(100))
    data_type   = db.Column(db.String(20), default='text', nullable=False)  # text|number|date|boolean
    is_required = db.Column(db.Boolean, default=False, nullable=False)
    sort_order  = db.Column(db.Integer, default=0)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'entity_type', 'field_key',
                            name='uq_extfield_company_entity_key'),
    )

    def __repr__(self):
        return f'<ExtensionFieldConfig {self.entity_type}.{self.field_key}>'


class ProductionPlan(db.Model):
    """Kế hoạch sản xuất — 1 plan / order, tạo tự động sau khi hợp đồng ký (Feature 2)."""
    __tablename__ = 'production_plans'

    STATUS_DRAFT = 'draft'
    STATUS_APPROVED = 'approved'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_VALIDATING = 'validating'
    STATUS_VALIDATED = 'validated'
    STATUS_REJECTED = 'rejected'
    STATUS_FINISHED = 'finished'
    STATUS_CANCELED = 'canceled'
    STATUS_IN_PROGRESS = 'processing'  # backward-compat alias

    # action -> (allowed-from statuses, target status)
    TRANSITIONS = {
        'approve':  (('draft',), 'approved'),
        'start':    (('approved', 'rejected'), 'processing'),
        'complete': (('processing',), 'completed'),
        'submit':   (('completed',), 'validating'),
        'validate': (('validating',), 'validated'),
        'reject':   (('validating',), 'rejected'),
        'finish':   (('validated',), 'finished'),
        'cancel':   (('draft', 'approved', 'processing', 'completed',
                      'validating', 'validated', 'rejected'), 'canceled'),
    }

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id  = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    order_id    = db.Column(GUID(), db.ForeignKey('orders.id'), nullable=False, unique=True, index=True)
    contract_id = db.Column(GUID(), db.ForeignKey('contracts.id'), nullable=True)
    plan_number = db.Column(db.String(50), nullable=False)
    status      = db.Column(db.String(20), default='draft', nullable=False, index=True)
    is_delayed   = db.Column(db.Boolean, default=False, nullable=False)
    delay_reason = db.Column(db.Text)
    notes       = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'plan_number', name='uq_company_plan_number'),)

    order    = db.relationship('Order', backref=db.backref('production_plan', uselist=False), lazy=True)
    contract = db.relationship('Contract', lazy=True)
    items = db.relationship('ProductionPlanItem', backref='plan', lazy=True, cascade='all, delete-orphan')
    material_lines = db.relationship('ProductionMaterialLine', backref='plan', lazy=True, cascade='all, delete-orphan')

    def can_edit(self):
        """BOM (danh sách vật tư/hạng mục) chỉ sửa được khi còn NHÁP.
        'Duyệt kế hoạch' = chốt lệnh: sau khi duyệt, danh mục vật tư khóa lại,
        chỉ còn cấp phát/nghiệm thu (muốn sửa lại thì 'Từ chối (làm lại)')."""
        return self.status == self.STATUS_DRAFT

    def can_issue(self):
        """Cấp phát vật tư (trừ kho) sau khi đã chốt, trong lúc sản xuất."""
        return self.status in (self.STATUS_APPROVED, self.STATUS_PROCESSING,
                               self.STATUS_REJECTED)

    def can(self, action):
        tr = self.TRANSITIONS.get(action)
        return bool(tr and self.status in tr[0])

    def allowed_actions(self):
        return [a for a, (froms, _) in self.TRANSITIONS.items() if self.status in froms]

    def __repr__(self):
        return f'<ProductionPlan {self.plan_number}>'


class ProductionPlanItem(db.Model):
    """Một hạng mục cần sản xuất (copy từ item hợp đồng)."""
    __tablename__ = 'production_plan_items'

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    plan_id     = db.Column(GUID(), db.ForeignKey('production_plans.id'), nullable=False, index=True)
    source_name = db.Column(db.String(255), nullable=False)
    quantity    = db.Column(db.Numeric(15, 2), default=0)
    unit        = db.Column(db.String(50))
    notes       = db.Column(db.Text)

    material_lines = db.relationship('ProductionMaterialLine', backref='plan_item', lazy=True)

    def __repr__(self):
        return f'<ProductionPlanItem {self.source_name}>'


class ProductionMaterialLine(db.Model):
    """Vật tư cần cho kế hoạch (theo item hoặc overall khi plan_item_id NULL)."""
    __tablename__ = 'production_material_lines'

    id           = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    plan_id      = db.Column(GUID(), db.ForeignKey('production_plans.id'), nullable=False, index=True)
    plan_item_id = db.Column(GUID(), db.ForeignKey('production_plan_items.id'), nullable=True, index=True)
    material_id  = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    quantity_required = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    quantity_issued   = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit         = db.Column(db.String(50))
    notes        = db.Column(db.Text)

    material = db.relationship('Material', lazy=True)

    def __repr__(self):
        return f'<ProductionMaterialLine material={self.material_id}>'


class MaterialNorm(db.Model):
    """Định mức vật tư tái sử dụng theo tên sản phẩm (per company) — Hybrid."""
    __tablename__ = 'material_norms'

    id                = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id        = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    product_key       = db.Column(db.String(255), nullable=False, index=True)  # lower/strip tên SP
    material_id       = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    quantity_per_unit = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit              = db.Column(db.String(50))
    created_at        = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'product_key', 'material_id',
                                          name='uq_norm_company_product_material'),)

    material = db.relationship('Material', lazy=True)

    def __repr__(self):
        return f'<MaterialNorm {self.product_key}>'


class PurchaseRequisition(ExtendFieldsMixin, db.Model):
    """Đề nghị mua hàng (PR) — nhu cầu mua nội bộ, tạo tay hoặc từ đề xuất tự động.

    Không phụ thuộc mức tồn kho (có thể đề nghị mua để dự phòng). Sau khi duyệt →
    chuyển thành một hoặc nhiều Đơn mua hàng (PO) gộp theo nhà cung cấp.
    """
    __tablename__ = 'purchase_requisitions'

    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'   # đã gửi duyệt
    STATUS_APPROVED = 'approved'     # đã duyệt — sẵn sàng tạo PO
    STATUS_CONVERTED = 'converted'   # đã tạo PO
    STATUS_CANCELED = 'canceled'

    TRANSITIONS = {
        'submit':  (('draft',), 'submitted'),
        'approve': (('submitted',), 'approved'),
        'reject':  (('submitted',), 'draft'),
        'cancel':  (('draft', 'submitted', 'approved'), 'canceled'),
        'reopen':  (('submitted', 'approved'), 'draft'),
    }

    id           = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id   = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id     = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=True, index=True)  # kho/CH cần
    pr_number    = db.Column(db.String(50), nullable=False)
    status       = db.Column(db.String(20), default='draft', nullable=False, index=True)
    request_date = db.Column(db.Date)
    expected_date = db.Column(db.Date)
    title        = db.Column(db.String(255))
    notes        = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'pr_number', name='uq_company_pr_number'),)

    store = db.relationship('Store', lazy=True)
    lines = db.relationship('PurchaseRequisitionLine', backref='pr', lazy=True, cascade='all, delete-orphan')
    purchase_orders = db.relationship('PurchaseOrder', backref='requisition', lazy=True,
                                      foreign_keys='PurchaseOrder.pr_id')

    def can_edit(self):
        return self.status == self.STATUS_DRAFT

    def can_convert(self):
        """Tạo PO khi đã duyệt (chưa hoặc đã convert vẫn cho tạo tiếp phần còn lại)."""
        return self.status in (self.STATUS_APPROVED, self.STATUS_CONVERTED)

    def can(self, action):
        tr = self.TRANSITIONS.get(action)
        return bool(tr and self.status in tr[0])

    def allowed_actions(self):
        return [a for a, (froms, _) in self.TRANSITIONS.items() if self.status in froms]

    def __repr__(self):
        return f'<PurchaseRequisition {self.pr_number}>'


class PurchaseRequisitionLine(db.Model):
    """Dòng vật tư trên đề nghị mua hàng."""
    __tablename__ = 'purchase_requisition_lines'

    id          = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    pr_id       = db.Column(GUID(), db.ForeignKey('purchase_requisitions.id'), nullable=False, index=True)
    material_id = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    quantity    = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit        = db.Column(db.String(50))
    notes       = db.Column(db.Text)

    material = db.relationship('Material', lazy=True)

    def __repr__(self):
        return f'<PurchaseRequisitionLine pr={self.pr_id} material={self.material_id}>'


class PurchaseOrder(ExtendFieldsMixin, db.Model):
    """Đơn mua hàng (PO) gửi nhà cung cấp — khép vòng cung ứng (Feature 3)."""
    __tablename__ = 'purchase_orders'

    STATUS_DRAFT = 'draft'          # nháp — soạn/sửa được
    STATUS_ORDERED = 'ordered'      # đã gửi NCC
    STATUS_PARTIAL = 'partial'      # đã nhập một phần
    STATUS_RECEIVED = 'received'    # đã nhập đủ
    STATUS_CANCELED = 'canceled'

    # action -> (allowed-from, target)
    TRANSITIONS = {
        'submit': (('draft',), 'ordered'),                      # gửi NCC
        'cancel': (('draft', 'ordered', 'partial'), 'canceled'),
        'reopen': (('ordered',), 'draft'),                      # thu hồi khi chưa nhập
    }

    id           = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id   = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id     = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=True, index=True)  # kho sẽ nhập về
    supplier_id  = db.Column(GUID(), db.ForeignKey('suppliers.id'), nullable=True, index=True)
    pr_id        = db.Column(GUID(), db.ForeignKey('purchase_requisitions.id'), nullable=True, index=True)  # nguồn PR (nếu có)
    po_number    = db.Column(db.String(50), nullable=False)
    status       = db.Column(db.String(20), default='draft', nullable=False, index=True)
    order_date   = db.Column(db.Date)
    expected_date = db.Column(db.Date)
    notes        = db.Column(db.Text)
    subtotal     = db.Column(db.Numeric(15, 2), default=0)
    vat_rate     = db.Column(db.Numeric(5, 2), default=0)
    vat_amount   = db.Column(db.Numeric(15, 2), default=0)
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'po_number', name='uq_company_po_number'),)

    supplier = db.relationship('Supplier', lazy=True)
    store    = db.relationship('Store', lazy=True)
    lines    = db.relationship('PurchaseOrderLine', backref='po', lazy=True, cascade='all, delete-orphan')
    receipts = db.relationship('GoodsReceipt', backref='po', lazy=True, cascade='all, delete-orphan')

    def can_edit(self):
        return self.status == self.STATUS_DRAFT

    def can_receive(self):
        """Nhập kho được khi đã gửi NCC và chưa nhập đủ."""
        return self.status in (self.STATUS_ORDERED, self.STATUS_PARTIAL)

    def can(self, action):
        tr = self.TRANSITIONS.get(action)
        return bool(tr and self.status in tr[0])

    def allowed_actions(self):
        return [a for a, (froms, _) in self.TRANSITIONS.items() if self.status in froms]

    def recompute_totals(self):
        from decimal import Decimal
        sub = sum((Decimal(str(l.line_total or 0)) for l in self.lines), Decimal('0'))
        self.subtotal = sub
        rate = Decimal(str(self.vat_rate or 0))
        self.vat_amount = (sub * rate / Decimal('100')).quantize(Decimal('1'))
        self.total_amount = sub + self.vat_amount

    def sync_receipt_status(self):
        """After a goods receipt, move to partial/received based on line fulfilment.
        Never overrides draft/canceled."""
        if self.status in (self.STATUS_DRAFT, self.STATUS_CANCELED):
            return
        lines = self.lines
        if lines and all((l.quantity_received or 0) >= (l.quantity_ordered or 0) for l in lines):
            self.status = self.STATUS_RECEIVED
        elif any((l.quantity_received or 0) > 0 for l in lines):
            self.status = self.STATUS_PARTIAL

    def __repr__(self):
        return f'<PurchaseOrder {self.po_number}>'


class PurchaseOrderLine(db.Model):
    """Dòng vật tư trên đơn mua."""
    __tablename__ = 'purchase_order_lines'

    id            = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    po_id         = db.Column(GUID(), db.ForeignKey('purchase_orders.id'), nullable=False, index=True)
    material_id   = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    quantity_ordered  = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    quantity_received = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    # Third leg of the 3-way match (PO / GR / invoice). Cumulative across all
    # supplier invoices billing this line.
    quantity_invoiced = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit          = db.Column(db.String(50))
    unit_price    = db.Column(db.Numeric(15, 2), default=0)
    line_total    = db.Column(db.Numeric(15, 2), default=0)
    notes         = db.Column(db.Text)

    material = db.relationship('Material', lazy=True)

    @property
    def outstanding(self):
        from decimal import Decimal
        return Decimal(str(self.quantity_ordered or 0)) - Decimal(str(self.quantity_received or 0))

    def __repr__(self):
        return f'<PurchaseOrderLine po={self.po_id} material={self.material_id}>'


class GoodsReceipt(ExtendFieldsMixin, db.Model):
    """Phiếu nhập kho (GR) — nhận hàng theo đơn mua, tăng tồn kho (Feature 3)."""
    __tablename__ = 'goods_receipts'

    id           = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id   = db.Column(GUID(), db.ForeignKey('companies.id'), nullable=False, index=True)
    po_id        = db.Column(GUID(), db.ForeignKey('purchase_orders.id'), nullable=True, index=True)
    store_id     = db.Column(GUID(), db.ForeignKey('stores.id'), nullable=True, index=True)  # kho nhập vào
    gr_number    = db.Column(db.String(50), nullable=False)
    receipt_date = db.Column(db.Date)
    notes        = db.Column(db.Text)
    is_posted    = db.Column(db.Boolean, default=False, nullable=False, index=True)  # đã ghi tăng tồn
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('company_id', 'gr_number', name='uq_company_gr_number'),)

    store = db.relationship('Store', lazy=True)
    lines = db.relationship('GoodsReceiptLine', backref='gr', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<GoodsReceipt {self.gr_number}>'


class GoodsReceiptLine(db.Model):
    """Dòng nhập kho — số lượng thực nhận cho một vật tư."""
    __tablename__ = 'goods_receipt_lines'

    id           = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    gr_id        = db.Column(GUID(), db.ForeignKey('goods_receipts.id'), nullable=False, index=True)
    po_line_id   = db.Column(GUID(), db.ForeignKey('purchase_order_lines.id'), nullable=True, index=True)
    material_id  = db.Column(GUID(), db.ForeignKey('materials.id'), nullable=False, index=True)
    quantity_received = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit         = db.Column(db.String(50))
    notes        = db.Column(db.Text)

    material = db.relationship('Material', lazy=True)
    po_line  = db.relationship('PurchaseOrderLine', lazy=True)

    def __repr__(self):
        return f'<GoodsReceiptLine gr={self.gr_id} material={self.material_id}>'


class WorkflowRule(db.Model):
    """One prerequisite of one workflow action, for one company.

    This table is the single place the order graph lives. Before it, the
    sequencing rules were spread across three layers — boolean flags on
    ``LifecycleStatus``, per-document ``can_*`` guards that could only see
    their own document, and hardcoded ``if/raise`` checks inside individual
    service methods — so no one place described the legal order of events.

    A rule reads: "before ACTION, PREREQUISITE must hold", qualified by MODE:

    * ``required``  — hard block; the action is refused.
    * ``waivable``  — may be bypassed, but only with a recorded reason
                      (this generalises the old ``advance_skipped`` flag).
    * ``optional``  — advisory only; surfaced as a warning, never blocks.
                      (Used for quotation-before-contract, which AUDIT D6
                      deliberately decided NOT to enforce.)

    Rules are seeded per company from ``WorkflowService.DEFAULT_RULES``, which
    reproduces the behaviour that used to be hardcoded, so installing this
    table changes nothing until an administrator edits it.
    """

    __tablename__ = 'workflow_rules'

    MODE_REQUIRED = 'required'
    MODE_WAIVABLE = 'waivable'
    MODE_OPTIONAL = 'optional'
    MODES = (MODE_REQUIRED, MODE_WAIVABLE, MODE_OPTIONAL)

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)

    # e.g. 'handover.create', 'payment.advance', 'contract.sign'
    action = db.Column(db.String(64), nullable=False)
    # a LifecycleStatus boolean column name, e.g. 'contract_signed'
    prerequisite = db.Column(db.String(64), nullable=False)
    mode = db.Column(db.String(16), nullable=False, default=MODE_REQUIRED)

    # Shown to the user when the rule blocks an action. Optional: a readable
    # default is derived from the prerequisite when this is empty.
    message = db.Column(db.String(255))

    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'action', 'prerequisite',
                            name='uq_workflow_rule'),
        db.Index('ix_workflow_rules_company_action', 'company_id', 'action'),
    )

    def __repr__(self):
        return f'<WorkflowRule {self.action} needs {self.prerequisite} ({self.mode})>'


class WorkflowWaiver(db.Model):
    """An audited bypass of a ``waivable`` workflow rule.

    Replaces the untracked ``LifecycleStatus.advance_skipped`` boolean, which
    recorded that a step was skipped but not by whom or why.
    """

    __tablename__ = 'workflow_waivers'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'),
                         nullable=False, index=True)

    action = db.Column(db.String(64), nullable=False)
    prerequisite = db.Column(db.String(64), nullable=False)
    reason = db.Column(db.Text, nullable=False)

    waived_by_user_id = db.Column(GUID(), db.ForeignKey('users.id'))
    waived_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_workflow_waivers_order_action', 'order_id', 'action'),
    )

    def __repr__(self):
        return f'<WorkflowWaiver {self.action}/{self.prerequisite} order={self.order_id}>'


class NormalizationRule(db.Model):
    """Per-company input-standardisation rule for ONE field.

    The business problem: data is typed by people who are not strict about
    capitalisation, spacing or punctuation, so generated documents look
    inconsistent and the stored data is hard to match on.

    One row = one field of one entity, plus the ORDERED list of primitives to
    run over it (see ``app/utils/text_normalize.py``). Keeping the transform
    list as data means a company can change its house style without a deploy,
    and means we do not grow a hardcoded rule per field.

    ``mode``:
      * ``auto``    — applied silently on save.
      * ``confirm`` — not applied; the suggestion is surfaced so a human can
                      accept it. Used for identity-sensitive values where a
                      wrong guess would misrepresent someone on a document.

    Fields matching ``PROTECTED_FIELD_HINTS`` (tax codes, bank accounts,
    document numbers...) are refused at the service layer whatever is
    configured here — normalising a legal identifier corrupts it.
    """

    __tablename__ = 'normalization_rules'

    MODE_AUTO = 'auto'
    MODE_CONFIRM = 'confirm'
    MODES = (MODE_AUTO, MODE_CONFIRM)

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)

    # 'customer', 'supplier', 'material', 'order', 'quotation', ...
    entity_type = db.Column(db.String(64), nullable=False)
    field_name = db.Column(db.String(64), nullable=False)

    # Ordered list of primitive names, e.g. ["nfc","trim","company_name_case"]
    primitives = db.Column(db.JSON, nullable=False, default=list)

    mode = db.Column(db.String(16), nullable=False, default=MODE_AUTO)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'entity_type', 'field_name',
                            name='uq_normalization_rule'),
        db.Index('ix_normalization_rules_company_entity',
                 'company_id', 'entity_type'),
    )

    def __repr__(self):
        return f'<NormalizationRule {self.entity_type}.{self.field_name}>'


class NormalizationSuggestion(db.Model):
    """A pending ``confirm``-mode change awaiting a human decision.

    Keeps the original alongside the proposal so nothing is lost and the
    change can be reviewed rather than silently applied.
    """

    __tablename__ = 'normalization_suggestions'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)

    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(GUID(), nullable=False)
    field_name = db.Column(db.String(64), nullable=False)

    original_value = db.Column(db.Text)
    suggested_value = db.Column(db.Text)

    status = db.Column(db.String(16), default='pending', nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('ix_norm_suggestions_entity', 'entity_type', 'entity_id'),
    )

    def __repr__(self):
        return f'<NormalizationSuggestion {self.entity_type}.{self.field_name}>'


class MasterAgreement(db.Model):
    """HỢP ĐỒNG NGUYÊN TẮC — a framework agreement with a customer.

    Vietnamese law does not name this as a distinct contract type; it is a
    framework built on ordinary freedom of contract (BLDS 2015 Đ.385, 398,
    401-403). It binds the *principles of cooperation* — scope, price list,
    payment/quality/delivery terms, penalties, dispute resolution — and
    deliberately omits what identifies a single transaction: quantity,
    specification, delivery date and final price.

    Because of that omission a HĐNT alone CANNOT substantiate a hóa đơn GTGT:
    NĐ 123/2020 Đ.9 ties invoice timing to a specific delivery and requires an
    invoice per delivery for repeated shipments. Each order therefore still
    needs its own document — an ``OrderConfirmation`` (ĐƠN ĐẶT HÀNG), which
    under BLDS 2015 Đ.386+393 is itself a complete contract for that
    transaction once accepted.

    Most Vietnamese SME framework agreements commit to no volume at all, so
    ``commitment_type`` defaults to NONE and the agreement is simply a terms +
    pricing container.
    """

    __tablename__ = 'master_agreements'

    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_SUSPENDED = 'suspended'
    STATUS_EXPIRED = 'expired'
    STATUS_TERMINATED = 'terminated'

    COMMITMENT_NONE = 'none'
    COMMITMENT_VALUE = 'value'
    COMMITMENT_QUANTITY = 'quantity'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)
    customer_id = db.Column(GUID(), db.ForeignKey('customers.id'),
                            nullable=False, index=True)

    agreement_number = db.Column(db.String(50), nullable=False)
    signed_date = db.Column(db.Date)
    effective_from = db.Column(db.Date, nullable=False)
    # NULL = vô thời hạn (open-ended until terminated) — common in practice.
    effective_to = db.Column(db.Date)

    auto_renew = db.Column(db.Boolean, default=False)
    renewal_notice_days = db.Column(db.Integer, default=30)

    status = db.Column(db.String(16), nullable=False, default=STATUS_DRAFT,
                       index=True)

    commitment_type = db.Column(db.String(16), default=COMMITMENT_NONE)
    target_value = db.Column(db.Numeric(15, 2))
    target_quantity = db.Column(db.Numeric(15, 2))

    scope_description = db.Column(db.Text)        # phạm vi hợp tác
    payment_terms = db.Column(db.Text)            # điều khoản thanh toán
    quality_terms = db.Column(db.Text)            # chất lượng
    delivery_terms = db.Column(db.Text)           # giao nhận

    # Phạt vi phạm. LTM 2005 Đ.301 caps the penalty at 8% OF THE VALUE OF THE
    # BREACHED PORTION of the obligation — not 8% of the whole contract value.
    penalty_pct = db.Column(db.Numeric(5, 2), default=8.00)
    penalty_basis_note = db.Column(
        db.String(255),
        default='Tính trên giá trị phần nghĩa vụ hợp đồng bị vi phạm')

    dispute_resolution = db.Column(db.Text)       # giải quyết tranh chấp
    seller_representative = db.Column(db.String(255))
    seller_representative_title = db.Column(db.String(100))
    buyer_representative = db.Column(db.String(255))
    buyer_representative_title = db.Column(db.String(100))

    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    price_lines = db.relationship('MasterAgreementPriceLine',
                                  backref='agreement', lazy=True,
                                  cascade='all, delete-orphan')
    confirmations = db.relationship('OrderConfirmation', backref='agreement',
                                    lazy=True)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'agreement_number',
                            name='uq_company_agreement_number'),
        db.Index('ix_master_agreements_customer_status',
                 'customer_id', 'status'),
    )

    def is_effective_on(self, on_date):
        """Is the agreement usable for a NEW release order on ``on_date``?

        An already-issued confirmation is never invalidated by the agreement
        later expiring — it was a completed offer+acceptance in its own right.
        Only the creation of new ones is gated.
        """
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.effective_from and on_date < self.effective_from:
            return False
        if self.effective_to and on_date > self.effective_to:
            return False
        return True

    def can_edit(self):
        return self.status in (self.STATUS_DRAFT, self.STATUS_ACTIVE)

    def __repr__(self):
        return f'<MasterAgreement {self.agreement_number}>'


class MasterAgreementPriceLine(db.Model):
    """An agreed price (or discount) for one product under a HĐNT.

    Line-level validity rather than whole-document versioning: revising a
    price closes the old line's ``effective_to`` and inserts a new one, so a
    past ĐƠN ĐẶT HÀNG can still be explained by the price that applied on its
    date. This matches Vietnamese practice, where a price revision is done by
    phụ lục rather than by reissuing the agreement under a new number.

    ``product_key`` is a normalized product name, consistent with
    ``MaterialNorm`` — this app has no product-master entity yet (see F11).
    """

    __tablename__ = 'master_agreement_price_lines'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    agreement_id = db.Column(GUID(), db.ForeignKey('master_agreements.id'),
                             nullable=False, index=True)

    product_key = db.Column(db.String(255), nullable=False)
    product_name = db.Column(db.String(255))
    unit = db.Column(db.String(50))

    agreed_unit_price = db.Column(db.Numeric(15, 2))
    discount_pct = db.Column(db.Numeric(5, 2))

    effective_from = db.Column(db.Date)
    effective_to = db.Column(db.Date)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MasterAgreementPriceLine {self.product_key}>'


class OrderConfirmation(DocExtensionMixin, db.Model):
    """ĐƠN ĐẶT HÀNG — the per-order document issued under a HĐNT.

    Occupies the same slot in the lifecycle that ``Contract`` does: both
    evidence offer + acceptance for one transaction, and either satisfies the
    precondition for a handover record. Which one an order gets is decided by
    the workflow configuration, not hardcoded.

    The agreement number/date are SNAPSHOTTED here rather than only joined, so
    the printed document keeps citing what it cited at the time even if the
    agreement is later amended.
    """

    __tablename__ = 'order_confirmations'

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELED = 'canceled'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(GUID(), db.ForeignKey('orders.id'),
                         nullable=False, index=True)
    master_agreement_id = db.Column(GUID(),
                                    db.ForeignKey('master_agreements.id'),
                                    nullable=False, index=True)
    quotation_id = db.Column(GUID(), db.ForeignKey('quotations.id'))

    confirmation_number = db.Column(db.String(50), nullable=False)
    confirmation_date = db.Column(db.Date, nullable=False)

    # Snapshot of the cited agreement ("căn cứ HĐNT số ... ngày ...").
    cited_agreement_number = db.Column(db.String(50))
    cited_agreement_date = db.Column(db.Date)

    items = db.Column(db.JSON, default=list)
    subtotal = db.Column(db.Numeric(15, 2), default=0)
    vat_rate = db.Column(db.Numeric(5, 2), default=8.00)
    vat_amount = db.Column(db.Numeric(15, 2), default=0)
    shipping_fee = db.Column(db.Numeric(15, 2), default=0)
    another_fee = db.Column(db.Numeric(15, 2), default=0)
    total_amount = db.Column(db.Numeric(15, 2), default=0)
    amount_in_words = db.Column(db.String(500))

    delivery_date = db.Column(db.Date)
    delivery_address = db.Column(db.Text)
    payment_terms = db.Column(db.Text)
    notes = db.Column(db.Text)

    status = db.Column(db.String(16), nullable=False, default=STATUS_DRAFT)
    is_active = db.Column(db.Boolean, default=True)
    is_canceled = db.Column(db.Boolean, default=False)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'confirmation_number',
                            name='uq_company_confirmation_number'),
    )

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED

    def can_edit(self):
        return self.status == self.STATUS_DRAFT and not self.is_canceled

    def can_confirm(self):
        return self.status == self.STATUS_DRAFT and not self.is_canceled

    def can_cancel(self):
        return not self.is_canceled

    def __repr__(self):
        return f'<OrderConfirmation {self.confirmation_number}>'


class SupplierInvoice(db.Model):
    """Hóa đơn GTGT received from a supplier — the "Invoice" of Procure-to-Pay.

    The procurement chain previously stopped at goods receipt: there was no
    supplier invoice, no payable and no payment, so "P2P" was really
    Procure-to-Receive.

    Fields follow what NĐ 123/2020 requires to be captured for input-VAT
    purposes: ký hiệu (series), số hóa đơn, ngày lập, MST người bán, tiền
    hàng, thuế suất, tiền thuế, tổng thanh toán. The seller's tax code is
    FROZEN here rather than only joined to ``Supplier``, because the supplier
    record can change later while the invoice must keep saying what it said.

    ``match_status`` is informational, never a hard block. SAP blocks an
    out-of-tolerance invoice for payment; for an SME that is hostile, because
    the usual cause is paperwork arriving in a different order rather than
    fraud. We surface the discrepancy and let a human decide.
    """

    __tablename__ = 'supplier_invoices'

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELED = 'canceled'

    MATCH_OK = 'ok'
    MATCH_NO_RECEIPT = 'no_receipt'        # invoiced more than was received
    MATCH_PRICE_VARIANCE = 'price_variance'
    MATCH_OVER_INVOICED = 'over_invoiced'  # invoiced more than was ordered

    # Deliberately hardcoded rather than a configurable tolerance table:
    # one SME does not need SAP's tolerance-key machinery.
    PRICE_TOLERANCE_PCT = 2.0
    QTY_TOLERANCE_PCT = 5.0

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)
    supplier_id = db.Column(GUID(), db.ForeignKey('suppliers.id'),
                            nullable=False, index=True)
    po_id = db.Column(GUID(), db.ForeignKey('purchase_orders.id'),
                      nullable=False, index=True)

    invoice_series = db.Column(db.String(20))       # ký hiệu
    invoice_number = db.Column(db.String(50), nullable=False)  # số hóa đơn
    invoice_date = db.Column(db.Date, nullable=False)          # ngày lập
    seller_tax_code = db.Column(db.String(50))                 # MST người bán

    subtotal = db.Column(db.Numeric(15, 2), default=0)   # tiền hàng
    vat_rate = db.Column(db.Numeric(5, 2), default=0)    # thuế suất
    vat_amount = db.Column(db.Numeric(15, 2), default=0)  # tiền thuế
    total_amount = db.Column(db.Numeric(15, 2), default=0)

    status = db.Column(db.String(16), nullable=False, default=STATUS_DRAFT,
                       index=True)
    match_status = db.Column(db.String(24), default=MATCH_OK)
    match_notes = db.Column(db.Text)

    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    supplier = db.relationship('Supplier', lazy=True)
    po = db.relationship('PurchaseOrder', backref='invoices', lazy=True)
    lines = db.relationship('SupplierInvoiceLine', backref='invoice',
                            lazy=True, cascade='all, delete-orphan')
    allocations = db.relationship('SupplierPaymentAllocation',
                                  backref='invoice', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'supplier_id', 'invoice_series',
                            'invoice_number', name='uq_supplier_invoice_number'),
    )

    def can_edit(self):
        return self.status == self.STATUS_DRAFT

    @property
    def amount_paid(self):
        from decimal import Decimal
        return sum((Decimal(str(a.allocated_amount or 0))
                    for a in self.allocations
                    if a.payment and a.payment.status == SupplierPayment.STATUS_CONFIRMED),
                   Decimal('0'))

    @property
    def amount_outstanding(self):
        from decimal import Decimal
        return Decimal(str(self.total_amount or 0)) - self.amount_paid

    @property
    def is_paid(self):
        return self.amount_outstanding <= 0

    def __repr__(self):
        return f'<SupplierInvoice {self.invoice_series}/{self.invoice_number}>'


class SupplierInvoiceLine(db.Model):
    """One invoiced line, matched back to the PO line it bills."""

    __tablename__ = 'supplier_invoice_lines'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    invoice_id = db.Column(GUID(), db.ForeignKey('supplier_invoices.id'),
                           nullable=False, index=True)
    po_line_id = db.Column(GUID(), db.ForeignKey('purchase_order_lines.id'),
                           nullable=False, index=True)
    material_id = db.Column(GUID(), db.ForeignKey('materials.id'), index=True)

    quantity = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    unit = db.Column(db.String(50))
    unit_price = db.Column(db.Numeric(15, 2), default=0)
    line_total = db.Column(db.Numeric(15, 2), default=0)

    po_line = db.relationship('PurchaseOrderLine', lazy=True)
    material = db.relationship('Material', lazy=True)

    def __repr__(self):
        return f'<SupplierInvoiceLine inv={self.invoice_id}>'


class SupplierPayment(db.Model):
    """Money paid to a supplier.

    ``method`` matters for tax, not just bookkeeping: input-VAT deduction in
    Vietnam depends on non-cash payment evidence. The threshold rules have
    changed recently, so the system RECORDS the method and flags cash payments
    rather than trying to enforce a rule that may move again — the accountant
    decides, we make the fact visible.
    """

    __tablename__ = 'supplier_payments'

    STATUS_DRAFT = 'draft'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELED = 'canceled'

    METHOD_CASH = 'cash'
    METHOD_TRANSFER = 'bank_transfer'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(GUID(), db.ForeignKey('companies.id'),
                           nullable=False, index=True)
    supplier_id = db.Column(GUID(), db.ForeignKey('suppliers.id'),
                            nullable=False, index=True)

    payment_number = db.Column(db.String(50), nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    method = db.Column(db.String(20), default=METHOD_TRANSFER, nullable=False)
    reference_number = db.Column(db.String(100))   # số UNC / bank ref

    status = db.Column(db.String(16), nullable=False, default=STATUS_DRAFT)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    supplier = db.relationship('Supplier', lazy=True)
    allocations = db.relationship('SupplierPaymentAllocation',
                                  backref='payment', lazy=True,
                                  cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('company_id', 'payment_number',
                            name='uq_company_supplier_payment_number'),
    )

    @property
    def allocated_amount(self):
        from decimal import Decimal
        return sum((Decimal(str(a.allocated_amount or 0))
                    for a in self.allocations), Decimal('0'))

    @property
    def unallocated_amount(self):
        from decimal import Decimal
        return Decimal(str(self.amount or 0)) - self.allocated_amount

    @property
    def is_cash(self):
        return self.method == self.METHOD_CASH

    def __repr__(self):
        return f'<SupplierPayment {self.payment_number}>'


class SupplierPaymentAllocation(db.Model):
    """Links a payment to the invoice(s) it settles.

    Necessary, not incidental: one payment can cover several invoices and one
    invoice can be settled in instalments, so "is this invoice paid?" is
    otherwise unanswerable.
    """

    __tablename__ = 'supplier_payment_allocations'

    id = db.Column(GUID(), primary_key=True, default=uuid.uuid4)
    payment_id = db.Column(GUID(), db.ForeignKey('supplier_payments.id'),
                           nullable=False, index=True)
    invoice_id = db.Column(GUID(), db.ForeignKey('supplier_invoices.id'),
                           nullable=False, index=True)
    allocated_amount = db.Column(db.Numeric(15, 2), default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('payment_id', 'invoice_id',
                            name='uq_payment_invoice_allocation'),
    )

    def __repr__(self):
        return f'<SupplierPaymentAllocation {self.allocated_amount}>'


def _populate_doc_company_id(mapper, connection, target):
    """before_insert: set a document's company_id from its order (NR3/D8).

    Runs for every insert path (route or service) so the NOT NULL company_id
    column is always populated without touching each create call site.
    """
    if getattr(target, 'company_id', None) is None and getattr(target, 'order_id', None) is not None:
        row = connection.execute(
            select(Order.company_id).where(Order.id == target.order_id)
        ).first()
        if row is not None:
            target.company_id = row[0]


for _doc_model in (Quotation, Contract, HandoverRecord, PaymentReport, ProductionPlan,
                   OrderConfirmation):
    event.listen(_doc_model, 'before_insert', _populate_doc_company_id)
