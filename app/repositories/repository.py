"""
Repository layer for data access
"""
from app.config.database import db
from app.models import (
    Company, Store, User, Customer, Order, Quotation, Contract,
    HandoverRecord, PaymentReport, Document, DocumentTemplate, LifecycleStatus,
    MaterialUnit, MaterialCategory, Supplier, Material, MaterialStock,
)
from sqlalchemy import and_, desc
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common CRUD operations"""
    
    def __init__(self, model):
        self.model = model
    
    def create(self, **kwargs):
        """Create new record"""
        instance = self.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        return instance
    
    def get_by_id(self, id):
        """Get record by ID"""
        return self.model.query.get(id)
    
    def get_all(self, limit=None, offset=None):
        """Get all records"""
        query = self.model.query
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()
    
    def update(self, id, **kwargs):
        """Update record"""
        instance = self.get_by_id(id)
        if instance:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            db.session.commit()
        return instance
    
    def delete(self, id):
        """Delete record"""
        instance = self.get_by_id(id)
        if instance:
            db.session.delete(instance)
            db.session.commit()
        return True
    
    def count(self):
        """Count total records"""
        return self.model.query.count()


class CompanyRepository(BaseRepository):
    """Repository for Company model"""
    
    def __init__(self):
        super().__init__(Company)
    
    def get_by_code(self, company_code):
        """Get company by code"""
        return self.model.query.filter_by(company_code=company_code).first()
    
    def get_active_companies(self):
        """Get all active companies"""
        return self.model.query.filter_by(is_active=True).all()


class StoreRepository(BaseRepository):
    """Repository for Store model"""
    
    def __init__(self):
        super().__init__(Store)
    
    def get_by_company_and_code(self, company_id, store_code):
        """Get store by company and code"""
        return self.model.query.filter_by(
            company_id=company_id,
            store_code=store_code
        ).first()
    
    def get_stores_for_company(self, company_id):
        """Get all stores for a company"""
        return self.model.query.filter_by(company_id=company_id, is_active=True).all()
    
    def get_active_store(self, company_id, store_id):
        """Get active store for company"""
        return self.model.query.filter_by(
            id=store_id,
            company_id=company_id,
            is_active=True
        ).first()


class UserRepository(BaseRepository):
    """Repository for User model"""
    
    def __init__(self):
        super().__init__(User)
    
    def get_by_username(self, username, company_id):
        """Get user by username in company"""
        return self.model.query.filter_by(
            username=username,
            company_id=company_id,
            is_active=True
        ).first()
    
    def get_by_email(self, email, company_id):
        """Get user by email in company"""
        return self.model.query.filter_by(
            email=email,
            company_id=company_id,
            is_active=True
        ).first()
    
    def get_users_for_company(self, company_id):
        """Get all active users for a company"""
        return self.model.query.filter_by(company_id=company_id, is_active=True).all()

    def get_users_for_store(self, store_id):
        """Get all active users assigned to a specific store"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).all()

    def get_admins_for_company(self, company_id):
        """Get company_admin users for a company"""
        return self.model.query.filter_by(
            company_id=company_id,
            role='company_admin',
            is_active=True
        ).all()


class CustomerRepository(BaseRepository):
    """Repository for Customer model"""
    
    def __init__(self):
        super().__init__(Customer)
    
    def get_for_company(self, id, company_id):
        """Get a customer by id ONLY if it belongs to the given company.

        Tenant-scoped lookup used to prevent cross-tenant IDOR (see AUDIT B5/B7):
        unlike the unscoped BaseRepository.get_by_id, this returns None when the
        customer belongs to another company.
        """
        return self.model.query.filter_by(id=id, company_id=company_id).first()

    def get_by_company_and_code(self, company_id, customer_code):
        """Get customer by company and code (company-wide uniqueness check)"""
        return self.model.query.filter_by(
            company_id=company_id,
            customer_code=customer_code,
            is_active=True
        ).first()

    def get_by_store_and_code(self, store_id, customer_code):
        """Get customer by store and code"""
        return self.model.query.filter_by(
            store_id=store_id,
            customer_code=customer_code,
            is_active=True
        ).first()
    
    def get_customers_for_store(self, store_id, limit=None, offset=None):
        """Get all customers for a store"""
        query = self.model.query.filter_by(store_id=store_id, is_active=True)
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()

    def get_customers_for_stores(self, store_ids, limit=None, offset=None):
        """Get all customers across multiple stores"""
        query = self.model.query.filter(
            self.model.store_id.in_(store_ids), self.model.is_active == True
        ).order_by(self.model.customer_code)
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        return query.all()

    def search_customers_for_stores(self, store_ids, search_term, limit=20):
        """Search customers across multiple stores"""
        return self.model.query.filter(
            self.model.store_id.in_(store_ids), self.model.is_active == True
        ).filter(
            db.or_(
                self.model.name.ilike(f'%{search_term}%'),
                self.model.customer_code.ilike(f'%{search_term}%'),
                self.model.phone.ilike(f'%{search_term}%')
            )
        ).order_by(self.model.customer_code).limit(limit).all()

    def count_for_stores(self, store_ids):
        """Count customers across multiple stores"""
        return self.model.query.filter(
            self.model.store_id.in_(store_ids), self.model.is_active == True
        ).count()

    def search_customers(self, store_id, search_term, limit=20):
        """Search customers by name or code"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).filter(
            db.or_(
                self.model.name.ilike(f'%{search_term}%'),
                self.model.customer_code.ilike(f'%{search_term}%'),
                self.model.phone.ilike(f'%{search_term}%')
            )
        ).limit(limit).all()
    
    def count_for_store(self, store_id):
        """Count customers in store"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).count()


class OrderRepository(BaseRepository):
    """Repository for Order model"""
    
    def __init__(self):
        super().__init__(Order)
    
    def get_by_company_and_code(self, company_id, order_code):
        """Get order by company and code (company-wide uniqueness check)"""
        return self.model.query.filter_by(
            company_id=company_id,
            order_code=order_code,
            is_active=True
        ).first()

    def get_by_store_and_code(self, store_id, order_code):
        """Get order by store and code"""
        return self.model.query.filter_by(
            store_id=store_id,
            order_code=order_code,
            is_active=True
        ).first()
    
    def get_orders_for_customer(self, customer_id):
        """Get all orders for a customer"""
        return self.model.query.filter_by(customer_id=customer_id, is_active=True).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_orders_for_store(self, store_id, limit=None, offset=None):
        """Get all orders for a store"""
        query = self.model.query.filter_by(store_id=store_id, is_active=True).order_by(
            desc(self.model.created_at)
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()
    
    def get_orders_for_company(self, company_id, limit=None, offset=None):
        """Get all orders for a company"""
        query = self.model.query.filter_by(company_id=company_id, is_active=True).order_by(
            desc(self.model.created_at)
        )
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()
    
    def count_for_store(self, store_id):
        """Count orders in store"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).count()


class QuotationRepository(BaseRepository):
    """Repository for Quotation model"""
    
    def __init__(self):
        super().__init__(Quotation)
    
    def get_by_number(self, quotation_number):
        """Get quotation by number"""
        return self.model.query.filter_by(quotation_number=quotation_number).first()

    def get_by_company_and_number(self, company_id, quotation_number):
        """Per-tenant duplicate check: a quotation with this number within the
        given company (joined via its order). Replaces the old global check
        that leaked across tenants (AUDIT W6/B3)."""
        return (self.model.query
                .join(Order, Order.id == self.model.order_id)
                .filter(Order.company_id == company_id,
                        self.model.quotation_number == quotation_number)
                .first())
    
    def get_for_order(self, order_id):
        """Get all quotations for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_latest_for_order(self, order_id):
        """Get latest quotation for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).first()


class ContractRepository(BaseRepository):
    """Repository for Contract model"""
    
    def __init__(self):
        super().__init__(Contract)
    
    def get_by_number(self, contract_number):
        """Get contract by number"""
        return self.model.query.filter_by(contract_number=contract_number).first()
    
    def get_for_order(self, order_id):
        """Get all contracts for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_latest_for_order(self, order_id):
        """Get latest contract for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).first()


class HandoverRecordRepository(BaseRepository):
    """Repository for HandoverRecord model"""
    
    def __init__(self):
        super().__init__(HandoverRecord)
    
    def get_by_number(self, report_number):
        """Get handover record by number"""
        return self.model.query.filter_by(report_number=report_number).first()
    
    def get_for_order(self, order_id):
        """Get all handover records for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_latest_for_order(self, order_id):
        """Get latest delivery report for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).first()


class PaymentReportRepository(BaseRepository):
    """Repository for PaymentReport model"""
    
    def __init__(self):
        super().__init__(PaymentReport)
    
    def get_by_number(self, report_number):
        """Get payment report by number"""
        return self.model.query.filter_by(report_number=report_number).first()
    
    def get_for_order(self, order_id):
        """Get all payment reports for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_for_order_by_type(self, order_id, payment_type):
        """Get payment reports of specific type for order"""
        return self.model.query.filter_by(
            order_id=order_id,
            payment_type=payment_type
        ).order_by(desc(self.model.created_at)).all()


class DocumentRepository(BaseRepository):
    """Repository for Document model"""
    
    def __init__(self):
        super().__init__(Document)
    
    def get_for_order(self, order_id):
        """Get all documents for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    
    def get_for_quotation(self, quotation_id):
        """Get documents for quotation"""
        return self.model.query.filter_by(quotation_id=quotation_id).all()
    
    def get_for_contract(self, contract_id):
        """Get documents for contract"""
        return self.model.query.filter_by(contract_id=contract_id).all()
    
    def get_for_delivery(self, handover_record_id):
        """Get documents for handover record"""
        return self.model.query.filter_by(handover_record_id=handover_record_id).all()
    
    def get_for_payment(self, payment_report_id):
        """Get documents for payment report"""
        return self.model.query.filter_by(payment_report_id=payment_report_id).all()


class DocumentTemplateRepository(BaseRepository):
    """Repository for DocumentTemplate model"""
    
    def __init__(self):
        super().__init__(DocumentTemplate)
    
    def get_for_company(self, company_id, document_type=None):
        """Get templates for company"""
        query = self.model.query.filter_by(company_id=company_id, is_active=True)
        if document_type:
            query = query.filter_by(document_type=document_type)
        return query.all()
    
    def get_default_for_type(self, company_id, document_type):
        """Get default template for document type"""
        return self.model.query.filter_by(
            company_id=company_id,
            document_type=document_type,
            is_active=True
        ).first()


class LifecycleStatusRepository(BaseRepository):
    """Repository for LifecycleStatus model"""
    
    def __init__(self):
        super().__init__(LifecycleStatus)
    
    def get_for_order(self, order_id):
        """Get lifecycle status for order"""
        return self.model.query.filter_by(order_id=order_id).first()
    
    def get_or_create_for_order(self, order_id):
        """Get or create lifecycle status for order"""
        status = self.get_for_order(order_id)
        if not status:
            status = self.create(order_id=order_id)
        return status


# ── Material Management Repositories ────────────────────────────────────────

class MaterialUnitRepository(BaseRepository):
    """Repository for MaterialUnit model"""

    def __init__(self):
        super().__init__(MaterialUnit)

    def get_for_company(self, company_id, active_only=True):
        """All units for a company, optionally only active."""
        q = self.model.query.filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(self.model.name).all()

    def get_by_name(self, company_id, name):
        """Get unit by exact name within company."""
        return self.model.query.filter_by(company_id=company_id, name=name).first()


class MaterialCategoryRepository(BaseRepository):
    """Repository for MaterialCategory model"""

    def __init__(self):
        super().__init__(MaterialCategory)

    def get_for_company(self, company_id, active_only=True):
        """All categories for a company ordered by sort_order then name."""
        q = self.model.query.filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(self.model.sort_order, self.model.name).all()

    def get_by_name(self, company_id, name):
        """Get category by exact name within company."""
        return self.model.query.filter_by(company_id=company_id, name=name).first()


class MaterialRepository(BaseRepository):
    """Repository for Material model"""

    def __init__(self):
        super().__init__(Material)

    def get_for_company(self, company_id, category_id=None, active_only=True, search=None):
        """All materials for a company with optional filters."""
        q = self.model.query.filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        if category_id:
            q = q.filter_by(category_id=category_id)
        if search:
            pattern = f'%{search}%'
            q = q.outerjoin(Supplier, self.model.supplier_id == Supplier.id).filter(
                (self.model.name.ilike(pattern)) |
                (self.model.material_code.ilike(pattern)) |
                (Supplier.name.ilike(pattern))
            )
        return q.order_by(self.model.material_code).all()

    def get_by_code(self, company_id, material_code):
        """Get material by code within company."""
        return self.model.query.filter_by(
            company_id=company_id, material_code=material_code
        ).first()

    def count_for_company(self, company_id, active_only=True):
        """Count materials for a company."""
        q = self.model.query.filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.count()


class MaterialStockRepository(BaseRepository):
    """Repository for MaterialStock model"""

    def __init__(self):
        super().__init__(MaterialStock)

    def get_for_material(self, material_id):
        """All stock entries for a material."""
        return self.model.query.filter_by(material_id=material_id).all()

    def get_for_store(self, company_id, store_id):
        """All stock entries for a specific store."""
        return self.model.query.filter_by(
            company_id=company_id, store_id=store_id
        ).all()

    def get_entry(self, material_id, store_id):
        """Get the single stock entry for material+store (store_id may be None for company warehouse)."""
        return self.model.query.filter_by(
            material_id=material_id, store_id=store_id
        ).first()

    def get_or_create_entry(self, material_id, company_id, store_id):
        """Get or create a stock entry row."""
        entry = self.get_entry(material_id, store_id)
        if not entry:
            entry = self.create(
                material_id=material_id,
                company_id=company_id,
                store_id=store_id,
                current_quantity=0,
            )
        return entry

    def upsert_quantity(self, material_id, company_id, store_id, quantity):
        """Set (overwrite) current_quantity for a stock entry."""
        from app.config.database import db as _db
        entry = self.get_or_create_entry(material_id, company_id, store_id)
        entry.current_quantity = quantity
        entry.last_updated = datetime.utcnow()
        _db.session.commit()
        return entry


class SupplierRepository(BaseRepository):
    """Repository for Supplier model"""

    def __init__(self):
        super().__init__(Supplier)

    def get_for_company(self, company_id, active_only=True):
        """All suppliers for a company ordered by name."""
        q = self.model.query.filter_by(company_id=company_id)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(self.model.name).all()

    def get_by_code(self, company_id, supplier_code):
        """Get supplier by code within company."""
        return self.model.query.filter_by(
            company_id=company_id, supplier_code=supplier_code
        ).first()

    def get_next_code(self, company_id):
        """Auto-generate next supplier code: NCC-001, NCC-002 ..."""
        count = self.model.query.filter_by(company_id=company_id).count()
        return f'NCC-{count + 1:03d}'
