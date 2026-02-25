# SofaFlow Workflow Implementation Guide - Remaining Tasks

## Quick Start for Completing the Implementation

### 1. Run the Database Migration

```bash
# From project root directory
python migrate_full_workflow.py
```

Expected output:
```
============================================================
SofaFlow Comprehensive Workflow Migration
============================================================
[1/5] Adding cancel fields to contracts table...
  ✓ Added is_canceled, canceled_at, canceled_reason to contracts
[2/5] Adding cancel fields to payment_reports table...
  ✓ Added is_canceled, canceled_at, canceled_reason to payment_reports
[3/5] Renaming delivery_reports table to handover_records...
  ✓ Renamed delivery_reports to handover_records
[4/5] Updating lifecycle_statuses table...
  ✓ Renamed delivery_confirmed -> handover_confirmed
[5/5] Updating documents table...
  ✓ Renamed delivery_report_id -> handover_record_id
============================================================
✓ All migrations completed successfully!
```

### 2. Add Missing Routes to `dashboard_routes.py`

Replace the existing delivery related routes with new handover routes, and add payment/contract management routes.

**Key locations in `app/routes/dashboard_routes.py`:**

Find and replace around line 560:
```python
@dashboard_bp.route('/delivery/<order_id>/create', methods=['GET', 'POST'])
@login_required
def create_delivery(order_id):
```

With handover equivalent. Template pattern provided below.

### 3. Core Implementation Patterns

#### Route Pattern 1: Create Resource
```python
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
            return redirect(url_for('dashboard.view_handover', handover_id=handover.id))
            
        except ValueError as e:
            flash(f'Error: {str(e)}', 'error')
        except Exception as e:
            logger.error(f"Error creating handover: {str(e)}")
            flash('Error creating handover record', 'error')
    
    return render_template('handover/create.html', order=order)
```

#### Route Pattern 2: View Resource
```python
@dashboard_bp.route('/handover/<handover_id>/view', methods=['GET'])
@login_required
def view_handover(handover_id):
    """View handover record"""
    company_id = get_current_company_id()
    
    from app.repositories.repository import HandoverRecordRepository
    handover_repo = HandoverRecordRepository()
    handover = handover_repo.get_by_id(handover_id)
    
    if not handover or str(handover.order.company_id) != str(company_id):
        flash('Handover record not found or access denied', 'error')
        return redirect(url_for('dashboard.list_orders'))
    
    return render_template('handover/view.html', handover=handover)
```

#### Route Pattern 3: Edit Resource
```python
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
            handover.report_number = request.form.get('report_number', '').strip()
            handover.report_date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
            handover.handover_date = datetime.strptime(request.form.get('handover_date'), '%Y-%m-%d').date()
            handover.customer_representative = request.form.get('customer_representative', '').strip() or None
            handover.company_representative = request.form.get('company_representative', '').strip() or None
            handover.product_condition = request.form.get('product_condition', '').strip() or None
            handover.notes = request.form.get('notes', '').strip() or None
            
            db.session.commit()
            flash('Handover record updated successfully', 'success')
            return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
            
        except Exception as e:
            logger.error(f"Error updating handover: {str(e)}")
            flash('Error updating handover record', 'error')
            db.session.rollback()
    
    return render_template('handover/edit.html', handover=handover)
```

#### Route Pattern 4: Confirm Resource
```python
@dashboard_bp.route('/handover/<handover_id>/confirm', methods=['POST'])
@login_required
def confirm_handover(handover_id):
    """Confirm/approve handover record"""
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
        flash('Handover record confirmed successfully', 'success')
    except Exception as e:
        logger.error(f"Error confirming handover: {str(e)}")
        flash('Error confirming handover record', 'error')
    
    return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
```

#### Route Pattern 5: Cancel Resource
```python
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
        reason = request.form.get('reason', '').strip()
        handover_service = HandoverRecordService()
        handover_service.cancel_handover(handover_id, handover.order_id, reason)
        flash('Handover record cancelled successfully', 'success')
    except Exception as e:
        logger.error(f"Error cancelling handover: {str(e)}")
        flash('Error cancelling handover record', 'error')
    
    return redirect(url_for('dashboard.view_handover', handover_id=handover_id))
```

### 4. Routes to Implement - Complete Checklist

Copy the patterns above to implement these routes:

**Contract Management:**
- [ ] `POST /contracts/<contract_id>/cancel` - Cancel contract

**Handover Records:**
- [ ] `GET /handover/<order_id>/create` - Create form
- [ ] `POST /handover/<order_id>/create` - Create action
- [ ] `GET /handover/<handover_id>/view` - View details
- [ ] `GET /handover/<handover_id>/edit` - Edit form
- [ ] `POST /handover/<handover_id>/edit` - Update action
- [ ] `POST /handover/<handover_id>/confirm` - Confirm action
- [ ] `POST /handover/<handover_id>/cancel` - Cancel action

**Payment Reporting:**
- [ ] `GET /payments/<payment_id>/view` - View details
- [ ] `GET /payments/<payment_id>/edit` - Edit form
- [ ] `POST /payments/<payment_id>/edit` - Update action
- [ ] `POST /payments/<payment_id>/cancel` - Cancel action

### 5. Update Order View Template

In `app/templates/orders/view.html`, update:

1. **Reorder timeline** (find sections with line numbers ~191-460):
   - Quotation Created (keep)
   - Quotation Approved (keep)
   - Contract Created (move up)
   - Contract Signed (move up)
   - **Advance Payment** (move here)
   - **Handover Record** (renamed from Delivery Completed, moved here)
   - Final Payment (keep)

2. **Update lifecycle references:**
   - `delivery_confirmed` → `handover_confirmed`
   - `delivery_confirmed_at` → `handover_confirmed_at`

3. **Quick Actions section** (around line 430):
   - "Create Handover" button shows when: `contract_signed AND NOT handover_confirmed`
   - "Create Advance Payment" button shows when: `contract_signed AND NOT advance_paid`
   - "Create Final Payment" button shows when: `handover_confirmed AND NOT fully_paid`

4. **Add cancel buttons** to Contract sections

### 6. Update Contract View Template

In `app/templates/contracts/view.html`:

1. Add Cancel button in actions area:
```html
{% if contract.can_cancel() %}
<button type="button" class="btn btn-sm btn-danger w-100 mb-2" data-bs-toggle="modal" data-bs-target="#cancelModal">
    <i class="bi bi-x-circle"></i> Cancel Contract
</button>
{% endif %}
```

2. Add cancel modal (copy pattern from `app/templates/handover/view.html`)

### 7. Testing Sequence

After implementing all routes:

```
1. Create Order
   ✓ Quotation created
   
2. Approve Quotation
   ✓ Can see Quotation Approved
   
3. Create Contract
   ✓ Contract Created appears in timeline
   
4. Sign Contract
   ✓ Contract Signed appears
   ✓ Add button now shows "Create Advance Payment"
   
5. Create & Confirm Advance Payment
   ✓ Advance Paid shows in timeline
   ✓ Add button shows "Create Handover Record"
   
6. Create & Confirm Handover Record
   ✓ Handover Confirmed shows in timeline
   ✓ Add button shows "Create Final Payment"
   
7. Create & Confirm Final Payment
   ✓ Fully Paid shows in timeline
   ✓ Order marked as Completed
   
8. Test Cancellations
   ✓ Cancel contract before signing
   ✓ Cancel payment before confirming
   ✓ Cancel handover before confirming
   ✓ Verify error messages for out-of-sequence actions
```

### 8. Verification Commands

```bash
# Check migrations were applied
psql $DATABASE_URL -c "
  SELECT column_name FROM information_schema.columns 
  WHERE table_name = 'contracts' AND column_name = 'is_canceled';"

# Should return: is_canceled

# Verify handover_records table exists
psql $DATABASE_URL -c "SELECT table_name FROM information_schema.tables WHERE table_name = 'handover_records';"

# Should return: handover_records
```

### 9. Debugging Tips

**If migrations fail:**
```python
# Check what columns already exist
from app.config.database import db
inspector = db.inspect(db.engine)
columns = [c['name'] for c in inspector.get_columns('contracts')]
print(columns)
```

**If routes not found:**
- Verify imports at top of `dashboard_routes.py`
- Check function names are unique
- Verify blueprints registered in `__init__.py`

**If templates render incorrectly:**
- Check all form field names match model properties
- Verify handover model has all expected attributes
- Check Jinja2 syntax in templates

## Key Files & Line References

| Task | File | Approximate Line |
|------|------|-----------------|
| Remove delivery routes | `dashboard_routes.py` | 560-610 |
| Add handover routes | `dashboard_routes.py` | 560+ (replace) |
| Update imports | `dashboard_routes.py` | 7 |
| Timeline reorder | `orders/view.html` | 191-460 |
| Quick Actions | `orders/view.html` | 430+ |
| Contract cancel button | `contracts/view.html` | ~TBD |

## Success Criteria

✅ All 7 new handover routes working  
✅ All 4 new payment routes working  
✅ 1 contract cancel route working  
✅ Order timeline shows steps in correct order  
✅ Quick Actions show correct buttons at each step  
✅ Workflow prevents out-of-sequence operations  
✅ Cancellation modals work with reason input  
✅ Document generation works for all types  
✅ All tests pass  
✅ Database migration completed without errors  

---

**Ready to proceed?** Start with the database migration, then implement routes using the patterns above.
