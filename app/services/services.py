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
from app.models import Contract
import logging

logger = logging.getLogger(__name__)

from app.services.workflow_service import (  # noqa: E402  (after logger by convention)
    ACTION_CONTRACT_CREATE,
    ACTION_CONTRACT_SIGN,
    ACTION_HANDOVER_CONFIRM,
    ACTION_HANDOVER_CREATE,
    ACTION_PAYMENT_ADVANCE,
    ACTION_PAYMENT_FINAL,
    ACTION_QUOTATION_APPROVE,
    WorkflowService,
)


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

        # Install the default workflow rules so the new tenant starts with the
        # standard order flow, editable from day one.
        try:
            WorkflowService.seed_defaults(company.id)
        except Exception as exc:  # never block company creation on this
            logger.warning("Could not seed workflow rules for %s: %s",
                           company_code, exc)

        # Same for the Vietnamese data-standardization defaults.
        try:
            from app.services.normalization_service import NormalizationService
            NormalizationService.seed_defaults(company.id)
        except Exception as exc:
            logger.warning("Could not seed normalization rules for %s: %s",
                           company_code, exc)

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
        # A new branch holds nothing, and has to be able to SAY it holds
        # nothing. Without a row per material, `_stock_for` finds nothing for
        # it — which used to fall through to the company warehouse and let the
        # new workshop issue fabric no document says was moved there. Zero rows
        # are the honest figure, and what makes removing that fallback safe.
        MaterialService().ensure_stock_entries_for_stores_of_company(company_id)
        return store
    
    
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
                    role='user', store_id=None, phone=None, position=None,
                    allowed_features=None):
        """Create new user"""
        from app.models.models import User
        existing = self.repo.get_by_username(username, company_id)
        if existing:
            raise ValueError(f"User with username {username} already exists")
        if not password:
            raise ValueError("Mật khẩu là bắt buộc")

        # Build the user WITH its password before insert — password_hash is NOT NULL,
        # so we must not flush/commit an incomplete row (the repo.create helper commits
        # immediately, which would fail on password_hash).
        user = User(
            company_id=company_id,
            username=username,
            email=email,
            full_name=full_name,
            role=role,
            store_id=store_id,
            phone=phone,
            position=position,
            allowed_features=list(allowed_features or []),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        logger.info(f"User created: {username} for company {company_id}")
        return user


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


    def list_users_for_company(self, company_id):
        """List all active users for company"""
        return self.repo.get_users_for_company(company_id)

    def list_users_for_store(self, store_id):
        """List all active users for a store"""
        return self.repo.get_users_for_store(store_id)

    def update_user(self, user_id, full_name=None, email=None, phone=None,
                    position=None, role=None, store_id=None, password=None,
                    allowed_features=None):
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
        if allowed_features is not None: user.allowed_features = list(allowed_features)
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
        """Get order - verify company AND store access.

        The list screens narrowed to `get_accessible_store_ids()`; this did
        not, so a store user holding an id from another branch could open that
        order and act on it. Checking here rather than at the ten call sites
        closes the class: a detail route added tomorrow is covered too.
        """
        order = self.repo.get_by_id(order_id)
        if not order or str(order.company_id) != str(company_id):
            return None
        if not user_may_access_store(order.store_id, company_id):
            return None
        return order
    
    def list_orders_for_customer(self, customer_id):
        """List orders for customer"""
        return self.repo.get_orders_for_customer(customer_id)
    
    
    def list_orders_for_company(self, company_id, page=1, per_page=20,
                                store_ids=None):
        """List orders for company, optionally narrowed to certain stores."""
        offset = (page - 1) * per_page
        return self.repo.get_orders_for_company(
            company_id, limit=per_page, offset=offset, store_ids=store_ids)
    
    def cancel_order(self, order_id, company_id, reason=""):
        """Cancel an order, with the reason, through one place.

        `OrderService` had no cancel method at all: the route set the flags
        itself. That matters less for tidiness than for where the DECISION
        lives — an order carries quotations, contracts, handovers and
        payments, and whatever is decided about that paperwork on
        cancellation has to be decided once. A route cannot be that place,
        because the next way to cancel an order (an API, a bulk action, the
        approval queue) will not pass through it.

        What this deliberately does NOT do: touch the child documents. The
        owner's rule for correcting a mistake is void-with-a-reason and
        re-create, one document at a time, each leaving its own trace — not a
        cascade that silently rewrites paperwork the customer has already
        been given. A cancelled order keeps its history visible, which is
        also what Luật Kế toán 2015 Đ.27 expects. If a cascade is wanted it
        is a business decision and belongs in the plan, not in this method.
        """
        order = self.get_order(order_id, company_id)
        if not order:
            raise ValueError('Đơn hàng không tồn tại hoặc không có quyền')

        if not order.can_cancel():
            raise ValueError('Đơn hàng này không huỷ được')

        reason = (reason or '').strip()
        if not reason:
            raise ValueError('Phải nhập lý do huỷ')

        from app.services.transitions import record as _history
        _history(order.company_id, 'order', order.id, 'order.cancel',
                 from_state='active', to_state='canceled', reason=reason)
        order.is_canceled = True
        order.canceled_at = datetime.utcnow()
        order.canceled_reason = reason
        db.session.commit()
        logger.info('Order %s canceled: %s', order.order_code, reason)
        return order

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
    
    
    def approve_quotation(self, quotation_id, order_id):
        """Mark quotation as approved"""
        quotation = self.repo.get_by_id(quotation_id)
        if not quotation:
            raise ValueError("Quotation not found")
        
        if not quotation.can_approve():
            raise ValueError("Quotation cannot be approved in its current state")

        # The company's own rules for this action. `quotation.approve` was
        # offered on the workflow settings grid, accepted rules, saved them and
        # showed them back — and nothing ever asked. An owner who set a control
        # was told they had one they did not have, and the absence of a refusal
        # is indistinguishable from a rule that was satisfied.
        WorkflowService.require(quotation.order, ACTION_QUOTATION_APPROVE)

        from app.services.transitions import record as _history
        _history(quotation.order.company_id, 'quotation', quotation.id,
                 'quotation.approve', from_state='draft', to_state='approved')
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

        # Put the order's lifecycle back, the same way cancelling a contract
        # does. This was missing, so cancelling the only quotation left the
        # order saying it HAD one — and an approved one — with nothing to show
        # for it. `quotation_approved` is what unlocks writing the contract,
        # so the order would go on offering a step it had lost the basis for.
        #
        # The same defect `cancel_contract` had, found by covering a route no
        # test had ever posted to.
        from app.models.models import Quotation as _Quotation
        other_active = db.session.query(_Quotation).filter(
            _Quotation.order_id == quotation.order_id,
            _Quotation.is_active == True,  # noqa: E712
            _Quotation.id != quotation.id,
        ).first()

        if not other_active:
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(
                quotation.order_id)
            lifecycle.quotation_created = False
            lifecycle.quotation_created_at = None
            # `quotation_approved` is deliberately NOT touched: `can_cancel()`
            # refuses an approved quotation, so this branch cannot be reached
            # with the approval flag set. Clearing it here would be a rule
            # written where nothing can execute it — the exact shape of defect
            # this refactor has been removing.
            db.session.add(lifecycle)

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

        # Same reason as contract.sign: the action is configurable on the
        # workflow settings screen but nothing consulted the rule. The shipped
        # default is OPTIONAL, i.e. advisory, so a default install is
        # unaffected - only an admin who deliberately makes it required sees a
        # change, which is what they asked for by making it required.
        WorkflowService.require(_order, ACTION_CONTRACT_CREATE)

        existing = self.repo.get_by_company_and_number(
            _order.company_id if _order else None, contract_number)
        if existing:
            raise ValueError(f"Contract {contract_number} already exists")
        
        # IMPORTANT: Single-active-contract constraint
        # Mark any existing active contracts as inactive
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
        
        # The contract is the later, binding agreement: it is what the order is
        # worth now. Only a quotation used to set this, so an order contracted
        # without one showed 0 ₫ on every list, and a renegotiated price showed
        # the quotation's figure instead of the one signed.
        order = OrderRepository().get_by_id(order_id)
        if order is not None:
            order.total_amount = contract_value

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

            # contract.sign is in ALL_ACTIONS and in DEFAULT_RULES, and the
            # workflow settings screen lets an admin change it - but nothing
            # ever consulted it, so the setting was decoration. Consulting it
            # here changes nothing on a default install: the shipped rule is
            # `contract_created`, which is satisfied by the contract existing.
            WorkflowService.require(contract.order, ACTION_CONTRACT_SIGN)
            
            if contract.is_signed:
                logger.warning(f"Contract {contract_id} already signed at {contract.signed_date}")
                return contract
            
            # Update contract
            from app.services.transitions import record as _history
            _history(contract.order.company_id, 'contract', contract.id,
                     'contract.sign', from_state='draft', to_state='signed')
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
        """Cancel a contract and put the order's lifecycle back.

        The route used to do this itself and never called this method, so the
        lifecycle rollback below ran only in tests. Cancelling the only
        contract through the UI left `contract_created` True for ever, and the
        order sat in a state the user had already undone with no way out but
        a contract they did not want.
        """
        try:
            contract = self.repo.get_by_id(contract_id)
            if not contract:
                raise ValueError(f"Contract {contract_id} not found")
            
            if not contract.can_cancel():
                raise ValueError("Contract cannot be canceled (already signed or canceled)")

            # The reason lived in the route, which is why moving the work had
            # to bring it along. A cancelled document with no reason is the
            # one people ask about six months later.
            reason = (reason or '').strip()
            if not reason:
                raise ValueError('Phải nhập lý do huỷ')
            
            # Update contract
            from app.services.transitions import record as _history
            _history(contract.order.company_id, 'contract', contract.id,
                     'contract.cancel',
                     from_state='signed' if contract.is_signed else 'draft',
                     to_state='canceled', reason=reason)
            contract.is_canceled = True
            contract.canceled_at = datetime.utcnow()
            contract.canceled_reason = reason
            contract.is_active = False
            
            # RECOMPUTED from the contracts that actually exist, not unpicked
            # flag by flag. Unpicking assumes you know everything that turned
            # the flag on; recomputing asks the data. Same choice, same
            # reason, as `_resync_payment_lifecycle`.
            lifecycle = LifecycleStatusRepository().get_or_create_for_order(order_id)
            
            other_active = db.session.query(Contract).filter(
                Contract.order_id == order_id,
                Contract.is_active == True,
                Contract.id != contract_id
            ).first()
            
            if not other_active:
                lifecycle.contract_created = False
                lifecycle.contract_created_at = None
                # A contract that could be cancelled was never signed, so this
                # is already False — set rather than assumed, because the two
                # flags are read independently by the screens.
                lifecycle.contract_signed = False
                lifecycle.contract_signed_at = None
            
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
        
        # Workflow sequencing is owned by WorkflowService (see
        # app/services/workflow_service.py). The default rule set reproduces
        # the requirement that used to be hardcoded here — an advance payment
        # before a handover — but a company can now relax or waive it.
        order = OrderRepository().get_by_id(order_id)
        if not order:
            raise ValueError("Order not found")
        WorkflowService.require(order, ACTION_HANDOVER_CREATE)
        
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

            # Same as `quotation.approve`: configurable and never checked.
            WorkflowService.require(record.order, ACTION_HANDOVER_CONFIRM)

            from app.services.transitions import record as _history
            _history(record.order.company_id, 'handover', record.id,
                     'handover.confirm', from_state='draft',
                     to_state='confirmed')

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


def plan_lock_reason(status):
    """Why this plan's material list is locked, and the way out — if there is one.

    The screen used to print one sentence for every locked state, telling the
    user to press "Từ chối (làm lại)". That button is not on the screen, and
    `reject` is only legal from `validating`; from `processing` the only moves
    are `complete` and `cancel`. So the message sent people looking for a
    control that does not exist and could not have worked — which is worse than
    saying nothing, because they spend the time believing the fault is theirs.

    Returns ``(message_key, action)``. ``action`` is the transition that
    unlocks editing, or None when nothing reopens it from here. Both are None
    for a draft, which is not locked.
    """
    from app.models.models import ProductionPlan as _Plan

    if status == _Plan.STATUS_DRAFT:
        return None, None

    if status == _Plan.STATUS_VALIDATING:
        # The one state the old message was actually right about.
        return ('Kế hoạch đang chờ nghiệm thu nên danh mục vật tư đã khóa. '
                'Dùng “Từ chối (làm lại)” để mở lại cho chỉnh sửa.'), 'reject'

    if status in (_Plan.STATUS_APPROVED, _Plan.STATUS_PROCESSING):
        return ('Kế hoạch đã chốt và đang sản xuất nên danh mục vật tư đã '
                'khóa — để số liệu cấp phát và giá vốn khớp với lệnh đã chốt. '
                'Từ trạng thái này chỉ có thể “Hoàn thành” hoặc “Hủy”.'), None

    return ('Kế hoạch đã qua giai đoạn sản xuất nên danh mục vật tư đã khóa.'), None


def user_may_access_store(store_id, company_id):
    """Whether the CURRENT user may act on something belonging to this store.

    Returns True outside a request — seeds, migrations and scripts have no
    session and are not acting on anyone's behalf.

    A company admin reaches every branch; a store user reaches their own.
    """
    try:
        from flask import has_request_context, session
        if not has_request_context() or 'user_id' not in session:
            return True
        from app.utils.auth_utils import get_accessible_store_ids
        allowed = get_accessible_store_ids(company_id)
    except Exception:
        # Never turn an access check into a 500; the company check above has
        # already run, and the routes still have their own guards.
        return True
    return store_id in allowed or str(store_id) in {str(s) for s in allowed}


def line_source_store(line, plan):
    """The branch whose stock a material line is drawn from.

    A line may name a warehouse of its own — the fabric store, when the frames
    come from the timber yard. Without one it falls back to the plan's
    production site, which is what every line did before the column existed.

    Returns a STORE id, not a warehouse id, because `MaterialStock` is keyed by
    (material, store). Two warehouses inside one branch therefore share a stock
    row and cannot be told apart; drawing from another BRANCH's warehouse —
    the case the owner described — works. Re-keying stock by warehouse is a
    data migration of its own, recorded in REFACTOR-2026Q3.md rather than
    smuggled in here.
    """
    warehouse_id = getattr(line, 'warehouse_id', None)
    if warehouse_id is None:
        return production_site_of(plan)

    from app.models.models import Warehouse
    warehouse = Warehouse.query.get(warehouse_id)
    if warehouse is None or str(warehouse.company_id) != str(plan.company_id):
        # Refuse rather than substitute, exactly as receiving does: quietly
        # falling back to the production site would take material from a place
        # nobody named.
        raise ValueError('Kho không thuộc công ty này')
    return warehouse.store_id


def production_site_of(plan):
    """The branch a plan is built at.

    Its own `production_store_id` when set, otherwise the branch on the order.
    The fallback is not laziness: until somebody separates the two, they ARE
    the same place, and defaulting to the order's branch reproduces exactly
    what the code did before the column existed. What changes is that the
    assumption now has a name and somewhere to be overridden.
    """
    site = getattr(plan, 'production_store_id', None)
    if site is not None:
        return site
    order = getattr(plan, 'order', None)
    return getattr(order, 'store_id', None)


def order_commitment(order):
    """What this order was agreed ON: a signed contract, or a confirmed ĐĐH.

    The handover and payment screens pre-filled their fees from
    `active_contract`, which is None for every framework-agreement order — and
    `getattr(None, 'shipping_fee', 0)` is 0, so the delivery and other fees the
    customer had agreed to were dropped without a word. The handover is the
    basis for the hóa đơn GTGT, so that undercharged the customer and took the
    VAT base from the wrong number.

    Returns None when nothing has been agreed yet.
    """
    from app.models.models import Contract as _Contract
    from app.models.models import OrderConfirmation as _Confirmation

    contract = _Contract.query.filter_by(
        order_id=order.id, is_signed=True, is_canceled=False, is_active=True,
    ).order_by(_Contract.contract_date.desc()).first()
    if contract:
        return contract

    return _Confirmation.query.filter_by(
        order_id=order.id, status=_Confirmation.STATUS_CONFIRMED,
        is_canceled=False,
    ).order_by(_Confirmation.confirmation_date.desc()).first()


def order_due_date(order, commitment=None):
    """The day this order was promised to the customer, or None.

    It was always written down and never read back. A contract states "Số
    ngày hoàn thành" (`contract_days_complete`, printed on the document) from
    its start date — or from signing, when no start date was given. A Đơn đặt
    hàng under a framework agreement states its `delivery_date` outright.
    Nothing compared either against the handover, so an order could run past
    what was promised with no one told.

    Pass `commitment` when the caller already holds it, to skip the lookup.
    """
    from datetime import timedelta

    from app.models.models import Contract as _Contract

    commitment = commitment if commitment is not None else order_commitment(order)
    if commitment is None:
        return None
    if isinstance(commitment, _Contract):
        start = (commitment.contract_start_date or commitment.contract_date
                 or (commitment.signed_date.date() if commitment.signed_date else None))
        days = commitment.contract_days_complete
        if start is None or not days:
            return None
        return start + timedelta(days=int(days))
    return commitment.delivery_date


def order_agreed_value(order):
    """What this order is worth, as currently agreed.

    One definition, because two of them disagreed. The margin calculation
    resolved it with `Contract.query.filter_by(is_signed=True,
    is_canceled=False).first()` — no `is_active`, so a renegotiated order could
    be valued at the contract it had replaced, and no ORDER BY, so WHICH of the
    two it picked was whatever the database happened to return first.

    A framework-agreement order has no contract at all; its value lives on the
    confirmed Đơn đặt hàng.

    Returns Decimal('0') when nothing has been agreed yet — an order that is
    still only a quotation is not owed anything.
    """
    from decimal import Decimal

    from app.models.models import Contract as _Contract

    commitment = order_commitment(order)
    if commitment is None:
        return Decimal('0')
    if isinstance(commitment, _Contract):
        return Decimal(str(commitment.contract_value or 0))
    return Decimal(str(commitment.total_amount or 0))


def order_amount_collected(order_id):
    """Confirmed, uncancelled money received against this order.

    Same rule the reports use, so the lifecycle flag and the receivable figure
    cannot disagree about whether a customer has paid.
    """
    from decimal import Decimal

    from app.models.models import PaymentReport as _Payment

    total = Decimal('0')
    payments = _Payment.query.filter_by(
        order_id=order_id, is_confirmed=True, is_canceled=False).all()
    for payment in payments:
        if payment.payment_type == 'advance':
            amount = payment.advance_amount or payment.amount or 0
        else:
            amount = payment.remaining_amount or payment.amount or 0
        total += Decimal(str(amount))
    return total


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
        # A receipt for nothing. Found by doing the sale in Chrome: the payment
        # form opens with an EMPTY line table until "Tải hạng mục từ hợp đồng"
        # is pressed, and saving it as it opens recorded a 0 đ advance — which
        # could then be confirmed, marking the order's advance as paid.
        # Only a receipt that records no money at all: an advance can be taken
        # with no line items (amount 0, advance_amount set), and that is money.
        if float(amount or 0) <= 0 and float(advance_amount or 0) <= 0:
            raise ValueError('Phiếu thanh toán chưa có số tiền. Bấm "Tải hạng mục từ '
                             'hợp đồng" hoặc nhập hạng mục trước khi lưu.')

        _order = OrderRepository().get_by_id(order_id)
        existing = self.repo.get_by_company_and_number(
            _order.company_id if _order else None, report_number)
        if existing:
            raise ValueError(f"Payment report {report_number} already exists")
        
        # Validate workflow sequencing
        order = OrderRepository().get_by_id(order_id)
        if not order or not order.lifecycle:
            raise ValueError("Order not found")
        
        # Sequencing delegated to WorkflowService; defaults reproduce the
        # previously hardcoded rules (advance needs a signed contract, final
        # needs a confirmed handover).
        if payment_type == 'advance':
            WorkflowService.require(order, ACTION_PAYMENT_ADVANCE)
        elif payment_type == 'final':
            WorkflowService.require(order, ACTION_PAYMENT_FINAL)

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
    
    
    def mark_confirmed(self, report_id, order_id):
        """Mark payment as confirmed and update lifecycle atomically"""
        try:
            report = self.repo.get_by_id(report_id)
            if not report:
                raise ValueError(f"Payment report {report_id} not found")
            
            # Cancelled is checked FIRST. `is_confirmed` stays true on a
            # voided payment — cancelling does not unset it, deliberately, so
            # the record still shows it was once confirmed — and an early
            # return on that flag meant a voided payment answered "already
            # done" and the route reported success.
            #
            # `can_confirm()` checks both conditions and the template uses it
            # to hide the button. Only the `is_confirmed` half was checked
            # here, so the other half lived entirely in a template. Hiding a
            # button is a convenience for whoever is looking at the screen; it
            # was never a rule, and a POST to the URL was never subject to it.
            #
            # Reachable only since voiding a confirmed payment became
            # possible: confirm, cancel (money goes back), POST confirm again.
            # A rule enforced only where it happened to be unreachable was
            # never working — it was untested.
            if report.is_canceled:
                raise ValueError('Phiếu đã huỷ thì không xác nhận được')

            if report.is_confirmed:
                logger.warning(f"Payment {report_id} already confirmed at {report.confirmed_date}")
                return report
            
            from app.services.transitions import record as _history
            _history(report.company_id, 'payment', report.id,
                     'payment.confirm', from_state='draft',
                     to_state='confirmed')

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
                # Paying the balance in two instalments is ordinary, and it
                # produces two 'final' slips. Marking the order paid on the
                # first one closed it while the customer still owed money —
                # and because the receivable is computed from the payments
                # rather than from this flag, the totals stayed right while
                # the work queue lied.
                agreed = order_agreed_value(report.order)
                collected = order_amount_collected(order_id)
                if agreed and collected < agreed:
                    logger.info(
                        "Payment confirmed for order %s: %s of %s collected, "
                        "still outstanding", order_id, collected, agreed)
                else:
                    lifecycle.fully_paid = True
                    lifecycle.fully_paid_at = datetime.utcnow()
                    lifecycle.completed = True
                    lifecycle.completed_at = datetime.utcnow()
                    logger.info(
                        f"Final payment confirmed - order {order_id} completed")
            
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
    
    def _resync_payment_lifecycle(self, order_id):
        """Set the money flags from the payments that actually stand.

        Asked of the data, not derived from what just changed: whichever
        payment was voided, and in whatever order, the answer is the same.
        """
        from app.repositories.repository import LifecycleStatusRepository
        from app.models.models import PaymentReport as _PR

        lifecycle = LifecycleStatusRepository().get_or_create_for_order(
            str(order_id))

        standing = _PR.query.filter(
            _PR.order_id == order_id,
            _PR.is_confirmed == True,        # noqa: E712
            _PR.is_canceled == False,        # noqa: E712
        ).all()

        has_advance = any(p.payment_type == 'advance' for p in standing)
        if not getattr(lifecycle, 'advance_skipped', False):
            lifecycle.advance_paid = has_advance
            if not has_advance:
                lifecycle.advance_paid_at = None

        # Paid in full is an arithmetic fact, not a flag somebody set: what has
        # been collected against what was agreed.
        agreed = order_agreed_value(lifecycle.order) if lifecycle.order else 0
        collected = order_amount_collected(order_id)
        lifecycle.fully_paid = bool(agreed) and collected >= agreed
        if not lifecycle.fully_paid:
            lifecycle.fully_paid_at = None

        # No separate "completed" state to unwind: `Order` has no status
        # column and `LifecycleStatus` has no `completed` flag — `fully_paid`
        # IS that state and the screens read it. I wrote code to reset a
        # field that does not exist; it raised only because Python has no
        # such attribute. A dict or a JSON blob would have swallowed it.

        db.session.add(lifecycle)
        return lifecycle

    def cancel_payment(self, payment_id, order_id, reason=""):
        """Cancel payment report and update lifecycle atomically"""
        try:
            payment = self.repo.get_by_id(payment_id)
            if not payment:
                raise ValueError(f"Payment report {payment_id} not found")
            
            if not payment.can_cancel():
                raise ValueError("Phiếu này đã được huỷ rồi")
            if payment.is_confirmed and not (reason or '').strip():
                # Money moving back with no explanation is a hole in the
                # record. A draft can be cancelled quietly; a confirmed slip
                # cannot.
                raise ValueError("Phải nhập lý do huỷ phiếu đã xác nhận")

            # Checked in the SERVICE, not only in the route: a period that is
            # closed is closed for every caller — a script, an import, a future
            # screen — and a control that only the UI enforces is one the next
            # entry point silently skips.
            from app.services.books import may_change
            allowed, why = may_change(payment)
            if not allowed:
                raise ValueError(why)
            
            from app.services.transitions import record as _history
            _history(payment.company_id, 'payment', payment.id,
                     'payment.cancel',
                     from_state='confirmed' if payment.is_confirmed
                     else 'draft',
                     to_state='canceled', reason=reason)

            # Update payment report
            payment.is_canceled = True
            payment.canceled_at = datetime.utcnow()
            payment.canceled_reason = reason

            # Everything the confirmation touched moves back.
            #
            # This used to handle ONLY `payment_type == 'advance'`, and it had
            # never run at all: `can_cancel()` refused every confirmed payment,
            # so the branch was dead code. Opening the door woke a path nobody
            # had executed, and it did half the job — void a FINAL payment and
            # the order stayed `completed` with `fully_paid` true, the system
            # saying a customer had paid in full while their money was given
            # back.
            #
            # Recomputed from the payments that remain rather than unpicked
            # flag by flag. Undoing a flag assumes this payment is the only
            # reason it was set; asking the data cannot make that mistake, and
            # gives the same answer whichever payment is voided and in which
            # order.
            if payment.is_confirmed:
                db.session.flush()
                self._resync_payment_lifecycle(payment.order_id)
            
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

    @staticmethod
    def _build_doc_basename(document_type, context, timestamp):
        """Build the document file base name per the business naming convention.

            BaoGia_{mã báo giá}_{ngày}_{giờ}      (quotation)
            HopDong_{mã hợp đồng}_{ngày}_{giờ}    (contract)
            TamUng_{mã hợp đồng}_{ngày}_{giờ}     (payment, advance)
            ThanhToan_{mã hợp đồng}_{ngày}_{giờ}  (payment, final)
            BanGiao_{mã hợp đồng}_{ngày}_{giờ}    (delivery / handover)

        The code is written "liền" (whitespace and path-unsafe characters removed).
        Advance/final payments and the handover all key off the CONTRACT number; the
        quotation keys off its own number, the contract off its own number.
        """
        import re as _re

        def _tidy(code):
            code = str(code or '').strip()
            code = _re.sub(r'\s+', '', code)                 # viết liền: no spaces
            code = _re.sub(r'[\\/:*?"<>|]', '-', code)       # path-safe
            return code or 'NA'

        if document_type == 'quotation':
            prefix, code = 'BaoGia', context.get('quotation_number')
        elif document_type == 'contract':
            prefix, code = 'HopDong', context.get('contract_number')
        elif document_type == 'delivery':
            prefix, code = 'BanGiao', context.get('contract_number') or context.get('report_number')
        elif document_type == 'payment':
            if context.get('payment_type') == 'final':
                prefix = 'ThanhToan'
            else:
                prefix = 'TamUng'
            code = context.get('contract_number') or context.get('report_number')
        else:
            prefix, code = (document_type or 'ChungTu'), context.get('report_number')

        return f"{prefix}_{_tidy(code)}_{timestamp}"

    def _save_document(self, *, company_id, order_id, template, document_type,
                       document_format, context,
                       quotation_id=None, contract_id=None,
                       handover_record_id=None, payment_report_id=None,
                       source=None):
        """
        Render & persist a document record.

        Chooses docxtpl (DOCX template) or legacy text-substitution based on
        the template file extension.

        `source` is the record the document was printed FROM. It fills
        `source_type`/`source_id`, which until now no code path wrote: the
        columns were added with a backfill, a lookup function was written
        against them, and tests passed because their fixtures set the columns
        by hand. So old rows had values, every NEW document had NULL, and a
        glance at the table looked healthy. Passing the record itself rather
        than a type string keeps the one mapping in `printing.SOURCE_TYPES`.
        """
        from io import BytesIO as _BytesIO

        timestamp  = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_name   = self._build_doc_basename(document_type, context, timestamp)
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

        # Regenerating supersedes the previous file for the SAME source
        # document, so the list stops showing three contract files with no
        # indication which one to send. A SIGNED document is never touched:
        # it is evidence, and a new draft must not quietly replace it.
        self._supersede_previous(
            order_id=order_id, document_type=document_type,
            quotation_id=quotation_id, contract_id=contract_id,
            handover_record_id=handover_record_id,
            payment_report_id=payment_report_id)

        from app.services.printing import source_type_of
        document = self.repo.create(
            company_id          = company_id,
            order_id            = order_id,
            template_id         = template.id,
            source_type         = source_type_of(source) if source else None,
            source_id           = getattr(source, 'id', None),
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

    def generate_purchase_order_document(self, po, company, format='docx'):
        """Print a purchase order FROM A TEMPLATE, the way everything else is.

        Returns `(BytesIO, Document)` on the template path, or `(None, None)`
        when the company has no purchase-order template yet — the caller then
        falls back to the built-in Python layout.

        The fallback is a MIGRATION PATH, not a second mechanism to keep. A
        company that has never opened the template screen still gets its
        purchase orders, unchanged, on the day this ships; once a template
        exists, that is what prints. `build_default_purchase_order_template`
        turns the built-in layout into exactly such a template, so becoming
        Cách A is one click rather than a document somebody has to author.
        """
        template = self.template_repo.get_default_for_type(company.id,
                                                           'purchase_order')
        if template is None:
            return None, None

        from app.utils.procurement_template import (
            collect_purchase_order_variables,
        )
        context = collect_purchase_order_variables(po, company)
        document = self._save_document(
            company_id=company.id,
            order_id=None,
            source=po,
            template=template,
            document_type='purchase_order',
            document_format=format,
            context=context)

        with open(document.file_path, 'rb') as handle:
            from io import BytesIO
            return BytesIO(handle.read()), document

    def generate_production_plan_document(self, plan, order, customer, company,
                                          format='docx'):
        """Print a production order FROM A TEMPLATE. See the PO twin above.

        Returns `(BytesIO, Document)`, or `(None, None)` when no template
        exists yet so the caller can fall back to the built-in layout.
        """
        template = self.template_repo.get_default_for_type(company.id,
                                                           'production_plan')
        if template is None:
            return None, None

        from app.utils.production_template import (
            collect_production_plan_variables,
        )
        context = collect_production_plan_variables(plan, order, customer,
                                                    company)
        document = self._save_document(
            company_id=company.id,
            order_id=getattr(order, 'id', None),
            source=plan,
            template=template,
            document_type='production_plan',
            document_format=format,
            context=context)

        with open(document.file_path, 'rb') as handle:
            from io import BytesIO
            return BytesIO(handle.read()), document

    def record_prebuilt_document(self, *, company_id, source, document_type,
                                 content, filename, order_id=None,
                                 folder_hint=None):
        """Store a document that was built in code rather than from a template.

        Two prints — the purchase order and the production plan — are produced
        by hardcoded Python builders and were streamed straight to the browser.
        Nothing was written down: no file kept, no `Document` row, so those
        screens can show no history and nobody can answer "which version did
        we send the supplier?". A document that leaves the building and leaves
        no trace is the one that causes the argument later.

        This does NOT make them template-driven. That is T-22b and needs a
        template authored, because a purchase-order layout has a row loop that
        cannot be mechanically inverted out of the Python that writes it. What
        this does is stop the record being lost in the meantime, which is the
        half that costs something today.

        `content` is the bytes already built. Kept deliberately narrow: this is
        a recording function, not a second way to produce documents.
        """
        def _safe(value):
            return (str(value or 'unknown')
                    .replace('/', '_').replace(chr(92), '_'))

        docs_dir = os.path.join(current_app.config['DOCUMENTS_FOLDER'],
                                _safe(folder_hint or 'chung'), document_type)
        os.makedirs(docs_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        stem, ext = os.path.splitext(filename)
        file_path = os.path.join(docs_dir, f'{_safe(stem)}_{timestamp}{ext}')
        with open(file_path, 'wb') as handle:
            handle.write(content)

        from app.services.printing import source_type_of
        document = self.repo.create(
            company_id     = company_id,
            order_id       = order_id,
            source_type    = source_type_of(source) if source else None,
            source_id      = getattr(source, 'id', None),
            document_name  = f'{stem}{ext}',
            document_type  = document_type,
            document_format= (ext or '.docx').lstrip('.'),
            file_path      = file_path,
            file_size      = len(content),
        )
        logger.info('Recorded prebuilt document %s', os.path.basename(file_path))
        return document

    def _supersede_previous(self, *, order_id, document_type,
                            quotation_id=None, contract_id=None,
                            handover_record_id=None, payment_report_id=None):
        """Mark earlier files for the same source document as superseded.

        Scoped to the specific source (this contract, this quotation) rather
        than to the order, so regenerating a contract never touches the
        order's handover or payment documents.
        """
        from app.models.models import Document

        query = Document.query.filter(
            Document.order_id == order_id,
            Document.document_type == document_type,
            Document.status == Document.STATUS_CURRENT,
        )
        # Narrow to the same source row when we know it.
        for column, value in (
            (Document.quotation_id, quotation_id),
            (Document.contract_id, contract_id),
            (Document.handover_record_id, handover_record_id),
            (Document.payment_report_id, payment_report_id),
        ):
            if value is not None:
                query = query.filter(column == value)

        superseded = 0
        for previous in query.all():
            previous.status = Document.STATUS_SUPERSEDED
            previous.superseded_at = datetime.utcnow()
            superseded += 1
        if superseded:
            db.session.flush()
            logger.info("Superseded %s earlier %s document(s)",
                        superseded, document_type)
        return superseded

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
            source       = quotation,
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
            source      = contract,
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
            source             = delivery_report,
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
            source            = payment_report,
            template          = template,
            document_type     = 'payment',
            document_format   = format,
            context           = context,
        )

    def generate_agreement_document(self, agreement_id, company_id,
                                    format='docx'):
        """Print a HỢP ĐỒNG NGUYÊN TẮC.

        `collect_master_agreement_variables` was written when the feature was
        built and then reached by nothing: the generator had no branch for this
        type, so the work was three quarters finished and produced no document.
        """
        from app.models.models import MasterAgreement
        from app.repositories.repository import CustomerRepository

        agreement = MasterAgreement.query.filter_by(
            id=agreement_id, company_id=company_id).first()
        if not agreement:
            raise ValueError("Framework agreement not found")

        customer = CustomerRepository().get_by_id(agreement.customer_id)
        template = self.template_repo.get_default_for_type(company_id,
                                                           'agreement')
        if not template:
            raise ValueError("No agreement template found for company")

        context = DocumentVariableCollector.collect_master_agreement_variables(
            agreement, customer, company=self._get_company(company_id))

        return self._save_document(
            company_id=company_id,
            # A framework agreement belongs to a customer, not to one order.
            order_id=None,
            source=agreement,
            template=template,
            document_type='agreement',
            document_format=format,
            context=context,
        )

    def generate_order_confirmation_document(self, confirmation_id, company_id,
                                             format='docx'):
        """Print an ĐƠN ĐẶT HÀNG issued under a framework agreement.

        This is the document a VAT invoice is raised against, so it is the one
        on this path that most needed printing.
        """
        from app.models.models import OrderConfirmation
        from app.repositories.repository import CustomerRepository, OrderRepository

        confirmation = OrderConfirmation.query.filter_by(
            id=confirmation_id, company_id=company_id).first()
        if not confirmation:
            raise ValueError("Order confirmation not found")

        order = OrderRepository().get_by_id(confirmation.order_id)
        customer = CustomerRepository().get_by_id(order.customer_id) if order else None
        template = self.template_repo.get_default_for_type(
            company_id, 'order_confirmation')
        if not template:
            raise ValueError("No order confirmation template found for company")

        context = DocumentVariableCollector.collect_order_confirmation_variables(
            confirmation, customer, order,
            company=self._get_company(company_id))

        return self._save_document(
            company_id=company_id,
            order_id=confirmation.order_id,
            source=confirmation,
            template=template,
            document_type='order_confirmation',
            document_format=format,
            context=context,
        )

    def generate_payment_request_document(self, order_id, company_id, format='docx'):
        """Generate a payment request document (Đề nghị thanh toán) for an order"""
        from app.repositories.repository import OrderRepository, CustomerRepository
        
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
            # No `source`: a payment request is raised for an ORDER, and Order
            # is deliberately not in `SOURCE_TYPES` — `order_id` already says
            # it. Left explicit so the omission reads as a decision.
            template          = template,
            document_type     = 'payment_request',
            document_format   = format,
            context           = context,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------


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

    def list_materials(self, company_id, category_id=None, search=None,
                       active_only=True, page=None, per_page=30):
        return self.repo.get_for_company(
            company_id, category_id=category_id, search=search,
            active_only=active_only, page=page, per_page=per_page
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
            if e.store_id is None:
                store_name = 'Kho công ty'
            else:
                store = self.store_repo.get_by_id(e.store_id)
                store_name = store.name if store else str(e.store_id)
            result.append({'entry': e, 'store_name': store_name})
        return result

    def update_stock(self, material_id, company_id, store_id, quantity):
        """Update or create stock quantity for a material+location."""
        mat = self.repo.get_by_id(material_id)
        if not mat or str(mat.company_id) != str(company_id):
            raise ValueError('NVL không tìm thấy')
        if quantity < 0:
            raise ValueError('Số lượng không thể âm')

        # The branch came straight off the form and went onto the stock row;
        # only the MATERIAL's company was ever checked. Setting a figure by
        # hand is already the event that most needs explaining afterwards.
        from app.utils.scope import usable_store
        usable_store(company_id, store_id)

        # Account for the CHANGE, not the new total. Somebody setting a figure
        # by hand is the event that most needs explaining later, and a movement
        # holding the new total could not be added up against the others.
        from decimal import Decimal as _D

        from app.models.models import MaterialStock as _MS, StockMovement as _SM
        from app.services.stock_movements import record as _record

        before = _MS.query.filter_by(material_id=material_id,
                                     store_id=store_id).first()
        was = _D(str(before.current_quantity or 0)) if before else _D('0')
        entry = self.stock_repo.upsert_quantity(material_id, company_id,
                                                store_id, quantity)
        _record(company_id, material_id, store_id, _D(str(quantity)) - was,
                _SM.TYPE_ADJUST, ref_type='manual_adjustment')
        return entry

    def ensure_stock_entries_for_stores_of_company(self, company_id):
        """Every material of this company gets a row for every active branch.

        Called when a branch is created. Cheap for a workshop's catalogue and
        run once per branch, not per page view.
        """
        from app.models.models import Material

        for material in Material.query.filter_by(company_id=company_id).all():
            self.ensure_stock_entries_for_stores(material.id, company_id)

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
        from app.services.procurement_service import _next_document_number
        return _next_document_number(ProductionPlan, ProductionPlan.plan_number,
                                     company_id, 'KHSX', dated=False, width=5)

    def get_plan_for_order(self, order_id):
        from app.models.models import ProductionPlan
        return ProductionPlan.query.filter_by(order_id=order_id).first()

    def create_from_contract(self, commitment):
        """Idempotent: tạo 1 ProductionPlan (draft) cho order, copy item và gợi
        ý ProductionMaterialLine từ MaterialNorm khớp tên.

        ``commitment`` is whatever the customer actually agreed to: a signed
        Contract, or — on the framework-agreement path — a confirmed Đơn đặt
        hàng, which has no Contract at all.

        This used to take a Contract only, and was called from exactly one
        place: contract signing. So an order placed under a HĐNT reached the
        workshop never: no material lines, no stock deduction, no cost, no
        margin, and it never appeared on the production list. The fabric those
        jobs consumed stayed on the books — for exactly the repeat customers a
        workshop most wants to keep supplying.
        """
        from decimal import Decimal
        from app.models.models import (ProductionPlan, ProductionPlanItem,
                                        ProductionMaterialLine, MaterialNorm)
        from app.models.models import Contract as _Contract
        from app.repositories.repository import OrderRepository
        order = OrderRepository().get_by_id(commitment.order_id)
        if order is None:
            return None
        existing = ProductionPlan.query.filter_by(order_id=commitment.order_id).first()
        if existing:
            return existing
        plan = ProductionPlan(
            order_id=commitment.order_id,
            # Only a Contract may fill contract_id; the column is a foreign key
            # to contracts, and an Đơn đặt hàng is not one.
            contract_id=commitment.id if isinstance(commitment, _Contract) else None,
            company_id=order.company_id,
            plan_number=self._gen_plan_number(order.company_id),
            status=ProductionPlan.STATUS_DRAFT)
        db.session.add(plan)
        db.session.flush()
        for it in (commitment.items or []):
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
        st = MaterialStock.query.filter_by(material_id=material_id,
                                           store_id=store_id).first()
        if st is None:
            # The company-level row (store_id NULL) is not "another branch's
            # stock". For a company that has never split its inventory by
            # location it is the ONLY place stock is recorded — `create_material`
            # makes exactly that row, and `MaterialService.update_stock` writes
            # to it. Reading it when the branch has no row of its own is reading
            # where the data is, not moving anything.
            #
            # I removed this and was wrong. The undocumented-transfer problem is
            # drawing from the company warehouse when the branch HAS a row and
            # is short — and this never did that: it fires only when the row is
            # absent. Removing it made company-level stock invisible to both
            # issuing and purchase suggestions, which showed up as a branch with
            # 10 units being told to buy 35 instead of 25.
            #
            # What made a NEW branch dangerous was having no rows at all, so the
            # fallback fired for it. `StoreService.create_store` now creates
            # them at zero, which closes that case without hiding this one.
            st = MaterialStock.query.filter_by(material_id=material_id,
                                               store_id=None).first()
        return st

    def stock_levels(self, plan):
        """What the store holds for each material this plan needs.

        The plan screen listed what the job requires and what has been handed
        over, but not what is actually there — so the only way to find out the
        fabric was short was to press Cấp phát and be refused. Telling someone
        afterwards is not a smaller version of telling them before: before,
        they can raise a requisition and carry on; after, they have already
        promised the workshop a start date.

        Uses the same `_stock_for` lookup the allocation uses, so the screen
        and the refusal can never disagree.

        Returns ``{line_id: {name, available, still_required, missing, short}}``.
        """
        from decimal import Decimal

        levels = {}
        for line in plan.material_lines:
            still = (Decimal(str(line.quantity_required or 0))
                     - Decimal(str(line.quantity_issued or 0)))
            entry = self._stock_for(line.material_id,
                                    line_source_store(line, plan))
            # No stock row at all is the ordinary state of a material nobody
            # has bought yet — zero, not an error and not unknown.
            available = Decimal(str(entry.current_quantity)) if entry else Decimal('0')
            missing = still - available
            levels[str(line.id)] = {
                'name': line.material.name if line.material else '',
                'available': float(available),
                'still_required': float(still),
                'missing': float(missing) if missing > 0 else 0.0,
                'short': bool(still > 0 and missing > 0),
            }
        return levels

    def issue_materials(self, plan, allow_partial=False):
        """Cấp phát: kiểm tồn trước; nếu thiếu → trả danh sách shortage, KHÔNG trừ.
        Nếu đủ → trừ MaterialStock, set quantity_issued, status=in_progress."""
        from decimal import Decimal
        needs = []
        for line in plan.material_lines:
            need = Decimal(str(line.quantity_required or 0)) - Decimal(str(line.quantity_issued or 0))
            if need > 0:
                needs.append((line, need))
        shortages = []
        for line, need in needs:
            st = self._stock_for(line.material_id, line_source_store(line, plan))
            avail = Decimal(str(st.current_quantity)) if st else Decimal('0')
            if avail < need:
                # Name the material and do the subtraction here. The caller
                # used to get an id and a count, so the message on screen
                # could only say "3 materials" — leaving the workshop manager
                # to find which three by hand, from data this loop already has.
                material = line.material
                shortages.append({
                    'material_id': str(line.material_id),
                    'material_code': material.material_code if material else '',
                    'name': material.name if material else '',
                    'unit': line.unit or (material.unit.name
                                          if material and material.unit else ''),
                    'need': float(need),
                    'available': float(avail),
                    'missing': float(need - avail),
                })
        if shortages and not allow_partial:
            return shortages

        # Hand over what is actually there, line by line. Per line, not "take
        # whatever is on the shelf everywhere": a line with nothing available
        # is left alone rather than issued a token amount.
        issued_anything = False
        for line, need in needs:
            st = self._stock_for(line.material_id, line_source_store(line, plan))
            avail = Decimal(str(st.current_quantity)) if st else Decimal('0')
            take = need if avail >= need else avail
            if take <= 0:
                continue
            st.current_quantity = avail - take
            from app.models.models import StockMovement as _SM
            from app.services.stock_movements import record as _record
            _record(plan.company_id, line.material_id,
                    line_source_store(line, plan), -take, _SM.TYPE_ISSUE,
                    ref_type='production_plan', ref_id=plan.id,
                    warehouse_id=getattr(line, 'warehouse_id', None))
            # ACCUMULATE. This used to assign `quantity_required`, and under
            # all-or-nothing the two were the same number so nothing showed.
            # Issue 12 of 20 and the assignment would say 20, leaving the plan
            # looking complete with 8m still on the shelf.
            line.quantity_issued = Decimal(str(line.quantity_issued or 0)) + take
            issued_anything = True

        if issued_anything:
            plan.status = plan.STATUS_IN_PROGRESS
        db.session.commit()
        # A partial issue still reports what is missing. A success message on
        # its own would leave the foreman to discover the gap himself, which is
        # the thing refusing was protecting him from.
        return shortages

    def material_cost(self, plan):
        """What the materials ISSUED to this plan cost.

        Issued, not required: a plan can require more than has been handed to
        the workshop, and the business has only actually spent the issued
        part. Valued at each material's moving-average cost.

        Returns a dict with the total and the per-line detail, plus a count of
        lines whose material has no cost recorded yet — an honest total is
        worth less than an honest total that says what it could not price.
        """
        from decimal import Decimal

        lines = []
        total = Decimal('0')
        unpriced = 0

        for line in plan.material_lines:
            issued = Decimal(str(line.quantity_issued or 0))
            material = line.material
            unit_cost = Decimal(str(getattr(material, 'avg_cost', 0) or 0))

            if issued > 0 and unit_cost <= 0:
                unpriced += 1

            line_cost = issued * unit_cost
            total += line_cost
            lines.append({
                'material_name': material.name if material else '',
                'issued': float(issued),
                'unit': line.unit or '',
                'unit_cost': float(unit_cost),
                'line_cost': float(line_cost),
                'priced': unit_cost > 0 or issued == 0,
            })

        return {
            'total': float(total),
            'lines': lines,
            'unpriced_lines': unpriced,
            'complete': unpriced == 0,
        }

    def order_margin(self, plan):
        """Revenue minus material cost for the order behind this plan.

        Labour is NOT included — the system does not record it yet (see
        SME-GAPS G6). The result says so rather than presenting a material-only
        figure as if it were profit, which would flatter every job.
        """
        from decimal import Decimal

        order = plan.order
        cost = self.material_cost(plan)

        revenue = order_agreed_value(order)

        material_total = Decimal(str(cost['total']))
        return {
            'revenue': float(revenue),
            'material_cost': cost['total'],
            'gross_margin': float(revenue - material_total),
            'material_cost_complete': cost['complete'],
            'unpriced_lines': cost['unpriced_lines'],
            'excludes_labour': True,
        }

    def save_as_norm(self, plan_item):
        """Lưu định mức từ các material line của 1 item để tái sử dụng (upsert).

        Trả về SỐ định mức đã ghi. Hàm lặp trên material_lines, nên một hạng mục
        chưa khai vật tư sẽ không ghi gì — người gọi cần biết để không báo
        "đã lưu" trong khi không có gì được lưu.
        """
        from decimal import Decimal
        from app.models.models import MaterialNorm
        company_id = plan_item.plan.company_id
        key = _product_key(plan_item.source_name)
        qty = Decimal(str(plan_item.quantity or 0)) or Decimal('1')
        written = 0
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
            written += 1
        db.session.commit()
        return written

    def low_stock_materials(self, company_id):
        from app.models.models import Material
        mats = Material.query.filter_by(company_id=company_id, is_active=True).all()
        return [m for m in mats if m.is_low_stock]

    def purchase_suggestions(self, company_id):
        """Đề xuất mua hàng (PO): bung định mức của các kế hoạch SX đang hoạt động
        (BOM explosion), trừ tồn kho hiện có + bù lên mức tối thiểu, gộp theo NCC.

        Đề xuất mua = max(0, (nhu cầu chưa cấp phát) - tồn + mức tối thiểu).
        Trả về {'groups': [...], 'total': Decimal, 'count': n} — chỉ đọc, không ghi.
        """
        from decimal import Decimal
        from app.models.models import Material, ProductionPlan
        active = (ProductionPlan.STATUS_DRAFT, ProductionPlan.STATUS_APPROVED,
                  ProductionPlan.STATUS_PROCESSING, ProductionPlan.STATUS_REJECTED)
        plans = ProductionPlan.query.filter(
            ProductionPlan.company_id == company_id,
            ProductionPlan.status.in_(active)).all()

        # 1) Un-issued requirement, aggregated PER PRODUCTION SITE.
        #
        # It used to be aggregated per material across the whole company and
        # compared against `m.total_stock`, the sum over every branch — while
        # issuing draws from one branch only. A workshop needing 20m and
        # holding none was told to buy nothing because 50m sat at the showroom,
        # and the shortage then surfaced on the day of cutting.
        #
        # The showroom's fabric is not unavailable in principle — somebody can
        # drive it over — but it is not available to this plan without a
        # transfer that has to be decided and documented. Counting it as if it
        # were already at the workshop treats an undocumented move as a fact,
        # the same error as the issuing fallback that silently drew from the
        # company warehouse.
        per_site = {}
        for plan in plans:
            site = production_site_of(plan)
            for line in plan.material_lines:
                need = Decimal(str(line.quantity_required or 0)) - Decimal(str(line.quantity_issued or 0))
                if need > 0:
                    key = (site, line.material_id)
                    per_site[key] = per_site.get(key, Decimal('0')) + need

        # What to buy, summed over the sites that are short. A company with one
        # location has one site, so this is the same arithmetic it always did.
        required = {}
        shortfall = {}
        for (site, material_id), need in per_site.items():
            required[material_id] = required.get(material_id, Decimal('0')) + need
            entry = self._stock_for(material_id, site)
            here = Decimal(str(entry.current_quantity)) if entry else Decimal('0')
            missing = need - here
            if missing > 0:
                shortfall[material_id] = shortfall.get(material_id, Decimal('0')) + missing

        # Every active material is read, unpaginated, and each one is asked for
        # its stock (`is_low_stock`), supplier and unit. Loaded lazily that was
        # three queries per material — a thousand for a real catalogue.
        from sqlalchemy.orm import joinedload, selectinload
        mats = {m.id: m for m in Material.query.filter_by(company_id=company_id, is_active=True)
                .options(selectinload(Material.stock_entries),
                         joinedload(Material.supplier),
                         joinedload(Material.unit)).all()}
        # Candidate materials: needed by a plan OR below their min stock level.
        per_site_materials = set(required)
        candidates = per_site_materials | {mid for mid, m in mats.items() if m.is_low_stock}

        by_supplier = {}
        total = Decimal('0')
        count = 0
        for mid in candidates:
            m = mats.get(mid)
            if not m:
                continue
            need = required.get(mid, Decimal('0'))
            min_level = Decimal(str(m.min_stock_level or 0))
            if mid in per_site_materials:
                # Needed by a plan: buy what the sites that are short are
                # short by. `avail` is still reported so the screen can show
                # what the company holds in total — it is the figure a buyer
                # wants to see, and it is no longer the figure the suggestion
                # is derived from.
                avail = Decimal(str(m.total_stock or 0))
                suggest = shortfall.get(mid, Decimal('0')) + min_level
            else:
                # Below its minimum and needed by nobody: a company-wide
                # question, answered with the company-wide figure.
                avail = Decimal(str(m.total_stock or 0))
                suggest = need - avail + min_level
            if suggest <= 0:
                continue
            unit_price = Decimal(str(m.unit_price or 0))
            est = (suggest * unit_price).quantize(Decimal('1'))
            total += est
            count += 1
            sup = m.supplier
            key = str(sup.id) if sup else '__none__'
            grp = by_supplier.setdefault(key, {'supplier': sup, 'lines': [], 'subtotal': Decimal('0')})
            grp['subtotal'] += est
            grp['lines'].append({
                'material': m,
                'unit': (m.unit.name if m.unit else ''),
                'required': float(need),
                'available': float(avail),
                'min_level': float(min_level),
                'suggested': float(suggest),
                'unit_price': float(unit_price),
                'est_cost': float(est),
            })

        # Sort: named suppliers first (by name), "no supplier" last; lines by material code.
        groups = sorted(by_supplier.values(),
                        key=lambda g: (g['supplier'] is None, (g['supplier'].name if g['supplier'] else '')))
        for g in groups:
            g['lines'].sort(key=lambda ln: ln['material'].material_code)
            g['subtotal'] = float(g['subtotal'])
        return {'groups': groups, 'total': float(total), 'count': count}

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
