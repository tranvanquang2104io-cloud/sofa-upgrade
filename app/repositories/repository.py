"""
Repository layer for data access
"""
from app.config.database import db
from app.models import (
    Company, Store, User, Customer, Order, Quotation, Contract,
    HandoverRecord, PaymentReport, Document, DocumentTemplate, LifecycleStatus,
    MaterialUnit, MaterialCategory, Supplier, Material, MaterialStock,
)
from sqlalchemy import desc
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import joinedload
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
        """Get a record by id, WITHOUT any tenant check.

        An id that is not a valid UUID returns None rather than raising. A
        malformed id is a request for something that does not exist, which is
        a 404 — the callers all treat None that way already. It used to reach
        the database and come back as `ValueError: badly formed hexadecimal
        UUID string`, i.e. a 500, so any mistyped or stale link crashed the
        screen instead of saying "not found".

        Found when `/materials/low-stock` was removed: the URL then fell
        through to `/materials/<material_id>` and the whole page 500'd.

        Tenant safety is therefore the caller's responsibility. A sweep in
        tests/test_tenant_isolation_sweep.py confirms every current detail
        route does check ownership, but this default is a standing hazard:
        the next route that forgets leaks another company's data, and nothing
        in the type signature warns about it.

        Prefer :meth:`get_for_company` in new code.
        """
        try:
            return self.model.query.get(id)
        except (ValueError, StatementError):
            db.session.rollback()
            return None

    def get_for_company(self, id, company_id):
        """Get a record by id ONLY if it belongs to ``company_id``.

        Returns None for another tenant's record, so a forgotten ownership
        check cannot become a data leak. Available on every repository whose
        model carries ``company_id``.
        """
        if not hasattr(self.model, 'company_id'):
            raise AttributeError(
                f'{self.model.__name__} has no company_id; use a scoped query '
                f'via its parent instead'
            )
        return self.model.query.filter_by(id=id, company_id=company_id).first()
    
    
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
    
    
    def get_users_for_company(self, company_id):
        """Get all active users for a company"""
        return self.model.query.filter_by(company_id=company_id, is_active=True).all()

    def get_users_for_store(self, store_id):
        """Get all active users assigned to a specific store"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).all()



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

    
    def get_customers_for_store(self, store_id, limit=None, offset=None):
        """Get all customers for a store"""
        query = self.model.query.filter_by(store_id=store_id, is_active=True)
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()



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
    
    def get_orders_for_company(self, company_id, limit=None, offset=None,
                               store_ids=None):
        """Get orders for a company (eager-loads customer + lifecycle to avoid
        N+1 in the list view — AUDIT W17/PF1).

        ``store_ids`` narrows to those stores IN THE QUERY. Callers used to take
        the company's newest N and filter afterwards, which silently returns
        fewer than N — or none at all when the other branches have been busier.
        The limit has to apply to the rows you want, not to the rows you are
        about to discard.
        """
        query = self.model.query.filter_by(company_id=company_id, is_active=True).options(
            joinedload(self.model.customer),
            joinedload(self.model.lifecycle),
        )
        if store_ids is not None:
            query = query.filter(self.model.store_id.in_(list(store_ids)))
        query = query.order_by(desc(self.model.created_at))
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        return query.all()
    
    def count_for_store(self, store_id):
        """Count orders in store"""
        return self.model.query.filter_by(store_id=store_id, is_active=True).count()


class OrderScopedRepository(BaseRepository):
    """A repository whose rows belong to an order, and so to a branch.

    `get_by_id` here refuses a row whose order sits in a branch the current
    user is not in. See `app/utils/scope.py` for why the check lives at this
    level and not on the routes.

    The refusal reads as "not found", which is what the callers already do with
    a missing id: `if not contract or str(contract.order.company_id) != ...`.
    So no call site had to change to get the branch check -- and no call site
    can forget it.
    """

    def get_by_id(self, id):
        from app.utils.scope import within_branch
        return within_branch(super().get_by_id(id))


class QuotationRepository(OrderScopedRepository):
    """Repository for Quotation model"""

    def __init__(self):
        super().__init__(Quotation)
    

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
    


class ContractRepository(OrderScopedRepository):
    """Repository for Contract model"""
    
    def __init__(self):
        super().__init__(Contract)
    

    def get_by_company_and_number(self, company_id, contract_number):
        """Per-tenant duplicate check via the contract's order company (W6b/B3)."""
        return (self.model.query
                .join(Order, Order.id == self.model.order_id)
                .filter(Order.company_id == company_id,
                        self.model.contract_number == contract_number)
                .first())
    
    def get_for_order(self, order_id):
        """Get all contracts for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    


class HandoverRecordRepository(OrderScopedRepository):
    """Repository for HandoverRecord model"""
    
    def __init__(self):
        super().__init__(HandoverRecord)
    

    def get_by_company_and_number(self, company_id, report_number):
        """Per-tenant duplicate check via the record's order company (W6b/B3)."""
        return (self.model.query
                .join(Order, Order.id == self.model.order_id)
                .filter(Order.company_id == company_id,
                        self.model.report_number == report_number)
                .first())
    
    def get_for_order(self, order_id):
        """Get all handover records for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    


class PaymentReportRepository(OrderScopedRepository):
    """Repository for PaymentReport model"""
    
    def __init__(self):
        super().__init__(PaymentReport)
    

    def get_by_company_and_number(self, company_id, report_number):
        """Per-tenant duplicate check via the report's order company (W6b/B3)."""
        return (self.model.query
                .join(Order, Order.id == self.model.order_id)
                .filter(Order.company_id == company_id,
                        self.model.report_number == report_number)
                .first())
    
    def get_for_order(self, order_id):
        """Get all payment reports for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.created_at)
        ).all()
    


class DocumentRepository(OrderScopedRepository):
    """Repository for Document model"""
    
    def __init__(self):
        super().__init__(Document)
    
    def get_for_order(self, order_id):
        """Get all documents for order"""
        return self.model.query.filter_by(order_id=order_id).order_by(
            desc(self.model.generated_at)
        ).all()
    
    def get_for_quotation(self, quotation_id):
        """Get documents for quotation"""
        return self.model.query.filter_by(quotation_id=quotation_id).order_by(
            desc(self.model.generated_at)
        ).all()
    
    
    


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
        """The template a document of this type is printed from.

        Activation is exclusive per type, so normally only one row matches.
        Rows created before that rule can still be doubly active, and `.first()`
        with no ORDER BY left the choice to whatever order the database
        returned — so a user could upload a corrected template, activate it,
        and go on printing the old one with nothing on screen to say so.

        The most recently created active template is the one the user chose
        last, so it wins.
        """
        return self.model.query.filter_by(
            company_id=company_id,
            document_type=document_type,
            is_active=True
        ).order_by(self.model.created_at.desc()).first()


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

    def get_for_company(self, company_id, category_id=None, active_only=True,
                        search=None, page=None, per_page=30):
        """Materials for a company with optional filters.

        Returns a Flask-SQLAlchemy Pagination when ``page`` is given, else the
        full list — the same contract the procurement lists use, so a caller
        that wants everything (an export, a dropdown) still gets everything.
        """
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
        q = q.order_by(self.model.material_code)
        if page:
            # The list screen shows each row's stock, low-stock flag, unit and
            # category; loaded lazily that was a query per row for each.
            from sqlalchemy.orm import selectinload
            q = q.options(selectinload(self.model.stock_entries),
                          joinedload(self.model.unit),
                          joinedload(self.model.category))
            return q.paginate(page=page, per_page=per_page, error_out=False)
        return q.all()

    def get_by_code(self, company_id, material_code):
        """Get material by code within company."""
        return self.model.query.filter_by(
            company_id=company_id, material_code=material_code
        ).first()



class MaterialStockRepository(BaseRepository):
    """Repository for MaterialStock model"""

    def __init__(self):
        super().__init__(MaterialStock)

    def get_for_material(self, material_id):
        """All stock entries for a material."""
        return self.model.query.filter_by(material_id=material_id).all()


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
        """Auto-generate next supplier code: NCC-001, NCC-002 ...

        From the highest code already issued, not from a row count: counting
        reissues a code as soon as a supplier is deleted, and
        (company_id, supplier_code) is unique.
        """
        from app.services.procurement_service import _next_document_number
        return _next_document_number(self.model, self.model.supplier_code,
                                     company_id, 'NCC', dated=False, width=3)
