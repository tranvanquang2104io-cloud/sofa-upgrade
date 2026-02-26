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
    DocumentTemplateRepository, LifecycleStatusRepository
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
    
    def create_customer(self, company_id, store_id, customer_code, name, phone=None, email=None, 
                       address=None, city=None, postal_code=None, country=None, notes=None):
        """Create new customer"""
        existing = self.repo.get_by_store_and_code(store_id, customer_code)
        if existing:
            raise ValueError(f"Customer with code {customer_code} already exists in store")
        
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
                              product_condition=None, items=None, notes=None):
        """Create handover record"""
        existing = self.repo.get_by_number(report_number)
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
            customer_representative=customer_representative,
            company_representative=company_representative,
            product_condition=product_condition,
            items=items or [],
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
                             transaction_reference=None, notes=None):
        """Create payment report"""
        existing = self.repo.get_by_number(report_number)
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
            
            # Lifecycle does not revert - payment can be recreated after cancellation
            
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
        """Build absolute path to the template file."""
        templates_dir = current_app.config['TEMPLATES_FOLDER']
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
        docs_dir   = current_app.config['DOCUMENTS_FOLDER']
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
            variables_used      = {k: str(v) if not isinstance(v, (list, dict)) else v
                                   for k, v in context.items()},
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
        context = DocumentVariableCollector.collect_payment_variables(
            payment_report, customer, order, company=company
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

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_document(self, document_id):
        """Get document"""
        return self.repo.get_by_id(document_id)

    def list_documents_for_order(self, order_id):
        """List documents for order"""
        return self.repo.get_for_order(order_id)
