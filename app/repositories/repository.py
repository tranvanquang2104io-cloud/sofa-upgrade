"""
Repository layer for data access
"""
from app.config.database import db
from app.models import (
    Company, Store, User, Customer, Order, Quotation, Contract,
    DeliveryReport, PaymentReport, Document, DocumentTemplate, LifecycleStatus
)
from sqlalchemy import and_, desc
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
        """Get all users for a company"""
        return self.model.query.filter_by(company_id=company_id, is_active=True).all()
    
    def get_admins_for_company(self, company_id):
        """Get admin users for company"""
        return self.model.query.filter_by(
            company_id=company_id,
            role='admin',
            is_active=True
        ).all()


class CustomerRepository(BaseRepository):
    """Repository for Customer model"""
    
    def __init__(self):
        super().__init__(Customer)
    
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


class DeliveryReportRepository(BaseRepository):
    """Repository for DeliveryReport model"""
    
    def __init__(self):
        super().__init__(DeliveryReport)
    
    def get_by_number(self, report_number):
        """Get delivery report by number"""
        return self.model.query.filter_by(report_number=report_number).first()
    
    def get_for_order(self, order_id):
        """Get all delivery reports for order"""
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
    
    def get_for_delivery(self, delivery_report_id):
        """Get documents for delivery report"""
        return self.model.query.filter_by(delivery_report_id=delivery_report_id).all()
    
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
