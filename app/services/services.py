"""
Service layer for business logic
"""
import os
from datetime import datetime
from flask import current_app
from app.config.database import db
from app.repositories.repository import (
    CompanyRepository, StoreRepository, UserRepository, CustomerRepository,
    OrderRepository, QuotationRepository, ContractRepository,
    HandoverRecordRepository, PaymentReportRepository, DocumentRepository,
    DocumentTemplateRepository, LifecycleStatusRepository,
    MaterialUnitRepository, MaterialCategoryRepository,
    SupplierRepository, MaterialRepository, MaterialStockRepository,
)
from app.utils.template_engine import TemplateEngine, DocxTemplateEngine, DocumentVariableCollector
from app.models import Document, Order, Quotation, Contract, HandoverRecord
import logging

logger = logging.getLogger(__name__)


class CompanyService:
    """Service for company management"""
    
    def __init__(self):
        self.repo = CompanyRepository()
    
    def create_company(self, company_code, name, email, phone=None, address=None, city=None, country=None):
        """Create new company"""
        existing = self.repo.get_by_code(company_code)
        if existing:
            raise ValueError(f"Company with code {company_code} already exists")

        company = self.repo.create(
            company_code=company_code,
            name=name,
            email=email,
            phone=phone,
            address=address,
            city=city,
            country=country
        )

        # Auto-create company template subfolder
        try:
            templates_base = current_app.config.get('TEMPLATES_FOLDER')
            if templates_base:
                safe_code = company_code.replace('/', '_').replace('\\', '_')
                os.makedirs(os.path.join(templates_base, safe_code), exist_ok=True)
                logger.info(f"Created template folder for company: {company_code}")
        except RuntimeError:
            pass  # Outside app context (tests)

        logger.info(f"Company created: {company_code}")
        return company
    
    def get_company(self, company_id):
        """Get company by ID"""
        return self.repo.get_by_id(company_id)
    
    def list_companies(self):
        """List all active companies"""
        return self.repo.get_active_companies()


class StoreService:
    """Service for store management"""
    
    def __init__(self):
        self.repo = StoreRepository()
    
    def create_store(self, company_id, store_code, name, manager_name=None, phone=None, address=None, city=None):
        """Create new store for company"""
        existing = self.repo.get_by_company_and_code(company_id, store_code)
        if existing:
            raise ValueError(f"Store with code {store_code} already exists in company")
        
        store = self.repo.create(
            company_id=company_id,
            store_code=store_code,
            name=name,
            manager_name=manager_name,
            phone=phone,
            address=address,
            city=city
        )
        logger.info(f"Store created: {store_code} for company {company_id}")
        return store
    
    def get_store(self, store_id, company_id):
        """Get store"""
        return self.repo.get_active_store(company_id, store_id)
    
    def list_stores_for_company(self, company_id):
        """List all stores for company"""
        return self.repo.get_stores_for_company(company_id)

    def update_store(self, store_id, name=None, manager_name=None, phone=None, address=None, city=None):
        """Update store details"""
        store = self.repo.get_by_id(store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")
        if name         is not None: store.name         = name
        if manager_name is not None: store.manager_name = manager_name
        if phone        is not None: store.phone        = phone
        if address      is not None: store.address      = address
        if city         is not None: store.city         = city
        db.session.commit()
        return store

    def deactivate_store(self, store_id):
        """Soft-deactivate a store"""
        store = self.repo.get_by_id(store_id)
        if not store:
            raise ValueError(f"Store {store_id} not found")
        store.is_active = False
        db.session.commit()
        return store


class UserService:
    """Service for user management"""
    
    def __init__(self):
        self.repo = UserRepository()
    
    def create_user(self, company_id, username, email, password, full_name,
                    role='user', store_id=None, phone=None, position=None):
        """Create new user"""
        existing = self.repo.get_by_username(username, company_id)
        if existing:
            raise ValueError(f"User with username {username} already exists")

        user = self.repo.create(
            company_id=company_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            store_id=store_id,
            phone=phone,
            position=position,
        )
        user.set_password(password)
        db.session.commit()
        logger.info(f"User created: {username} for company {company_id}")
        return user

    def authenticate_user(self, username, password, company_id):
        """Authenticate user"""
        user = self.repo.get_by_username(username, company_id)
        if user and user.check_password(password):
            return user
        return None

    def authenticate_by_email(self, email, password):
        """Authenticate by email + password (global — email is unique).

        Email is the login identifier, so the company is derived from the user.
        Case-insensitive email match; only active users can log in.
        """
        from sqlalchemy import func
        from app.models.models import User
        email = (email or '').strip().lower()
        if not email:
            return None
        user = User.query.filter(func.lower(User.email) == email,
                                 User.is_active == True).first()
        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        """Get user by ID"""
        return self.repo.get_by_id(user_id)

    def list_users_for_company(self, company_id):
        """List all active users for company"""
        return self.repo.get_users_for_company(company_id)

    def list_users_for_store(self, store_id):
        """List all active users for a store"""
        return self.repo.get_users_for_store(store_id)

    def update_user(self, user_id, full_name=None, email=None, phone=None,
                    position=None, role=None, store_id=None, password=None):
        """Update user profile / role / store assignment"""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        if full_name  is not None: user.full_name  = full_name
        if email      is not None: user.email      = email
        if phone      is not None: user.phone      = phone
        if position   is not None: user.position   = position
        if role       is not None: user.role       = role
        if store_id   is not None: user.store_id   = store_id
        if password:
            user.set_password(password)
        db.session.commit()
        return user

    def deactivate_user(self, user_id):
        """Soft-delete / deactivate a user"""
        user = self.repo.get_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.is_active = False
        db.session.commit()
        return user


class CustomerService:
    """Service for customer management"""
    
    def __init__(self):
        self.repo = CustomerRepository()
    
    def create_customer(self, company_id, store_id, customer_code, name, phone=None, email=None,
                       address=None, city=None, postal_code=None, country=None, notes=None,
                       tax_code=None, representative_name=None, representative_title=None):
        """Create new customer"""
        existing = self.repo.get_by_company_and_code(company_id, customer_code)
        if existing:
            raise ValueError(f"Mã khách hàng {customer_code} đã tồn tại. Vui lòng dùng mã khác.")
        
        customer = self.repo.create(
            company_id=company_id,
            store_id=store_id,
            customer_code=customer_code,
            name=name,
            phone=phone,
            email=email,
            address=address,
            city=city,
            postal_code=postal_code,
            country=country,
            tax_code=tax_code,
            representative_name=representative_name,
            representative_title=representative_title,
            notes=notes
        )

        # Auto-create customer document subfolder
        try:
            docs_base = current_app.config.get('DOCUMENTS_FOLDER')
            if docs_base:
                safe_code = customer_code.replace('/', '_').replace('\\', '_')
                os.makedirs(os.path.join(docs_base, safe_code), exist_ok=True)
                logger.info(f"Created document folder for customer: {customer_code}")
        except RuntimeError:
            pass

        logger.info(f"Customer created: {customer_code}")
        return customer
    
    def get_customer(self, customer_id):
        """Get customer"""
        return self.repo.get_by_id(customer_id)
    
    def list_customers_for_store(self, store_id, page=1, per_page=20):
        """List customers for store with pagination"""
        offset = (page - 1) * per_page
        return self.repo.get_customers_for_store(store_id, limit=per_page, offset=offset)
    
    def search_customers(self, store_id, search_term):
        """Search customers"""
        return self.repo.search_customers(store_id, search_term)
    
    def count_customers_for_store(self, store_id):
        """Count customers in store"""
        return self.repo.count_for_store(store_id)

    def update_customer(self, customer_id, name=None, phone=None, email=None,
                        address=None, city=None, postal_code=None, country=None,
                        tax_code=None, representative_name=None, representative_title=None,
                        notes=None):
        """Update customer information"""
        customer = self.repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        fields = {
            'name': name,
            'phone': phone,
            'email': email,
            'address': address,
            'city': city,
            'postal_code': postal_code,
            'country': country,
            'tax_code': tax_code,
            'representative_name': representative_name,
            'representative_title': representative_title,
            'notes': notes,
        }
        for field, value in fields.items():
            if value is not None:
                setattr(customer, field, value if value != '' else None)

        from app.config.database import db
        db.session.commit()
        logger.info(f"Customer updated: {customer_id}")
        return customer


class OrderService:
    """Service for order management"""
    
    def __init__(self):
        self.repo = OrderRepository()
        self.lifecycle_repo = LifecycleStatusRepository()
    
    def create_order(self, store_id, company_id, customer_id, order_code, title,
                    description=None, notes=None):
        """Create new order"""
        existing = self.repo.get_by_company_and_code(company_id, order_code)
        if existing:
            raise ValueError(f"Mã đơn hàng {order_code} đã tồn tại. Vui lòng dùng mã khác.")

        order = self.repo.create(
            store_id=store_id,
            company_id=company_id,
            customer_id=customer_id,
            order_code=order_code,
            title=title,
            description=description,
            notes=notes
        )

        # Create lifecycle status
        self.lifecycle_repo.create(order_id=order.id)

        # Auto-create order document subfolders (one per document type)
        try:
            docs_base = current_app.config.get('DOCUMENTS_FOLDER')
            if docs_base:
                from app.models.models import Customer as _Cust
                cust = db.session.get(_Cust, customer_id)
                if cust:
                    safe_cust  = cust.customer_code.replace('/', '_').replace('\\', '_')
                    safe_order = order_code.replace('/', '_').replace('\\', '_')
                    base = os.path.join(docs_base, safe_cust, safe_order)
                    for doc_type in ('quotation', 'contract', 'handover', 'delivery', 'payment', 'request_payment'):
                        os.makedirs(os.path.join(base, doc_type), exist_ok=True)
                    logger.info(f"Created document folders for order: {order_code}")
        except RuntimeError:
            pass

        logger.info(f"Order created: {order_code}")
        return order
    
    def get_order(self, order_id, company_id):
        """Get order - verify company access"""
        order = self.repo.get_by_id(order_id)
        if order and str(order.company_id) == str(company_id):
            return order
        return None
    
    def list_orders_for_customer(self, customer_id):
        """List orders for customer"""
        return self.repo.get_orders_for_customer(customer_id)
    
    def list_orders_for_store(self, store_id, page=1, per_page=20):
        """List orders for store"""
        offset = (page - 1) * per_page
        return self.repo.get_orders_for_store(store_id, limit=per_page, offset=offset)
    
    def list_orders_for_company(self, company_id, page=1, per_page=20):
        """List orders for company"""
        offset = (page - 1) * per_page
        return self.repo.get_orders_for_company(company_id, limit=per_page, offset=offset)
    
    def get_order_with_details(self, order_id, company_id):
        """Get order with all related data"""
        from app.repositories.repository import QuotationRepository, ContractRepository
        from app.repositories.repository import HandoverRecordRepository, PaymentReportRepository
        
        order = self.get_order(order_id, company_id)
        if not order:
            return None
        
        return {
            'order': order,
            'quotations': QuotationRepository().get_for_order(order_id),
            'contracts': ContractRepository().get_for_order(order_id),
            'handover_records': HandoverRecordRepository().get_for_order(order_id),
            'payment_reports': PaymentReportRepository().get_for_order(order_id),
            'lifecycle': order.lifecycle
        }
    
    def update_order_totals(self, order_id, total_amount=None, advance_amount=None, final_amount=None):
        """Update order financial totals"""
        order = self.repo.get_by_id(order_id)
        if order:
            if total_amount is not None:
                order.total_amount = total_amount
            if advance_amount is not None:
                order.advance_amount = advance_amount
            if final_amount is not None:
                order.final_amount = final_amount
            db.session.commit()
        return order


class QuotationService:
    """Service for quotation management"""
    
    def __init__(self):
        self.repo = QuotationRepository()
        self.order_service = OrderService()
    
    def create_quotation(self, order_id, quotation_number, quotation_date, items,
                        total_amount, validity_days=30, notes=None,
                        city=None, subtotal=None, vat_rate=8.0, vat_amount=0,
                        payment_terms=None, amount_in_words=None,
                        shipping_fee=0, another_fee=0, company_id=None):
        """Create quotation"""
        # Per-tenant duplicate check (AUDIT W6/B3): scope by company when known,
        # else fall back to the order's company.
        if company_id is None:
            _order = OrderRepository().get_by_id(order_id)
            company_id = _order.company_id if _order else None
        existing = self.repo.get_by_company_and_number(company_id, quotation_number)
        if existing:
            raise ValueError(f"Quotation {quotation_number} already exists")
        
        if subtotal is None:
            subtotal = total_amount

        quotation = self.repo.create(
            order_id=order_id,
            quotation_number=quotation_number,
            quotation_date=quotation_date,
            items=items,
            subtotal=subtotal,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            shipping_fee=shipping_fee,
            another_fee=another_fee,
            total_amount=total_amount,
            validity_days=validity_days,
            city=city,
            payment_terms=payment_terms,
            amount_in_words=amount_in_words,
            notes=notes
        )
        
        # Update order totals
        self.order_service.update_order_totals(order_id, total_amount=total_amount)
        
        # Update lifecycle - explicitly add to session and commit
        lifecycle = self._get_or_create_lifecycle(order_id)
        lifecycle.quotation_created = True
        lifecycle.quotation_created_at = datetime.utcnow()
        db.session.add(lifecycle)  # Ensure it's in the session
        db.session.commit()
        
        logger.info(f"Quotation created: {quotation_number}")
        return quotation
    
    def get_quotation(self, quotation_id):
        """Get quotation"""
        return self.repo.get_by_id(quotation_id)
    
    def list_quotations_for_order(self, order_id):
        """List quotations for order"""
        return self.repo.get_for_order(order_id)
    
    def approve_quotation(self, quotation_id, order_id):
        """Mark quotation as approved"""
        quotation = self.repo.get_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        
        if not quotation.can_approve():
            raise ValueError("Quotation cannot be approved in its current state")
        
        quotation.is_approved = True
        db.session.commit()
        
        # Update lifecycle - explicitly add to session and commit
        lifecycle = self._get_or_create_lifecycle(order_id)
        lifecycle.quotation_approved = True
        lifecycle.quotation_approved_at = datetime.utcnow()
        db.session.add(lifecycle)  # Ensure it's in the session
        db.session.commit()
        
        logger.info(f"Quotation approved: {quotation.quotation_number}")
        return quotation
    
    def cancel_quotation(self, quotation_id, reason=""):
        """Cancel an active quotation"""
        quotation = self.repo.get_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        
        if not quotation.can_cancel():
            raise ValueError("Quotation cannot be canceled in its current state")
        
        quotation.is_canceled = True
        quotation.is_active = False
        quotation.canceled_at = datetime.utcnow()
        quotation.canceled_reason = reason
        db.session.commit()
        
        logger.info(f"Quotation canceled: {quotation.quotation_number}")
        return quotation
    
    def update_quotation(self, quotation_id, items=None, total_amount=None, validity_days=None,
                         notes=None, city=None, subtotal=None, vat_rate=None, vat_amount=None,
                         payment_terms=None, amount_in_words=None,
                         shipping_fee=None, another_fee=None):
        """Update quotation - only if not approved"""
        quotation = self.repo.get_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        
        if not quotation.can_edit():
            raise ValueError("Quotation cannot be edited after approval")
        
        if items is not None:
            quotation.items = items
        if total_amount is not None:
            quotation.total_amount = total_amount
            self.order_service.update_order_totals(quotation.order_id, total_amount=total_amount)
        if validity_days is not None:
            quotation.validity_days = validity_days
        if notes is not None:
            quotation.notes = notes
        if city is not None:
            quotation.city = city
        if subtotal is not None:
            quotation.subtotal = subtotal
        if vat_rate is not None:
            quotation.vat_rate = vat_rate
        if vat_amount is not None:
            quotation.vat_amount = vat_amount
        if shipping_fee is not None:
            quotation.shipping_fee = shipping_fee
        if another_fee is not None:
            quotation.another_fee = another_fee
        if payment_terms is not None:
            quotation.payment_terms = payment_terms
        if amount_in_words is not None:
            quotation.amount_in_words = amount_in_words
        
        db.session.commit()
        logger.info(f"Quotation updated: {quotation.quotation_number}")
        return quotation
    
    def get_active_quotation_for_order(self, order_id):
        """Get the currently active quotation for an order"""
        return db.session.query(Quotation).filter_by(
            order_id=order_id, is_active=True, is_canceled=False
        ).first()
    
    def _get_or_create_lifecycle(self, order_id):
        """Helper to get or create lifecycle"""
        lifecycle = LifecycleStatusRepository().get_for_order(order_id)
        if not lifecycle:
            lifecycle = LifecycleStatusRepository().create(order_id=order_id)
        return lifecycle


class ContractService:
    """Service for contract management"""
    
    def __init__(self):
        self.repo = ContractRepository()
    
    def create_contract(self, order_id, quotation_id, contract_number, contract_date, 
                       contract_value, terms_and_conditions=None):
        """Create contract"""
        _order = OrderRepository().get_by_id(order_id)
        existing = self.repo.get_by_company_and_number(
            _order.company_id if _order else None, contract_number)
        if existing:
            raise ValueError(f"Contract {contract_number} already exists")
        
        # IMPORTANT: Single-active-contract constraint
        # Mark any existing active contracts as inactive
        from app.repositories.repository import ContractRepository
        active_contracts = db.session.query(Contract).filter(
            Contract.order_id == order_id,
            Contract.is_active == True
        ).all()
        
        for old_contract in active_contracts:
            old_contract.is_active = False
            logger.info(f"Deactivated previous contract: {old_contract.contract_number}")
        
        # Copy items from quotation if available
        items = []
        if quotation_id:
            from app.repositories.repository import QuotationRepository
            quotation = QuotationRepository().get_by_id(quotation_id)
            if quotation and quotation.items:
                items = list(quotation.items)  # Deep copy of items list
        
        # Create new contract
        contract = self.repo.create(
            order_id=order_id,
            quotation_id=quotation_id,
            contract_number=contract_number,
            contract_date=contract_date,
            contract_value=contract_value,
            items=items,
            terms_and_conditions=terms_and_conditions
        )
        
        # Update lifecycle atomically - mark contract as created
        lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
        lifecycle.contract_created = True
        lifecycle.contract_created_at = datetime.utcnow()
        
        # Commit all changes together for atomicity
        db.session.add(lifecycle)
        db.session.commit()
        
        logger.info(f"Contract created: {contract_number} (deactivated {len(active_contracts)} previous contracts)")
        return contract
    
    def get_contract(self, contract_id):
        """Get contract"""
        return self.repo.get_by_id(contract_id)
    
    def mark_signed(self, contract_id, order_id):
        """Mark contract as signed and update lifecycle atomically"""
        try:
            contract = self.repo.get_by_id(contract_id)
            if not contract:
                raise ValueError(f"Contract {contract_id} not found")
            
            if contract.is_signed:
                logger.warning(f"Contract {contract_id} already signed at {contract.signed_date}")
                return contract
            
            # Update contract
            contract.is_signed = True
            contract.signed_date = datetime.utcnow()
            
            # Update lifecycle - mark contract as signed
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            lifecycle.contract_signed = True
            lifecycle.contract_signed_at = datetime.utcnow()
            
            # Make both updates atomic - add both to session before committing
            db.session.add(contract)
            db.session.add(lifecycle)
            db.session.commit()

            # Feature 2: auto-create a production plan once the contract is signed.
            # Best-effort — a failure here must not break the signing flow.
            try:
                ProductionPlanService().create_from_contract(contract)
            except Exception as _pp_err:
                logger.error(f"Auto production-plan failed for contract {contract_id}: {_pp_err}")

            logger.info(f"Contract {contract.contract_number} signed and lifecycle updated")
            return contract
            
        except Exception as e:
            logger.error(f"Error marking contract as signed: {str(e)}")
            db.session.rollback()
            raise
    
    def cancel_contract(self, contract_id, order_id, reason=""):
        """Cancel contract and update lifecycle atomically"""
        try:
            contract = self.repo.get_by_id(contract_id)
            if not contract:
                raise ValueError(f"Contract {contract_id} not found")
            
            if not contract.can_cancel():
                raise ValueError("Contract cannot be canceled (already signed or canceled)")
            
            # Update contract
            contract.is_canceled = True
            contract.canceled_at = datetime.utcnow()
            contract.canceled_reason = reason
            contract.is_active = False
            
            # Update lifecycle - reset contract creation if no other active contract
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            
            # Check if there are any other active contracts
            other_active = db.session.query(Contract).filter(
                Contract.order_id == order_id,
                Contract.is_active == True,
                Contract.id != contract_id
            ).first()
            
            if not other_active:
                lifecycle.contract_created = False
                lifecycle.contract_created_at = None
            
            # Make both updates atomic
            db.session.add(contract)
            db.session.add(lifecycle)
            db.session.commit()
            
            logger.info(f"Contract {contract.contract_number} canceled with reason: {reason}")
            return contract
            
        except Exception as e:
            logger.error(f"Error canceling contract: {str(e)}")
            db.session.rollback()
            raise


class HandoverRecordService:
    """Service for handover record management (Biên Bản Bàn Giao)"""
    
    def __init__(self):
        self.repo = HandoverRecordRepository()
    
    def create_handover_record(self, order_id, report_number, report_date, handover_date,
                              customer_representative=None, company_representative=None,
                              product_condition=None, items=None, notes=None,
                              handover_location=None, start_time=None, end_time=None,
                              copies_count=2, vat_rate=8.0, vat_amount=0,
                              subtotal=0, total_amount=0,
                              shipping_fee=0, another_fee=0,
                              customer_representative_title=None,
                              company_representative_title=None):
        """Create handover record"""
        _order = OrderRepository().get_by_id(order_id)
        existing = self.repo.get_by_company_and_number(
            _order.company_id if _order else None, report_number)
        if existing:
            raise ValueError(f"Handover record {report_number} already exists")
        
        # Check workflow: advance payment must be confirmed before handover
        order = OrderRepository().get_by_id(order_id)
        if not order or not order.lifecycle or not order.lifecycle.advance_paid:
            raise ValueError("Advance payment must be confirmed before creating handover record")
        
        record = self.repo.create(
            order_id=order_id,
            report_number=report_number,
            report_date=report_date,
            handover_date=handover_date,
            handover_location=handover_location,
            start_time=start_time,
            end_time=end_time,
            copies_count=copies_count,
            customer_representative=customer_representative,
            customer_representative_title=customer_representative_title,
            company_representative=company_representative,
            company_representative_title=company_representative_title,
            product_condition=product_condition,
            items=items or [],
            subtotal=subtotal,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            shipping_fee=shipping_fee,
            another_fee=another_fee,
            total_amount=total_amount,
            notes=notes
        )
        
        logger.info(f"Handover record created: {report_number}")
        return record
    
    def get_handover_record(self, record_id):
        """Get handover record"""
        return self.repo.get_by_id(record_id)
    
    def confirm_handover(self, record_id, order_id):
        """Mark handover as confirmed and update lifecycle atomically"""
        try:
            record = self.repo.get_by_id(record_id)
            if not record:
                raise ValueError(f"Handover record {record_id} not found")
            
            if record.is_confirmed:
                logger.warning(f"Handover {record_id} already confirmed at {record.confirmed_date}")
                return record
            
            if not record.can_confirm():
                raise ValueError("Handover record cannot be confirmed (already confirmed or canceled)")
            
            # Update handover record
            record.is_confirmed = True
            record.confirmed_date = datetime.utcnow()
            record.customer_signature_confirmed = True
            
            # Update lifecycle - mark handover as confirmed
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            lifecycle.handover_confirmed = True
            lifecycle.handover_confirmed_at = datetime.utcnow()
            
            # Make both updates atomic - add both to session before committing
            db.session.add(record)
            db.session.add(lifecycle)
            db.session.commit()
            
            logger.info(f"Handover {record.report_number} confirmed and lifecycle updated")
            return record
            
        except Exception as e:
            logger.error(f"Error confirming handover: {str(e)}")
            db.session.rollback()
            raise
    
    def cancel_handover(self, record_id, order_id, reason=""):
        """Cancel handover record and update lifecycle atomically"""
        try:
            record = self.repo.get_by_id(record_id)
            if not record:
                raise ValueError(f"Handover record {record_id} not found")
            
            if not record.can_cancel():
                raise ValueError("Handover record cannot be canceled (already confirmed or canceled)")
            
            # Update handover record
            record.is_canceled = True
            record.canceled_at = datetime.utcnow()
            record.canceled_reason = reason
            
            # Lifecycle does not revert - handover can be recreated after cancellation
            
            # Make update atomic
            db.session.add(record)
            db.session.commit()
            
            logger.info(f"Handover record {record.report_number} canceled with reason: {reason}")
            return record
            
        except Exception as e:
            logger.error(f"Error canceling handover record: {str(e)}")
            db.session.rollback()
            raise


class PaymentReportService:
    """Service for payment report management"""
    
    def __init__(self):
        self.repo = PaymentReportRepository()
    
    def create_payment_report(self, order_id, report_number, payment_type, report_date,
                             payment_date, amount, payment_method=None,
                             transaction_reference=None, notes=None,
                             items=None, subtotal=0, vat_rate=8.0, vat_amount=0,
                             shipping_fee=0, another_fee=0,
                             advance_percentage=None, advance_amount=0,
                             remaining_amount=0, amount_in_words=None,
                             work_completed_summary=None,
                             quotation_reference_date=None,
                             bank_account_info=None):
        """Create payment report"""
        _order = OrderRepository().get_by_id(order_id)
        existing = self.repo.get_by_company_and_number(
            _order.company_id if _order else None, report_number)
        if existing:
            raise ValueError(f"Payment report {report_number} already exists")
        
        # Validate workflow sequencing
        order = OrderRepository().get_by_id(order_id)
        if not order or not order.lifecycle:
            raise ValueError("Order not found")
        
        if payment_type == 'advance':
            if not order.lifecycle.contract_signed:
                raise ValueError("Advance payment can only be created after contract is signed")
        elif payment_type == 'final':
            if not order.lifecycle.handover_confirmed:
                raise ValueError("Final payment can only be created after handover record is confirmed")
        
        report = self.repo.create(
            order_id=order_id,
            report_number=report_number,
            payment_type=payment_type,
            report_date=report_date,
            payment_date=payment_date,
            items=items or [],
            subtotal=subtotal,
            vat_rate=vat_rate,
            vat_amount=vat_amount,
            shipping_fee=shipping_fee,
            another_fee=another_fee,
            amount=amount,
            advance_percentage=advance_percentage,
            advance_amount=advance_amount,
            remaining_amount=remaining_amount,
            amount_in_words=amount_in_words,
            work_completed_summary=work_completed_summary,
            quotation_reference_date=quotation_reference_date,
            bank_account_info=bank_account_info or [],
            payment_method=payment_method,
            transaction_reference=transaction_reference,
            notes=notes
        )
        
        logger.info(f"Payment report created: {report_number}")
        return report
    
    def get_payment_report(self, report_id):
        """Get payment report"""
        return self.repo.get_by_id(report_id)
    
    def mark_confirmed(self, report_id, order_id):
        """Mark payment as confirmed and update lifecycle atomically"""
        try:
            report = self.repo.get_by_id(report_id)
            if not report:
                raise ValueError(f"Payment report {report_id} not found")
            
            if report.is_confirmed:
                logger.warning(f"Payment {report_id} already confirmed at {report.confirmed_date}")
                return report
            
            # Update payment report
            report.is_confirmed = True
            report.confirmed_date = datetime.utcnow()
            
            # Update lifecycle - mark payment as confirmed
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            
            if report.payment_type == 'advance':
                lifecycle.advance_paid = True
                lifecycle.advance_paid_at = datetime.utcnow()
                logger.info(f"Advance payment confirmed for order {order_id}")
            elif report.payment_type == 'final':
                lifecycle.fully_paid = True
                lifecycle.fully_paid_at = datetime.utcnow()
                # Mark order as completed only when final payment is done
                lifecycle.completed = True
                lifecycle.completed_at = datetime.utcnow()
                logger.info(f"Final payment confirmed - order {order_id} completed")
            
            # Make all updates atomic - add both to session before committing
            db.session.add(report)
            db.session.add(lifecycle)
            db.session.commit()
            
            logger.info(f"Payment {report.report_number} confirmed and lifecycle updated")
            return report
            
        except Exception as e:
            logger.error(f"Error confirming payment: {str(e)}")
            db.session.rollback()
            raise
    
    def cancel_payment(self, payment_id, order_id, reason=""):
        """Cancel payment report and update lifecycle atomically"""
        try:
            payment = self.repo.get_by_id(payment_id)
            if not payment:
                raise ValueError(f"Payment report {payment_id} not found")
            
            if not payment.can_cancel():
                raise ValueError("Payment cannot be canceled (already confirmed or canceled)")
            
            # Update payment report
            payment.is_canceled = True
            payment.canceled_at = datetime.utcnow()
            payment.canceled_reason = reason

            # If this was a confirmed advance payment, check if lifecycle should revert
            if payment.payment_type == 'advance' and payment.is_confirmed:
                from app.repositories.repository import LifecycleStatusRepository, PaymentReportRepository as _PRRepo
                from app.models.models import PaymentReport as _PR
                remaining_confirmed = db.session.query(_PR).filter(
                    _PR.order_id == payment.order_id,
                    _PR.payment_type == 'advance',
                    _PR.is_confirmed == True,
                    _PR.is_canceled == False,
                    _PR.id != payment.id
                ).count()
                lifecycle = LifecycleStatusRepository().get_or_create_for_order(str(payment.order_id))
                if remaining_confirmed == 0 and not getattr(lifecycle, 'advance_skipped', False):
                    lifecycle.advance_paid = False
                    lifecycle.advance_paid_at = None
                    db.session.add(lifecycle)
            
            # Make update atomic
            db.session.add(payment)
            db.session.commit()
            
            logger.info(f"Payment {payment.report_number} canceled with reason: {reason}")
            return payment
            
        except Exception as e:
            logger.error(f"Error canceling payment: {str(e)}")
            db.session.rollback()
            raise


class DocumentService:
    """Service for document management"""
    
    def __init__(self):
        self.repo = DocumentRepository()
        self.template_repo = DocumentTemplateRepository()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_company(self, company_id):
        """Load Company object (silently returns None if not found)."""
        try:
            from app.repositories.repository import CompanyRepository
            return CompanyRepository().get_by_id(company_id)
        except Exception:
            return None

    def _get_template_file_path(self, template) -> str:
        """Build absolute path to the template file.

        Resolution order:
          1. templates/{company_code}/{filename}  (per-company subfolder)
          2. templates/{company_id}/{filename}    (legacy UUID subfolder)
          3. templates/{filename}                 (legacy flat folder)
        """
        templates_dir = current_app.config['TEMPLATES_FOLDER']

        # 1. company_code subfolder
        try:
            company_code = template.company.company_code if template.company else None
        except Exception:
            company_code = None

        if company_code:
            safe_code = company_code.replace('/', '_').replace('\\', '_')
            p = os.path.join(templates_dir, safe_code, template.template_file)
            if os.path.exists(p):
                return p

        # 2. company_id subfolder (legacy)
        p = os.path.join(templates_dir, str(template.company_id), template.template_file)
        if os.path.exists(p):
            return p

        # 3. flat folder fallback
        return os.path.join(templates_dir, template.template_file)

    def _save_document(self, *, company_id, order_id, template, document_type,
                       document_format, context,
                       quotation_id=None, contract_id=None,
                       handover_record_id=None, payment_report_id=None):
        """
        Render & persist a document record.

        Chooses docxtpl (DOCX template) or legacy text-substitution based on
        the template file extension.
        """
        from io import BytesIO as _BytesIO

        timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_name   = f"{document_type}_{timestamp}"
        # Build hierarchical output path: documents/{customer_code}/{order_code}/{doc_type}/
        _safe = lambda s: str(s or 'unknown').replace('/', '_').replace('\\', '_')
        customer_code = _safe(context.get('customer_code'))
        order_code    = _safe(context.get('order_code'))
        docs_dir   = os.path.join(
            current_app.config['DOCUMENTS_FOLDER'],
            customer_code, order_code, document_type
        )
        os.makedirs(docs_dir, exist_ok=True)

        template_file_path = self._get_template_file_path(template)
        output_ext         = document_format.lower()

        # ---- DOCX-template path (docxtpl) --------------------------------
        if DocxTemplateEngine.is_docx_template(template.template_file):
            if output_ext == 'pdf':
                # Render to DOCX first, then attempt PDF conversion
                docx_path = os.path.join(docs_dir, f"{doc_name}.docx")
                DocxTemplateEngine.render_to_file(template_file_path, context, docx_path)
                pdf_path  = os.path.join(docs_dir, f"{doc_name}.pdf")
                with open(docx_path, 'rb') as fh:
                    docx_bytes = _BytesIO(fh.read())
                if TemplateEngine.generate_pdf_from_docx(docx_bytes, pdf_path):
                    os.remove(docx_path)
                    file_path  = pdf_path
                else:
                    # PDF conversion failed → keep DOCX and fix extension
                    logger.warning("PDF conversion failed – keeping DOCX output")
                    file_path  = docx_path
                    output_ext = 'docx'
            else:
                file_path = os.path.join(docs_dir, f"{doc_name}.docx")
                DocxTemplateEngine.render_to_file(template_file_path, context, file_path)
                output_ext = 'docx'

        # ---- Legacy text-substitution path --------------------------------
        else:
            rendered_content = TemplateEngine.render_template(
                template.template_content or '', context
            )
            if output_ext == 'docx':
                file_path = os.path.join(docs_dir, f"{doc_name}.docx")
                buf = TemplateEngine.create_docx_document(
                    rendered_content, f"{document_type.title()} Document"
                )
                with open(file_path, 'wb') as fh:
                    fh.write(buf.getvalue())
            else:
                file_path = os.path.join(docs_dir, f"{doc_name}.pdf")
                buf = TemplateEngine.create_docx_document(
                    rendered_content, f"{document_type.title()} Document"
                )
                if not TemplateEngine.generate_pdf_from_docx(buf, file_path):
                    TemplateEngine.fallback_pdf_generation(rendered_content, file_path)

        file_size = os.path.getsize(file_path)

        def _sanitize(v):
            """Recursively convert context values to JSON-safe types."""
            if isinstance(v, dict):
                return {k2: _sanitize(v2) for k2, v2 in v.items()}
            if isinstance(v, list):
                return [_sanitize(i) for i in v]
            if isinstance(v, (str, int, float, bool)) or v is None:
                return v
            return ''   # InlineImage and any other non-serializable object

        document = self.repo.create(
            company_id          = company_id,
            order_id            = order_id,
            template_id         = template.id,
            quotation_id        = quotation_id,
            contract_id         = contract_id,
            handover_record_id  = handover_record_id,
            payment_report_id   = payment_report_id,
            document_name       = doc_name,
            document_type       = document_type,
            document_format     = output_ext,
            file_path           = file_path,
            file_size           = file_size,
            variables_used      = _sanitize(context),
        )
        logger.info(f"Document generated: {os.path.basename(file_path)}")
        return document

    # ------------------------------------------------------------------
    # Public generators
    # ------------------------------------------------------------------

    def generate_quotation_document(self, quotation_id, order_id, company_id, format='docx'):
        """Generate quotation document"""
        from app.repositories.repository import QuotationRepository, OrderRepository, CustomerRepository

        quotation = QuotationRepository().get_by_id(quotation_id)
        order     = OrderRepository().get_by_id(order_id)
        customer  = CustomerRepository().get_by_id(order.customer_id)

        if not all([quotation, order, customer]):
            raise ValueError("Quotation, Order, or Customer not found")

        template = self.template_repo.get_default_for_type(company_id, 'quotation')
        if not template:
            raise ValueError("No quotation template found for company")

        company = self._get_company(company_id)
        context = DocumentVariableCollector.collect_quotation_variables(
            quotation, customer, order, company=company
        )

        return self._save_document(
            company_id   = company_id,
            order_id     = order_id,
            quotation_id = quotation_id,
            template     = template,
            document_type   = 'quotation',
            document_format = format,
            context         = context,
        )

    def generate_contract_document(self, contract_id, order_id, company_id,
                                   quotation_id=None, format='docx'):
        """Generate contract document"""
        from app.repositories.repository import (
            ContractRepository, OrderRepository, CustomerRepository, QuotationRepository
        )

        contract  = ContractRepository().get_by_id(contract_id)
        order     = OrderRepository().get_by_id(order_id)
        customer  = CustomerRepository().get_by_id(order.customer_id)
        quotation = QuotationRepository().get_by_id(quotation_id) if quotation_id else None

        if not all([contract, order, customer]):
            raise ValueError("Contract, Order, or Customer not found")

        template = self.template_repo.get_default_for_type(company_id, 'contract')
        if not template:
            raise ValueError("No contract template found for company")

        company = self._get_company(company_id)
        context = DocumentVariableCollector.collect_contract_variables(
            contract, quotation, customer, order, company=company
        )

        return self._save_document(
            company_id  = company_id,
            order_id    = order_id,
            contract_id = contract_id,
            template    = template,
            document_type   = 'contract',
            document_format = format,
            context         = context,
        )

    def generate_delivery_document(self, delivery_report_id, order_id, company_id, format='docx'):
        """Generate handover / delivery record document"""
        from app.repositories.repository import (
            HandoverRecordRepository, OrderRepository, CustomerRepository
        )

        delivery_report = HandoverRecordRepository().get_by_id(delivery_report_id)
        order           = OrderRepository().get_by_id(order_id)
        customer        = CustomerRepository().get_by_id(order.customer_id)

        if not all([delivery_report, order, customer]):
            raise ValueError("Delivery Report, Order, or Customer not found")

        template = self.template_repo.get_default_for_type(company_id, 'delivery')
        if not template:
            template = self.template_repo.get_default_for_type(company_id, 'handover')
        if not template:
            raise ValueError("No delivery template found for company")

        company = self._get_company(company_id)
        context = DocumentVariableCollector.collect_delivery_variables(
            delivery_report, customer, order, company=company
        )

        return self._save_document(
            company_id         = company_id,
            order_id           = order_id,
            handover_record_id = delivery_report_id,
            template           = template,
            document_type      = 'delivery',
            document_format    = format,
            context            = context,
        )

    def generate_payment_document(self, payment_report_id, order_id, company_id, format='docx'):
        """Generate payment report document"""
        from app.repositories.repository import (
            PaymentReportRepository, OrderRepository, CustomerRepository
        )

        payment_report = PaymentReportRepository().get_by_id(payment_report_id)
        order          = OrderRepository().get_by_id(order_id)
        customer       = CustomerRepository().get_by_id(order.customer_id)

        if not all([payment_report, order, customer]):
            raise ValueError("Payment Report, Order, or Customer not found")

        doc_type = 'payment_' + payment_report.payment_type
        template = self.template_repo.get_default_for_type(company_id, doc_type)
        if not template:
            template = self.template_repo.get_default_for_type(company_id, 'payment')
        if not template:
            raise ValueError("No payment template found for company")

        company = self._get_company(company_id)

        # Look up active contract for this order to reference in payment doc
        _contract = None
        if order and hasattr(order, 'contracts'):
            _active = [c for c in (order.contracts or []) if getattr(c, 'is_active', False) and not getattr(c, 'is_canceled', False)]
            if _active:
                _contract = _active[0]

        context = DocumentVariableCollector.collect_payment_variables(
            payment_report, customer, order, company=company, contract=_contract
        )

        return self._save_document(
            company_id        = company_id,
            order_id          = order_id,
            payment_report_id = payment_report_id,
            template          = template,
            document_type     = 'payment',
            document_format   = format,
            context           = context,
        )

    def generate_payment_request_document(self, order_id, company_id, format='docx'):
        """Generate a payment request document (Đề nghị thanh toán) for an order"""
        from app.repositories.repository import OrderRepository, CustomerRepository, PaymentReportRepository
        
        order = OrderRepository().get_by_id(order_id)
        customer = CustomerRepository().get_by_id(order.customer_id)
        
        if not all([order, customer]):
            raise ValueError("Order or Customer not found")
            
        template = self.template_repo.get_default_for_type(company_id, 'payment_request')
        if not template:
            raise ValueError("No payment request template found for company. Please upload one in Document Templates.")
            
        company = self._get_company(company_id)
        
        _contract = None
        if order and hasattr(order, 'contracts'):
            _active = [c for c in (order.contracts or []) if getattr(c, 'is_active', False) and not getattr(c, 'is_canceled', False)]
            if _active:
                _contract = _active[0]
                
        # Get confirmed advance payments
        from app.models.models import PaymentReport
        from app.config.database import db
        advance_payments = db.session.query(PaymentReport).filter(
            PaymentReport.order_id == order_id,
            PaymentReport.payment_type == 'advance',
            PaymentReport.is_confirmed == True,
            PaymentReport.is_canceled == False
        ).all()
        
        total_advance = sum(float(p.amount or 0) for p in advance_payments)
        contract_value = float(_contract.contract_value) if _contract else 0
        remaining_amount = contract_value - total_advance
        
        context = DocumentVariableCollector.collect_payment_request_variables(
            order, customer, company=company, contract=_contract, 
            advance_payments=advance_payments, remaining_amount=remaining_amount
        )
        
        return self._save_document(
            company_id        = company_id,
            order_id          = order_id,
            template          = template,
            document_type     = 'payment_request',
            document_format   = format,
            context           = context,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_document(self, document_id):
        """Get document"""
        return self.repo.get_by_id(document_id)

    def list_documents_for_order(self, order_id):
        """List documents for order"""
        return self.repo.get_for_order(order_id)


# ── Material Service ───────────────────────────────────────────────────

class MaterialService:
    """Business logic for the Material management module."""

    def __init__(self):
        self.repo          = MaterialRepository()
        self.cat_repo      = MaterialCategoryRepository()
        self.unit_repo     = MaterialUnitRepository()
        self.stock_repo    = MaterialStockRepository()
        self.store_repo    = StoreRepository()
        self.supplier_repo = SupplierRepository()

    # ── Units ────────────────────────────────────────────────

    def list_units(self, company_id, active_only=True):
        return self.unit_repo.get_for_company(company_id, active_only=active_only)

    # ── Suppliers (thin proxy — SupplierService is standalone) ──

    def list_suppliers(self, company_id, active_only=True):
        return self.supplier_repo.get_for_company(company_id, active_only=active_only)

    def create_unit(self, company_id, name, abbreviation=None, description=None):
        if not name:
            raise ValueError('Tên đơn vị không được để trống')
        if self.unit_repo.get_by_name(company_id, name):
            raise ValueError(f'Đơn vị “{name}” đã tồn tại')
        return self.unit_repo.create(
            company_id=company_id, name=name,
            abbreviation=abbreviation or None,
            description=description or None,
        )

    def update_unit(self, unit_id, company_id, **kwargs):
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit or str(unit.company_id) != str(company_id):
            raise ValueError('Đơn vị không tìm thấy')
        new_name = kwargs.get('name')
        if new_name and new_name != unit.name:
            existing = self.unit_repo.get_by_name(company_id, new_name)
            if existing and str(existing.id) != str(unit_id):
                raise ValueError(f'Đơn vị “{new_name}” đã tồn tại')
        for k, v in kwargs.items():
            setattr(unit, k, v)
        db.session.commit()
        return unit

    def delete_unit(self, unit_id, company_id):
        """Soft-delete: set is_active=False. Cannot delete if materials use it."""
        unit = self.unit_repo.get_by_id(unit_id)
        if not unit or str(unit.company_id) != str(company_id):
            raise ValueError('Đơn vị không tìm thấy')
        if unit.materials:
            raise ValueError('Không thể xóa đơn vị đang được sử dụng bởi NVL')
        unit.is_active = False
        db.session.commit()

    # ── Categories ────────────────────────────────────────────

    def list_categories(self, company_id, active_only=True):
        return self.cat_repo.get_for_company(company_id, active_only=active_only)

    def create_category(self, company_id, name, description=None, sort_order=0):
        if not name:
            raise ValueError('Tên danh mục không được để trống')
        if self.cat_repo.get_by_name(company_id, name):
            raise ValueError(f'Danh mục “{name}” đã tồn tại')
        return self.cat_repo.create(
            company_id=company_id, name=name,
            description=description or None,
            sort_order=sort_order,
        )

    def update_category(self, cat_id, company_id, **kwargs):
        cat = self.cat_repo.get_by_id(cat_id)
        if not cat or str(cat.company_id) != str(company_id):
            raise ValueError('Danh mục không tìm thấy')
        new_name = kwargs.get('name')
        if new_name and new_name != cat.name:
            existing = self.cat_repo.get_by_name(company_id, new_name)
            if existing and str(existing.id) != str(cat_id):
                raise ValueError(f'Danh mục “{new_name}” đã tồn tại')
        for k, v in kwargs.items():
            setattr(cat, k, v)
        db.session.commit()
        return cat

    def delete_category(self, cat_id, company_id):
        """Soft-delete. Cannot delete if materials are in this category."""
        cat = self.cat_repo.get_by_id(cat_id)
        if not cat or str(cat.company_id) != str(company_id):
            raise ValueError('Danh mục không tìm thấy')
        if cat.materials:
            raise ValueError('Không thể xóa danh mục đang có NVL')
        cat.is_active = False
        db.session.commit()

    # ── Materials ──────────────────────────────────────────────

    def list_materials(self, company_id, category_id=None, search=None, active_only=True):
        return self.repo.get_for_company(
            company_id, category_id=category_id, search=search, active_only=active_only
        )

    def get_material(self, material_id, company_id=None):
        mat = self.repo.get_by_id(material_id)
        if mat and company_id and str(mat.company_id) != str(company_id):
            return None
        return mat

    def create_material(self, company_id, material_code, name, **kwargs):
        if not material_code or not name:
            raise ValueError('Mã NVL và tên không được để trống')
        if self.repo.get_by_code(company_id, material_code):
            raise ValueError(f'Mã NVL “{material_code}” đã tồn tại')
        mat = self.repo.create(
            company_id=company_id,
            material_code=material_code,
            name=name,
            **kwargs,
        )
        # Auto-create company warehouse stock entry (store_id=None)
        self.stock_repo.get_or_create_entry(mat.id, company_id, store_id=None)
        logger.info(f'Material created: {material_code} for company {company_id}')
        return mat

    def update_material(self, material_id, company_id, **kwargs):
        mat = self.repo.get_by_id(material_id)
        if not mat or str(mat.company_id) != str(company_id):
            raise ValueError('NVL không tìm thấy')
        new_code = kwargs.get('material_code')
        if new_code and new_code != mat.material_code:
            existing = self.repo.get_by_code(company_id, new_code)
            if existing and str(existing.id) != str(material_id):
                raise ValueError(f'Mã NVL “{new_code}” đã tồn tại')
        for k, v in kwargs.items():
            setattr(mat, k, v)
        db.session.commit()
        logger.info(f'Material updated: {mat.material_code}')
        return mat

    def deactivate_material(self, material_id, company_id):
        mat = self.repo.get_by_id(material_id)
        if not mat or str(mat.company_id) != str(company_id):
            raise ValueError('NVL không tìm thấy')
        mat.is_active = False
        db.session.commit()
        logger.info(f'Material deactivated: {mat.material_code}')

    # ── Stock management ────────────────────────────────────────

    def get_stock_for_material(self, material_id):
        """Return all stock entries enriched with store name."""
        entries = self.stock_repo.get_for_material(material_id)
        result = []
        for e in entries:
            store_name = 'Kho công ty' if e.store_id is None else (
                self.store_repo.get_by_id(e.store_id).name
                if self.store_repo.get_by_id(e.store_id) else str(e.store_id)
            )
            result.append({'entry': e, 'store_name': store_name})
        return result

    def update_stock(self, material_id, company_id, store_id, quantity):
        """Update or create stock quantity for a material+location."""
        mat = self.repo.get_by_id(material_id)
        if not mat or str(mat.company_id) != str(company_id):
            raise ValueError('NVL không tìm thấy')
        if quantity < 0:
            raise ValueError('Số lượng không thể âm')
        return self.stock_repo.upsert_quantity(material_id, company_id, store_id, quantity)

    def ensure_stock_entries_for_stores(self, material_id, company_id):
        """Ensure a stock entry exists for company warehouse + every active store."""
        stores = self.store_repo.get_stores_for_company(company_id)
        self.stock_repo.get_or_create_entry(material_id, company_id, store_id=None)
        for store in stores:
            self.stock_repo.get_or_create_entry(material_id, company_id, store_id=store.id)


class SupplierService:
    """Business logic for managing Suppliers / Nhà cung cấp."""

    def __init__(self):
        self.repo = SupplierRepository()

    def list_suppliers(self, company_id, active_only=True):
        return self.repo.get_for_company(company_id, active_only=active_only)

    def get_supplier(self, supplier_id, company_id=None):
        s = self.repo.get_by_id(supplier_id)
        if s and company_id and str(s.company_id) != str(company_id):
            return None
        return s

    def create_supplier(self, company_id, name, contact_person=None, phone=None,
                        email=None, address=None, tax_code=None,
                        payment_terms='COD', lead_time_days=0, rating=0, notes=None):
        if not name:
            raise ValueError('Tên nhà cung cấp không được để trống')
        supplier_code = self.repo.get_next_code(company_id)
        return self.repo.create(
            company_id=company_id,
            supplier_code=supplier_code,
            name=name,
            contact_person=contact_person or None,
            phone=phone or None,
            email=email or None,
            address=address or None,
            tax_code=tax_code or None,
            payment_terms=payment_terms or 'COD',
            lead_time_days=int(lead_time_days or 0),
            rating=int(rating or 0),
            notes=notes or None,
        )

    def update_supplier(self, supplier_id, company_id, **kwargs):
        s = self.repo.get_by_id(supplier_id)
        if not s or str(s.company_id) != str(company_id):
            raise ValueError('Nhà cung cấp không tìm thấy')
        for k, v in kwargs.items():
            setattr(s, k, v)
        db.session.commit()
        logger.info(f'Supplier updated: {s.supplier_code}')
        return s

    def delete_supplier(self, supplier_id, company_id):
        """Soft-delete. Cannot delete if materials reference this supplier."""
        s = self.repo.get_by_id(supplier_id)
        if not s or str(s.company_id) != str(company_id):
            raise ValueError('Nhà cung cấp không tìm thấy')
        if s.materials:
            raise ValueError('Không thể xóa nhà cung cấp đang được sử dụng bởi NVL')
        s.is_active = False
        db.session.commit()
        logger.info(f'Supplier deactivated: {s.supplier_code}')


# ============================================================================
# Feature 2 — Production Planning
# ============================================================================

def _product_key(name):
    return (name or '').strip().lower()


class ProductionPlanService:
    """Kế hoạch sản xuất: tạo từ hợp đồng, gợi ý vật tư từ định mức, cấp phát
    (trừ kho), lưu định mức, cảnh báo tồn thấp. Xem AUDIT/feature2-*.md."""

    def _gen_plan_number(self, company_id):
        from app.models.models import ProductionPlan
        n = ProductionPlan.query.filter_by(company_id=company_id).count() + 1
        return f"KHSX-{n:05d}"

    def get_plan_for_order(self, order_id):
        from app.models.models import ProductionPlan
        return ProductionPlan.query.filter_by(order_id=order_id).first()

    def create_from_contract(self, contract):
        """Idempotent: tạo 1 ProductionPlan (draft) cho order của hợp đồng, copy
        item hợp đồng, và gợi ý ProductionMaterialLine từ MaterialNorm khớp tên."""
        from decimal import Decimal
        from app.models.models import (ProductionPlan, ProductionPlanItem,
                                        ProductionMaterialLine, MaterialNorm)
        from app.repositories.repository import OrderRepository
        order = OrderRepository().get_by_id(contract.order_id)
        if order is None:
            return None
        existing = ProductionPlan.query.filter_by(order_id=contract.order_id).first()
        if existing:
            return existing
        plan = ProductionPlan(
            order_id=contract.order_id, contract_id=contract.id, company_id=order.company_id,
            plan_number=self._gen_plan_number(order.company_id),
            status=ProductionPlan.STATUS_DRAFT)
        db.session.add(plan)
        db.session.flush()
        for it in (contract.items or []):
            qty = Decimal(str(it.get('quantity', 0) or 0))
            pi = ProductionPlanItem(plan_id=plan.id, source_name=it.get('name', ''),
                                    quantity=qty, unit=it.get('unit', ''))
            db.session.add(pi)
            db.session.flush()
            norms = MaterialNorm.query.filter_by(
                company_id=order.company_id, product_key=_product_key(pi.source_name)).all()
            for nrm in norms:
                db.session.add(ProductionMaterialLine(
                    plan_id=plan.id, plan_item_id=pi.id, material_id=nrm.material_id,
                    quantity_required=Decimal(str(nrm.quantity_per_unit or 0)) * qty,
                    unit=nrm.unit))
        db.session.commit()
        return plan

    def _stock_for(self, material_id, store_id):
        from app.models.models import MaterialStock
        st = MaterialStock.query.filter_by(material_id=material_id, store_id=store_id).first()
        if st is None:
            st = MaterialStock.query.filter_by(material_id=material_id, store_id=None).first()
        return st

    def issue_materials(self, plan):
        """Cấp phát: kiểm tồn trước; nếu thiếu → trả danh sách shortage, KHÔNG trừ.
        Nếu đủ → trừ MaterialStock, set quantity_issued, status=in_progress."""
        from decimal import Decimal
        order = plan.order
        needs = []
        for line in plan.material_lines:
            need = Decimal(str(line.quantity_required or 0)) - Decimal(str(line.quantity_issued or 0))
            if need > 0:
                needs.append((line, need))
        shortages = []
        for line, need in needs:
            st = self._stock_for(line.material_id, order.store_id)
            avail = Decimal(str(st.current_quantity)) if st else Decimal('0')
            if avail < need:
                shortages.append({'material_id': str(line.material_id),
                                  'need': float(need), 'available': float(avail)})
        if shortages:
            return shortages
        for line, need in needs:
            st = self._stock_for(line.material_id, order.store_id)
            st.current_quantity = Decimal(str(st.current_quantity)) - need
            line.quantity_issued = Decimal(str(line.quantity_required or 0))
        plan.status = plan.STATUS_IN_PROGRESS
        db.session.commit()
        return []

    def save_as_norm(self, plan_item):
        """Lưu định mức từ các material line của 1 item để tái sử dụng (upsert)."""
        from decimal import Decimal
        from app.models.models import MaterialNorm
        company_id = plan_item.plan.company_id
        key = _product_key(plan_item.source_name)
        qty = Decimal(str(plan_item.quantity or 0)) or Decimal('1')
        for line in plan_item.material_lines:
            per_unit = (Decimal(str(line.quantity_required or 0)) / qty) if qty else Decimal('0')
            norm = MaterialNorm.query.filter_by(
                company_id=company_id, product_key=key, material_id=line.material_id).first()
            if norm is None:
                norm = MaterialNorm(company_id=company_id, product_key=key,
                                    material_id=line.material_id, unit=line.unit)
                db.session.add(norm)
            norm.quantity_per_unit = per_unit
            norm.unit = line.unit
        db.session.commit()

    def low_stock_materials(self, company_id):
        from app.models.models import Material
        mats = Material.query.filter_by(company_id=company_id, is_active=True).all()
        return [m for m in mats if m.is_low_stock]

    def transition(self, plan, action):
        """Move the plan through its lifecycle (validates the transition)."""
        tr = plan.TRANSITIONS.get(action)
        if not tr or plan.status not in tr[0]:
            raise ValueError(f'Không thể "{action}" khi kế hoạch đang ở trạng thái "{plan.status}"')
        plan.status = tr[1]
        if action in ('start', 'validate', 'finish'):
            plan.is_delayed = plan.is_delayed if action == 'start' else False
        db.session.commit()
        return plan

    def set_delay(self, plan, delayed, reason=None):
        plan.is_delayed = bool(delayed)
        plan.delay_reason = (reason or None) if delayed else None
        db.session.commit()
        return plan
