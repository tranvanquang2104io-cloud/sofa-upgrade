"""
Dashboard and main application routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, send_file
from app.utils.auth_utils import login_required, ensure_tenant_access, get_current_company_id
from app.services.services import (
    StoreService, CustomerService, OrderService, QuotationService,
    ContractService, HandoverRecordService, PaymentReportService, DocumentService
)
from app.repositories.repository import (
    StoreRepository, CustomerRepository, OrderRepository, DocumentRepository
)
from app.models import Order, Document
from app.config.database import db
from datetime import datetime, date
import logging
import os

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


# ===== DASHBOARD =====

@dashboard_bp.route('/')
@login_required
def index():
    """Main dashboard"""
    company_id = get_current_company_id()
    
    order_service = OrderService()
    store_repo = StoreRepository()
    
    # Get recent orders
    recent_orders = order_service.list_orders_for_company(company_id, page=1, per_page=10)
    
    # Get stores
    stores = store_repo.get_stores_for_company(company_id)
    
    return render_template('dashboard/index.html',
                         orders=recent_orders,
                         stores=stores,
                         total_orders=order_service.repo.count())


# ===== CUSTOMERS =====

@dashboard_bp.route('/customers', methods=['GET'])
@login_required
def list_customers():
    """List customers"""
    company_id = get_current_company_id()
    store_id = request.args.get('store_id')
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    
    store_repo = StoreRepository()
    customer_service = CustomerService()
    
    # Get stores for company
    stores = store_repo.get_stores_for_company(company_id)
    
    # Select store (use first if not specified)
    if not store_id and stores:
        store_id = stores[0].id
    
    customers = None
    total = 0
    
    if store_id:
        # Verify store belongs to company
        store = store_repo.get_active_store(company_id, store_id)
        if not store:
            flash('Store not found or access denied', 'error')
            return redirect(url_for('dashboard.index'))
        
        if search:
            customers = customer_service.search_customers(store_id, search)
            total = len(customers)
        else:
            customers = customer_service.list_customers_for_store(store_id, page=page, per_page=20)
            total = customer_service.count_customers_for_store(store_id)
    
    return render_template('customers/list.html',
                         customers=customers,
                         stores=stores,
                         selected_store_id=store_id,
                         page=page,
                         total=total,
                         search=search)


@dashboard_bp.route('/customers/create', methods=['GET', 'POST'])
@login_required
def create_customer():
    """Create customer"""
    company_id = get_current_company_id()
    store_repo = StoreRepository()
    store_id = request.args.get('store_id') or request.form.get('store_id')
    
    stores = store_repo.get_stores_for_company(company_id)
    
    if not store_id and stores:
        store_id = stores[0].id
    
    if request.method == 'POST':
        try:
            store_customer = CustomerService()
            customer = store_customer.create_customer(
                store_id=store_id,
                customer_code=request.form.get('customer_code', '').strip(),
                name=request.form.get('name', '').strip(),
                phone=request.form.get('phone', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                address=request.form.get('address', '').strip() or None,
                city=request.form.get('city', '').strip() or None,
                postal_code=request.form.get('postal_code', '').strip() or None,
                country=request.form.get('country', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            flash('Customer created successfully', 'success')
            return redirect(url_for('dashboard.list_customers', store_id=store_id))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating customer: {str(e)}")
            flash('Error creating customer', 'error')
    
    return render_template('customers/create.html', stores=stores, selected_store_id=store_id)


@dashboard_bp.route('/customers/<customer_id>')
@login_required
def view_customer(customer_id):
    """View customer details"""
    company_id = get_current_company_id()
    customer_repo = CustomerRepository()
    
    customer = customer_repo.get_by_id(customer_id)
    if not customer or str(customer.store.company_id) != str(company_id):
        flash('Customer not found or access denied', 'error')
        return redirect(url_for('dashboard.list_customers'))
    
    order_service = OrderService()
    orders = order_service.list_orders_for_customer(customer_id)
    
    return render_template('customers/view.html', customer=customer, orders=orders)


# ===== ORDERS =====

@dashboard_bp.route('/orders', methods=['GET'])
@login_required
def list_orders():
    """List all orders"""
    company_id = get_current_company_id()
    page = request.args.get('page', 1, type=int)
    
    order_service = OrderService()
    orders = order_service.list_orders_for_company(company_id, page=page, per_page=20)
    
    return render_template('orders/list.html', orders=orders, page=page)


@dashboard_bp.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_order():
    """Create order"""
    company_id = get_current_company_id()
    store_repo = StoreRepository()
    customer_repo = CustomerRepository()
    
    stores = store_repo.get_stores_for_company(company_id)
    
    if request.method == 'POST':
        try:
            store_id = request.form.get('store_id')
            customer_id = request.form.get('customer_id')
            
            # Verify access
            customer = customer_repo.get_by_id(customer_id)
            if not customer or str(customer.store_id) != str(store_id):
                flash('Invalid customer selection', 'error')
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
            
            flash('Order created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order.id))
            
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            logger.error(f"Error creating order: {str(e)}")
            flash('Error creating order', 'error')
    
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
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('orders/view.html', **order_details)


# ===== QUOTATIONS =====

@dashboard_bp.route('/quotations/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_quotation(order_id):
    """Create quotation"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Parse items from request
            items = []
            item_names = request.form.getlist('item_name[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            total = 0
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    total += item_total
            
            quotation_service = QuotationService()
            quotation = quotation_service.create_quotation(
                order_id=order_id,
                quotation_number=request.form.get('quotation_number', '').strip(),
                quotation_date=datetime.strptime(request.form.get('quotation_date'), '%Y-%m-%d').date(),
                items=items,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Quotation created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error creating quotation: {str(e)}")
            flash('Error creating quotation', 'error')
    
    return render_template('quotations/create.html', order=order)


# ===== QUOTATION DETAIL, EDIT, AND LIFECYCLE ACTIONS =====

@dashboard_bp.route('/quotations/<quotation_id>/view', methods=['GET'])
@login_required
def view_quotation(quotation_id):
    """View quotation details"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    quotation = quotation_service.get_quotation(quotation_id)
    if not quotation or str(quotation.order.company_id) != str(company_id):
        flash('Quotation not found or access denied', 'error')
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
        flash('Quotation not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if not quotation.can_edit():
        flash('Quotation cannot be edited after approval', 'error')
        return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
    
    if request.method == 'POST':
        try:
            # Parse items from request
            items = []
            item_names = request.form.getlist('item_name[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            total = 0
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
                    total += item_total
            
            quotation_service.update_quotation(
                quotation_id=quotation_id,
                items=items,
                total_amount=total,
                validity_days=int(request.form.get('validity_days', 30)),
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Quotation updated successfully', 'success')
            return redirect(url_for('dashboard.view_quotation', quotation_id=quotation_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating quotation: {str(e)}")
            flash('Error updating quotation', 'error')
    
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
            flash('Quotation not found or access denied', 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        quotation_service.approve_quotation(quotation_id, quotation.order_id)
        flash('Quotation approved successfully', 'success')
        
    except ValueError as e:
        flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        logger.error(f"Error approving quotation: {str(e)}")
        flash('Error approving quotation', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))


@dashboard_bp.route('/quotations/<quotation_id>/cancel', methods=['POST'])
@login_required
def cancel_quotation(quotation_id):
    """Cancel quotation"""
    company_id = get_current_company_id()
    quotation_service = QuotationService()
    
    try:
        quotation = quotation_service.get_quotation(quotation_id)
        if not quotation or str(quotation.order.company_id) != str(company_id):
            flash('Quotation not found or access denied', 'error')
            return redirect(url_for('dashboard.list_orders'))
        
        reason = request.form.get('reason', '').strip() or 'No reason provided'
        quotation_service.cancel_quotation(quotation_id, reason)
        flash('Quotation canceled successfully', 'success')
        
    except ValueError as e:
        flash(f'Error: {str(e)}', 'error')
    except Exception as e:
        logger.error(f"Error canceling quotation: {str(e)}")
        flash('Error canceling quotation', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=quotation.order_id))


# ===== CONTRACTS =====

@dashboard_bp.route('/contracts/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_contract(order_id):
    """Create contract"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    # Only show active quotations (not canceled) - typically approved ones for contract
    quotations = [q for q in order.quotations if q.is_active and not q.is_canceled]
    
    if request.method == 'POST':
        try:
            contract_service = ContractService()
            contract = contract_service.create_contract(
                order_id=order_id,
                quotation_id=request.form.get('quotation_id') or None,
                contract_number=request.form.get('contract_number', '').strip(),
                contract_date=datetime.strptime(request.form.get('contract_date'), '%Y-%m-%d').date(),
                contract_value=float(request.form.get('contract_value') or 0),
                terms_and_conditions=request.form.get('terms_and_conditions', '').strip() or None
            )
            
            flash('Contract created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating contract: {str(e)}")
            flash('Error creating contract', 'error')
    
    return render_template('contracts/create.html', order=order, quotations=quotations)


@dashboard_bp.route('/contracts/<contract_id>/view', methods=['GET'])
@login_required
def view_contract(contract_id):
    """View contract details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('contracts/view.html', contract=contract, order=contract.order)


@dashboard_bp.route('/contracts/<contract_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_contract(contract_id):
    """Edit contract - only if not signed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if contract.is_signed:
        flash('Cannot edit a signed contract', 'error')
        return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
    
    if request.method == 'POST':
        try:
            from app.services.services import ContractService
            contract_service = ContractService()
            
            # Parse contract data
            contract_value = float(request.form.get('contract_value', 0))
            terms_and_conditions = request.form.get('terms_and_conditions', '').strip() or None
            
            # Parse items from form
            items = []
            item_names = request.form.getlist('item_name[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_prices = request.form.getlist('item_price[]')
            
            for i, name in enumerate(item_names):
                if name:
                    qty = float(item_quantities[i] or 0)
                    price = float(item_prices[i] or 0)
                    item_total = qty * price
                    items.append({
                        'name': name,
                        'quantity': qty,
                        'unit_price': price,
                        'total': item_total
                    })
            
            # Update contract
            contract.contract_value = contract_value
            contract.terms_and_conditions = terms_and_conditions
            contract.items = items
            contract.updated_at = datetime.utcnow()
            db.session.commit()
            
            flash('Contract updated successfully', 'success')
            return redirect(url_for('dashboard.view_contract', contract_id=contract_id))
            
        except Exception as e:
            logger.error(f"Error updating contract: {str(e)}")
            flash('Error updating contract', 'error')
    
    return render_template('contracts/edit.html', contract=contract, order=contract.order)


@dashboard_bp.route('/contracts/<contract_id>/sign', methods=['POST'])
@login_required
def sign_contract(contract_id):
    """Mark contract as signed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import ContractRepository
    contract_repo = ContractRepository()
    contract = contract_repo.get_by_id(contract_id)
    
    if not contract or str(contract.order.company_id) != str(company_id):
        flash('Contract not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        contract_service = ContractService()
        contract_service.mark_signed(contract_id, contract.order_id)
        flash('Contract marked as signed', 'success')
    except Exception as e:
        logger.error(f"Error signing contract: {str(e)}")
        flash('Error signing contract', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=contract.order_id))


# ===== DELIVERY REPORTS =====

@dashboard_bp.route('/handover/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_handover(order_id):
    """Create handover record"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            handover_service = HandoverRecordService()
            handover = handover_service.create_handover_record(
                order_id=order_id,
                report_number=request.form.get('report_number', '').strip(),
                report_date=datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date(),
                handover_date=datetime.strptime(request.form.get('handover_date'), '%Y-%m-%d').date(),
                customer_representative=request.form.get('customer_representative', '').strip() or None,
                company_representative=request.form.get('company_representative', '').strip() or None,
                product_condition=request.form.get('product_condition', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Handover record created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except Exception as e:
            logger.error(f"Error creating handover record: {str(e)}")
            flash('Error creating handover record', 'error')
    
    return render_template('handover/create.html', order=order)


@dashboard_bp.route('/handover/<handover_id>/confirm', methods=['POST'])
@login_required
def confirm_handover(handover_id):
    """Mark handover as confirmed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        handover_service.confirm_handover(handover_id, handover.order_id)
        flash('Handover record confirmed', 'success')
    except Exception as e:
        logger.error(f"Error confirming handover: {str(e)}")
        flash('Error confirming handover', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=handover.order_id))


@dashboard_bp.route('/handover/<handover_id>', methods=['GET'])
@login_required
def view_handover(handover_id):
    """View handover record details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('handover/view.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_handover(handover_id):
    """Edit handover record"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not handover.can_edit():
                flash('Handover record cannot be edited (already confirmed or canceled)', 'error')
                return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
            # Update handover fields
            handover.report_number = request.form.get('report_number', '').strip()
            handover.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
            handover.handover_date = datetime.strptime(request.form.get('handover_date'), '%Y-%m-%d').date()
            handover.company_representative = request.form.get('company_representative', '').strip() or None
            handover.customer_representative = request.form.get('customer_representative', '').strip() or None
            handover.product_condition = request.form.get('product_condition', '').strip() or None
            handover.notes = request.form.get('notes', '').strip() or None
            handover.updated_at = datetime.utcnow()
            
            db.session.add(handover)
            db.session.commit()
            
            flash('Handover record updated successfully', 'success')
            return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating handover record: {str(e)}")
            flash('Error updating handover record', 'error')
    
    return render_template('handover/edit.html', handover=handover)


@dashboard_bp.route('/handover/<handover_id>/cancel', methods=['POST'])
@login_required
def cancel_handover(handover_id):
    """Cancel handover record"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        handover_service = HandoverRecordService()
        reason = request.form.get('reason', '').strip()
        handover_service.cancel_handover(handover_id, handover.order_id, reason)
        flash('Handover record canceled successfully', 'success')
    except Exception as e:
        logger.error(f"Error canceling handover: {str(e)}")
        flash(f'Error canceling handover: {str(e)}', 'error')
    
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
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    # Get default payment type from query parameter (advance or final)
    default_type = request.args.get('type', 'advance')
    
    if request.method == 'POST':
        try:
            payment_service = PaymentReportService()
            payment_type = request.form.get('payment_type')
            
            # Validate payment sequencing
            if payment_type == 'advance' and not order.lifecycle.contract_signed:
                flash('Advance payment can only be recorded after contract is signed', 'error')
                return render_template('payment/create.html', order=order, default_type=default_type)
            
            if payment_type == 'final' and not order.lifecycle.handover_confirmed:
                flash('Final payment can only be recorded after handover is confirmed', 'error')
                return render_template('payment/create.html', order=order, default_type=default_type)
            
            payment = payment_service.create_payment_report(
                order_id=order_id,
                report_number=request.form.get('report_number', '').strip(),
                payment_type=payment_type,
                report_date=datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date(),
                payment_date=datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date(),
                amount=float(request.form.get('amount') or 0),
                payment_method=request.form.get('payment_method', '').strip() or None,
                transaction_reference=request.form.get('transaction_reference', '').strip() or None,
                notes=request.form.get('notes', '').strip() or None
            )
            
            flash('Payment report created successfully', 'success')
            return redirect(url_for('dashboard.view_order', order_id=order_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error creating payment report: {str(e)}")
            flash('Error creating payment report', 'error')
    
    return render_template('payment/create.html', order=order, default_type=default_type)


@dashboard_bp.route('/payment/<payment_id>/confirm', methods=['POST'])
@login_required
def confirm_payment(payment_id):
    """Mark payment as confirmed"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        payment_service = PaymentReportService()
        payment_service.mark_confirmed(payment_id, payment.order_id)
        flash('Payment marked as confirmed', 'success')
    except Exception as e:
        logger.error(f"Error confirming payment: {str(e)}")
        flash('Error confirming payment', 'error')
    
    return redirect(url_for('dashboard.view_order', order_id=payment.order_id))


@dashboard_bp.route('/payment/<payment_id>', methods=['GET'])
@login_required
def view_payment(payment_id):
    """View payment report details"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('payments/view.html', payment=payment)


@dashboard_bp.route('/payment/<payment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_payment(payment_id):
    """Edit payment report"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    if request.method == 'POST':
        try:
            # Only allow editing if not confirmed and not canceled
            if not payment.can_edit():
                flash('Payment cannot be edited (already confirmed or canceled)', 'error')
                return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
            # Update payment fields
            payment.report_number = request.form.get('report_number', '').strip()
            payment.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
            payment.payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
            payment.amount = float(request.form.get('amount') or 0)
            payment.payment_method = request.form.get('payment_method', '').strip() or None
            payment.transaction_reference = request.form.get('transaction_reference', '').strip() or None
            payment.notes = request.form.get('notes', '').strip() or None
            payment.updated_at = datetime.utcnow()
            
            db.session.add(payment)
            db.session.commit()
            
            flash('Payment report updated successfully', 'success')
            return redirect(url_for('dashboard.view_payment', payment_id=payment_id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error updating payment report: {str(e)}")
            flash('Error updating payment report', 'error')
    
    return render_template('payments/edit.html', payment=payment)


@dashboard_bp.route('/payment/<payment_id>/cancel', methods=['POST'])
@login_required
def cancel_payment(payment_id):
    """Cancel payment report"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import PaymentReportRepository
    payment_repo = PaymentReportRepository()
    payment = payment_repo.get_by_id(payment_id)
    
    if not payment or str(payment.order.company_id) != str(company_id):
        flash('Payment report not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    try:
        payment_service = PaymentReportService()
        reason = request.form.get('reason', '').strip()
        payment_service.cancel_payment(payment_id, payment.order_id, reason)
        flash('Payment report canceled successfully', 'success')
    except Exception as e:
        logger.error(f"Error canceling payment: {str(e)}")
        flash(f'Error canceling payment: {str(e)}', 'error')
    
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
            from app.repositories.repository import QuotationRepository
            quotation = QuotationRepository().get_by_id(ref_id)
            if not quotation or str(quotation.order.company_id) != str(company_id):
                flash('Quotation not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_quotation_document(ref_id, quotation.order_id, company_id, doc_format)
        
        elif doc_type == 'contract':
            from app.repositories.repository import ContractRepository
            contract = ContractRepository().get_by_id(ref_id)
            if not contract or str(contract.order.company_id) != str(company_id):
                flash('Contract not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_contract_document(
                ref_id, contract.order_id, company_id, 
                quotation_id=contract.quotation_id, format=doc_format
            )
        
        elif doc_type == 'handover':
            from app.repositories.repository import HandoverRecordRepository
            handover = HandoverRecordRepository().get_by_id(ref_id)
            if not handover or str(handover.order.company_id) != str(company_id):
                flash('Handover record not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_delivery_document(ref_id, handover.order_id, company_id, doc_format)
        
        elif doc_type == 'payment':
            from app.repositories.repository import PaymentReportRepository
            payment = PaymentReportRepository().get_by_id(ref_id)
            if not payment or str(payment.order.company_id) != str(company_id):
                flash('Payment report not found', 'error')
                return redirect(request.referrer)
            
            document = document_service.generate_payment_document(ref_id, payment.order_id, company_id, doc_format)
        
        else:
            flash('Unknown document type', 'error')
            return redirect(request.referrer)
        
        flash('Document generated successfully', 'success')
        
    except Exception as e:
        logger.error(f"Error generating document: {str(e)}")
        flash(f'Error generating document: {str(e)}', 'error')
    
    return redirect(request.referrer)


@dashboard_bp.route('/documents/<document_id>/download')
@login_required
def download_document(document_id):
    """Download document"""
    company_id = get_current_company_id()
    doc_repo = DocumentRepository()
    
    document = doc_repo.get_by_id(document_id)
    if not document or str(document.company_id) != str(company_id):
        flash('Document not found or access denied', 'error')
        return redirect(request.referrer)
    
    if not os.path.exists(document.file_path):
        flash('Document file not found', 'error')
        return redirect(request.referrer)
    
    try:
        return send_file(
            document.file_path,
            as_attachment=True,
            download_name=f"{document.document_name}.{document.document_format}"
        )
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        flash('Error downloading document', 'error')
        return redirect(request.referrer)


@dashboard_bp.route('/documents/<order_id>')
@login_required
def list_documents(order_id):
    """List documents for order"""
    company_id = get_current_company_id()
    order_service = OrderService()
    
    order = order_service.get_order(order_id, company_id)
    if not order:
        flash('Order not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    doc_service = DocumentService()
    documents = doc_service.list_documents_for_order(order_id)
    
    return render_template('documents/list.html', order=order, documents=documents)


@dashboard_bp.route('/api/quotations/<quotation_id>')
@dashboard_bp.route('/api/quotations/<quotation_id>')
@login_required
def get_quotation_detail(quotation_id):
    """Get quotation details as JSON - for AJAX calls"""
    company_id = get_current_company_id()
    
    try:
        from app.repositories.repository import QuotationRepository
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
            'items': items,
            'is_approved': quotation.is_approved,
            'is_canceled': quotation.is_canceled
        }
        
        return response, 200
        
    except Exception as e:
        logger.error(f"Error getting quotation detail for {quotation_id}: {str(e)}", exc_info=True)
        return {'error': f'Error: {str(e)}'}, 500

