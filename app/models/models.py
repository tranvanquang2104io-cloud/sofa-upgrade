"""
Database models for SaaS application
"""
from datetime import datetime
from app.config.database import db
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.security import generate_password_hash, check_password_hash
import uuid


class Company(db.Model):
    """Company/Tenant model"""
    __tablename__ = 'companies'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100))
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
    
    def __repr__(self):
        return f'<Company {self.company_code}>'


class Store(db.Model):
    """Store model - each company can have multiple stores"""
    __tablename__ = 'stores'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
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
    customers = db.relationship('Customer', backref='store', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='store', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Store {self.store_code}>'


class User(db.Model):
    """User model"""
    __tablename__ = 'users'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
    username = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='user')  # admin, manager, user
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Customer(db.Model):
    """Customer model"""
    __tablename__ = 'customers'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id = db.Column(UUID(as_uuid=True), db.ForeignKey('stores.id'), nullable=False, index=True)
    customer_code = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False, index=True)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(255))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    country = db.Column(db.String(100))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint on customer_code per store
    __table_args__ = (db.UniqueConstraint('store_id', 'customer_code', name='uq_store_customer_code'),)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Customer {self.customer_code}>'


class LifecycleStatus(db.Model):
    """Order lifecycle status tracking"""
    __tablename__ = 'lifecycle_statuses'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    
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
    
    fully_paid = db.Column(db.Boolean, default=False)
    fully_paid_at = db.Column(db.DateTime)
    
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<LifecycleStatus {self.order_id}>'


class Order(db.Model):
    """Order model - represents customer lifecycle"""
    __tablename__ = 'orders'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
    store_id = db.Column(UUID(as_uuid=True), db.ForeignKey('stores.id'), nullable=False, index=True)
    customer_id = db.Column(UUID(as_uuid=True), db.ForeignKey('customers.id'), nullable=False, index=True)
    
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
    __table_args__ = (db.UniqueConstraint('store_id', 'order_code', name='uq_store_order_code'),)
    
    # Relationships
    lifecycle = db.relationship('LifecycleStatus', backref='order', uselist=False, lazy=True, cascade='all, delete-orphan', foreign_keys='LifecycleStatus.order_id')
    quotations = db.relationship('Quotation', backref='order', lazy=True, cascade='all, delete-orphan')
    contracts = db.relationship('Contract', backref='order', lazy=True, cascade='all, delete-orphan')
    handover_records = db.relationship('HandoverRecord', backref='order', lazy=True, cascade='all, delete-orphan')
    payment_reports = db.relationship('PaymentReport', backref='order', lazy=True, cascade='all, delete-orphan')
    documents = db.relationship('Document', backref='order', lazy=True, cascade='all, delete-orphan')
    
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


class Quotation(db.Model):
    """Quotation model"""
    __tablename__ = 'quotations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    quotation_number = db.Column(db.String(50), nullable=False, unique=True)
    quotation_date = db.Column(db.Date, nullable=False)
    validity_days = db.Column(db.Integer, default=30)
    
    # Items - stored as JSON
    items = db.Column(db.JSON, default=list)  # [{name, quantity, unit_price, total}]
    
    total_amount = db.Column(db.Numeric(15, 2), nullable=False)
    notes = db.Column(db.Text)
    
    # Status tracking
    is_approved = db.Column(db.Boolean, default=False, index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)  # False when canceled
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='quotation', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Quotation {self.quotation_number}>'
    
    def can_edit(self):
        return not self.is_approved
    
    def can_approve(self):
        return self.is_active and not self.is_canceled and not self.is_approved
    
    def can_cancel(self):
        return self.is_active and not self.is_canceled and not self.is_approved


class Contract(db.Model):
    """Contract model"""
    __tablename__ = 'contracts'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    quotation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('quotations.id'))
    
    contract_number = db.Column(db.String(50), nullable=False, unique=True)
    contract_date = db.Column(db.Date, nullable=False)
    contract_value = db.Column(db.Numeric(15, 2), nullable=False)
    
    # Items - can differ from quotation as products can be added
    items = db.Column(db.JSON, default=list)  # [{name, quantity, unit_price, total}]
    
    terms_and_conditions = db.Column(db.Text)
    is_signed = db.Column(db.Boolean, default=False, index=True)
    signed_date = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True, index=True)  # Only one active contract per order
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    quotation = db.relationship('Quotation', backref='contracts', foreign_keys='Contract.quotation_id', lazy=True)
    documents = db.relationship('Document', backref='contract', lazy=True, cascade='all, delete-orphan')
    
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


class HandoverRecord(db.Model):
    """Handover Record (Biên Bản Bàn Giao) - confirms customer acceptance of product/service"""
    __tablename__ = 'handover_records'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    report_number = db.Column(db.String(50), nullable=False, unique=True)
    report_date = db.Column(db.Date, nullable=False)
    handover_date = db.Column(db.Date, nullable=False)
    
    # Items acceptance - tracks which items the customer accepts
    # [{name, quantity, unit_price, total, delivered_qty, accepted_qty, accepted, rejection_reason}]
    items = db.Column(db.JSON, default=list)
    
    customer_representative = db.Column(db.String(200))  # Customer's representative name
    company_representative = db.Column(db.String(200))  # Company's representative name
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
    
    # Relationships
    documents = db.relationship('Document', backref='handover_record', lazy=True)
    
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


class PaymentReport(db.Model):
    """Payment report model"""
    __tablename__ = 'payment_reports'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    
    report_number = db.Column(db.String(50), nullable=False, unique=True)
    payment_type = db.Column(db.String(50), nullable=False)  # 'advance' or 'final'
    report_date = db.Column(db.Date, nullable=False)
    payment_date = db.Column(db.Date, nullable=False)
    
    amount = db.Column(db.Numeric(15, 2), nullable=False)
    payment_method = db.Column(db.String(100))  # cash, check, bank transfer, etc.
    transaction_reference = db.Column(db.String(100))
    
    notes = db.Column(db.Text)
    is_confirmed = db.Column(db.Boolean, default=False, index=True)
    confirmed_date = db.Column(db.DateTime)
    is_canceled = db.Column(db.Boolean, default=False, index=True)
    canceled_at = db.Column(db.DateTime)
    canceled_reason = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    documents = db.relationship('Document', backref='payment_report', lazy=True)
    
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
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
    
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
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = db.Column(UUID(as_uuid=True), db.ForeignKey('companies.id'), nullable=False, index=True)
    order_id = db.Column(UUID(as_uuid=True), db.ForeignKey('orders.id'), nullable=False, index=True)
    template_id = db.Column(UUID(as_uuid=True), db.ForeignKey('document_templates.id'))
    quotation_id = db.Column(UUID(as_uuid=True), db.ForeignKey('quotations.id'))
    contract_id = db.Column(UUID(as_uuid=True), db.ForeignKey('contracts.id'))
    handover_record_id = db.Column(UUID(as_uuid=True), db.ForeignKey('handover_records.id'))
    payment_report_id = db.Column(UUID(as_uuid=True), db.ForeignKey('payment_reports.id'))
    
    document_name = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # quotation, contract, delivery, payment
    document_format = db.Column(db.String(10), nullable=False)  # pdf, docx
    
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer)
    
    variables_used = db.Column(db.JSON, default=dict)  # {"var_name": value}
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Document {self.document_name}>'
