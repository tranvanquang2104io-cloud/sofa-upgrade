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
    DeliveryReportRepository, PaymentReportRepository, DocumentRepository,
    DocumentTemplateRepository, LifecycleStatusRepository
)
from app.utils.template_engine import TemplateEngine, DocumentVariableCollector
from app.models import Document, Order, Quotation, Contract
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


class UserService:
    """Service for user management"""
    
    def __init__(self):
        self.repo = UserRepository()
    
    def create_user(self, company_id, username, email, password, full_name, role='user'):
        """Create new user"""
        existing = self.repo.get_by_username(username, company_id)
        if existing:
            raise ValueError(f"User with username {username} already exists")
        
        user = self.repo.create(
            company_id=company_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role
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
    
    def get_user(self, user_id):
        """Get user by ID"""
        return self.repo.get_by_id(user_id)
    
    def list_users_for_company(self, company_id):
        """List all users for company"""
        return self.repo.get_users_for_company(company_id)


class CustomerService:
    """Service for customer management"""
    
    def __init__(self):
        self.repo = CustomerRepository()
    
    def create_customer(self, store_id, customer_code, name, phone=None, email=None, 
                       address=None, city=None, postal_code=None, country=None, notes=None):
        """Create new customer"""
        existing = self.repo.get_by_store_and_code(store_id, customer_code)
        if existing:
            raise ValueError(f"Customer with code {customer_code} already exists in store")
        
        customer = self.repo.create(
            store_id=store_id,
            customer_code=customer_code,
            name=name,
            phone=phone,
            email=email,
            address=address,
            city=city,
            postal_code=postal_code,
            country=country,
            notes=notes
        )
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


class OrderService:
    """Service for order management"""
    
    def __init__(self):
        self.repo = OrderRepository()
        self.lifecycle_repo = LifecycleStatusRepository()
    
    def create_order(self, store_id, company_id, customer_id, order_code, title, 
                    description=None, notes=None):
        """Create new order"""
        existing = self.repo.get_by_store_and_code(store_id, order_code)
        if existing:
            raise ValueError(f"Order with code {order_code} already exists in store")
        
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
        from app.repositories.repository import DeliveryReportRepository, PaymentReportRepository
        
        order = self.get_order(order_id, company_id)
        if not order:
            return None
        
        return {
            'order': order,
            'quotations': QuotationRepository().get_for_order(order_id),
            'contracts': ContractRepository().get_for_order(order_id),
            'delivery_reports': DeliveryReportRepository().get_for_order(order_id),
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
                        total_amount, validity_days=30, notes=None):
        """Create quotation"""
        existing = self.repo.get_by_number(quotation_number)
        if existing:
            raise ValueError(f"Quotation {quotation_number} already exists")
        
        quotation = self.repo.create(
            order_id=order_id,
            quotation_number=quotation_number,
            quotation_date=quotation_date,
            items=items,
            total_amount=total_amount,
            validity_days=validity_days,
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
    
    def update_quotation(self, quotation_id, items=None, total_amount=None, validity_days=None, notes=None):
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
            # Update order totals when quotation amount changes
            self.order_service.update_order_totals(quotation.order_id, total_amount=total_amount)
        if validity_days is not None:
            quotation.validity_days = validity_days
        if notes is not None:
            quotation.notes = notes
        
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
        existing = self.repo.get_by_number(contract_number)
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
        
        # Create new contract
        contract = self.repo.create(
            order_id=order_id,
            quotation_id=quotation_id,
            contract_number=contract_number,
            contract_date=contract_date,
            contract_value=contract_value,
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
            
            logger.info(f"Contract {contract.contract_number} signed and lifecycle updated")
            return contract
            
        except Exception as e:
            logger.error(f"Error marking contract as signed: {str(e)}")
            db.session.rollback()
            raise


class DeliveryReportService:
    """Service for delivery report management"""
    
    def __init__(self):
        self.repo = DeliveryReportRepository()
    
    def create_delivery_report(self, order_id, report_number, report_date, delivery_date,
                              work_description=None, materials_used=None, notes=None):
        """Create delivery report"""
        existing = self.repo.get_by_number(report_number)
        if existing:
            raise ValueError(f"Delivery report {report_number} already exists")
        
        # Note: Delivery reports can have multiple (before/after), so we don't deactivate previous
        # But we ensure only one is confirmed at a time
        
        report = self.repo.create(
            order_id=order_id,
            report_number=report_number,
            report_date=report_date,
            delivery_date=delivery_date,
            work_description=work_description,
            materials_used=materials_used,
            notes=notes
        )
        
        logger.info(f"Delivery report created: {report_number}")
        return report
    
    def get_delivery_report(self, report_id):
        """Get delivery report"""
        return self.repo.get_by_id(report_id)
    
    def mark_confirmed(self, report_id, order_id):
        """Mark delivery as confirmed and update lifecycle atomically"""
        try:
            report = self.repo.get_by_id(report_id)
            if not report:
                raise ValueError(f"Delivery report {report_id} not found")
            
            if report.is_confirmed:
                logger.warning(f"Delivery {report_id} already confirmed at {report.confirmed_date}")
                return report
            
            # Update delivery report
            report.is_confirmed = True
            report.confirmed_date = datetime.utcnow()
            
            # Update lifecycle - mark delivery as confirmed
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            lifecycle.delivery_confirmed = True
            lifecycle.delivery_confirmed_at = datetime.utcnow()
            
            # Make both updates atomic - add both to session before committing
            db.session.add(report)
            db.session.add(lifecycle)
            db.session.commit()
            
            logger.info(f"Delivery {report.report_number} confirmed and lifecycle updated")
            return report
            
        except Exception as e:
            logger.error(f"Error confirming delivery: {str(e)}")
            db.session.rollback()
            raise


class PaymentReportService:
    """Service for payment report management"""
    
    def __init__(self):
        self.repo = PaymentReportRepository()
    
    def create_payment_report(self, order_id, report_number, payment_type, report_date, 
                             payment_date, amount, payment_method=None, 
                             transaction_reference=None, notes=None):
        """Create payment report"""
        existing = self.repo.get_by_number(report_number)
        if existing:
            raise ValueError(f"Payment report {report_number} already exists")
        
        report = self.repo.create(
            order_id=order_id,
            report_number=report_number,
            payment_type=payment_type,
            report_date=report_date,
            payment_date=payment_date,
            amount=amount,
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


class DocumentService:
    """Service for document management"""
    
    def __init__(self):
        self.repo = DocumentRepository()
        self.template_repo = DocumentTemplateRepository()
    
    def generate_quotation_document(self, quotation_id, order_id, company_id, format='pdf'):
        """Generate quotation document"""
        from app.repositories.repository import QuotationRepository, OrderRepository, CustomerRepository
        
        quotation = QuotationRepository().get_by_id(quotation_id)
        order = OrderRepository().get_by_id(order_id)
        customer = CustomerRepository().get_by_id(order.customer_id)
        
        if not all([quotation, order, customer]):
            raise ValueError("Quotation, Order, or Customer not found")
        
        # Get template
        template = self.template_repo.get_default_for_type(company_id, 'quotation')
        if not template:
            raise ValueError("No quotation template found for company")
        
        # Collect variables
        variables = DocumentVariableCollector.collect_quotation_variables(quotation, customer, order)
        
        # Render template
        rendered_content = TemplateEngine.render_template(template.template_content, variables)
        
        # Generate document
        return self._save_document(
            company_id=company_id,
            order_id=order_id,
            quotation_id=quotation_id,
            template_id=template.id,
            document_type='quotation',
            document_format=format,
            rendered_content=rendered_content,
            variables_used=variables
        )
    
    def generate_contract_document(self, contract_id, order_id, company_id, quotation_id=None, format='pdf'):
        """Generate contract document"""
        from app.repositories.repository import (
            ContractRepository, OrderRepository, CustomerRepository, QuotationRepository
        )
        
        contract = ContractRepository().get_by_id(contract_id)
        order = OrderRepository().get_by_id(order_id)
        customer = CustomerRepository().get_by_id(order.customer_id)
        quotation = QuotationRepository().get_by_id(quotation_id) if quotation_id else None
        
        if not all([contract, order, customer]):
            raise ValueError("Contract, Order, or Customer not found")
        
        # Get template
        template = self.template_repo.get_default_for_type(company_id, 'contract')
        if not template:
            raise ValueError("No contract template found for company")
        
        # Collect variables
        variables = DocumentVariableCollector.collect_contract_variables(
            contract, quotation, customer, order
        )
        
        # Render template
        rendered_content = TemplateEngine.render_template(template.template_content, variables)
        
        # Generate document
        return self._save_document(
            company_id=company_id,
            order_id=order_id,
            contract_id=contract_id,
            template_id=template.id,
            document_type='contract',
            document_format=format,
            rendered_content=rendered_content,
            variables_used=variables
        )
    
    def generate_delivery_document(self, delivery_report_id, order_id, company_id, format='pdf'):
        """Generate delivery document"""
        from app.repositories.repository import (
            DeliveryReportRepository, OrderRepository, CustomerRepository
        )
        
        delivery_report = DeliveryReportRepository().get_by_id(delivery_report_id)
        order = OrderRepository().get_by_id(order_id)
        customer = CustomerRepository().get_by_id(order.customer_id)
        
        if not all([delivery_report, order, customer]):
            raise ValueError("Delivery Report, Order, or Customer not found")
        
        # Get template
        template = self.template_repo.get_default_for_type(company_id, 'delivery')
        if not template:
            raise ValueError("No delivery template found for company")
        
        # Collect variables
        variables = DocumentVariableCollector.collect_delivery_variables(
            delivery_report, customer, order
        )
        
        # Render template
        rendered_content = TemplateEngine.render_template(template.template_content, variables)
        
        # Generate document
        return self._save_document(
            company_id=company_id,
            order_id=order_id,
            delivery_report_id=delivery_report_id,
            template_id=template.id,
            document_type='delivery',
            document_format=format,
            rendered_content=rendered_content,
            variables_used=variables
        )
    
    def generate_payment_document(self, payment_report_id, order_id, company_id, format='pdf'):
        """Generate payment document"""
        from app.repositories.repository import (
            PaymentReportRepository, OrderRepository, CustomerRepository
        )
        
        payment_report = PaymentReportRepository().get_by_id(payment_report_id)
        order = OrderRepository().get_by_id(order_id)
        customer = CustomerRepository().get_by_id(order.customer_id)
        
        if not all([payment_report, order, customer]):
            raise ValueError("Payment Report, Order, or Customer not found")
        
        # Get template
        doc_type = 'payment_' + payment_report.payment_type
        template = self.template_repo.get_default_for_type(company_id, doc_type)
        if not template:
            template = self.template_repo.get_default_for_type(company_id, 'payment')
        if not template:
            raise ValueError("No payment template found for company")
        
        # Collect variables
        variables = DocumentVariableCollector.collect_payment_variables(
            payment_report, customer, order
        )
        
        # Render template
        rendered_content = TemplateEngine.render_template(template.template_content, variables)
        
        # Generate document
        return self._save_document(
            company_id=company_id,
            order_id=order_id,
            payment_report_id=payment_report_id,
            template_id=template.id,
            document_type='payment',
            document_format=format,
            rendered_content=rendered_content,
            variables_used=variables
        )
    
    def _save_document(self, company_id, order_id, template_id, document_type, 
                      document_format, rendered_content, variables_used,
                      quotation_id=None, contract_id=None, delivery_report_id=None, payment_report_id=None):
        """Save generated document"""
        
        # Create filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_name = f"{document_type}_{timestamp}"
        
        if document_format.lower() == 'pdf':
            filename = f"{doc_name}.pdf"
        else:
            filename = f"{doc_name}.docx"
        
        # Ensure documents directory exists
        docs_dir = os.path.join(current_app.config['DOCUMENTS_FOLDER'])
        os.makedirs(docs_dir, exist_ok=True)
        
        file_path = os.path.join(docs_dir, filename)
        
        try:
            if document_format.lower() == 'docx':
                # Generate DOCX
                docx_bytes = TemplateEngine.create_docx_document(
                    rendered_content,
                    f"{document_type.title()} Document"
                )
                with open(file_path, 'wb') as f:
                    f.write(docx_bytes.getvalue())
            else:
                # Try to generate PDF
                docx_bytes = TemplateEngine.create_docx_document(
                    rendered_content,
                    f"{document_type.title()} Document"
                )
                
                # Try LibreOffice first
                if not TemplateEngine.generate_pdf_from_docx(docx_bytes, file_path):
                    # Fallback to reportlab
                    TemplateEngine.fallback_pdf_generation(rendered_content, file_path)
            
            # Get file size
            file_size = os.path.getsize(file_path)
            
            # Save document record
            document = self.repo.create(
                company_id=company_id,
                order_id=order_id,
                template_id=template_id,
                quotation_id=quotation_id,
                contract_id=contract_id,
                delivery_report_id=delivery_report_id,
                payment_report_id=payment_report_id,
                document_name=doc_name,
                document_type=document_type,
                document_format=document_format,
                file_path=file_path,
                file_size=file_size,
                variables_used=variables_used
            )
            
            logger.info(f"Document generated: {filename}")
            return document
            
        except Exception as e:
            logger.error(f"Error generating document: {str(e)}")
            raise
    
    def get_document(self, document_id):
        """Get document"""
        return self.repo.get_by_id(document_id)
    
    def list_documents_for_order(self, order_id):
        """List documents for order"""
        return self.repo.get_for_order(order_id)
