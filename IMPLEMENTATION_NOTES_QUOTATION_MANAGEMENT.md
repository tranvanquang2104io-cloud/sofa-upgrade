# SofaFlow Enhancement Summary - Quotation & Lifecycle Management

**Date:** February 25, 2026  
**Status:** Implementation Complete

## Overview
Comprehensive enhancement of the SofaFlow order management system with advanced quotation management, single-active constraint enforcement, and lifecycle action buttons.

## Changes Implemented

### 1. Database Models (`app/models/models.py`)

#### Quotation Model - Enhanced
- **New Fields:**
  - `is_active: Boolean` - Track if quotation is current/active
  - `is_canceled: Boolean` - Track if quotation has been canceled
  - `canceled_at: DateTime` - Timestamp of cancellation
  - `canceled_reason: Text` - Reason for cancellation
  
- **Business Logic Methods:**
  - `can_edit()` - Returns true if quotation is not yet approved
  - `can_approve()` - Returns true if quotation can be approved (active, not canceled, not already approved)
  - `can_cancel()` - Returns true if quotation can be canceled (active, not canceled, not approved)

- **Constraint:** Only one active quotation per order (enforced at application layer)

#### Contract Model - Enhanced  
- **New Fields:**
  - `items: JSON` - Can differ from quotation as additional products can be added
  - `is_active: Boolean` - Only one active contract per order

- **Business Logic Methods:**
  - `can_edit()` - Returns true if contract is not signed
  - `can_sign()` - Returns true if contract is not signed

- **Constraint:** Only one active contract per order (enforced at application layer)

### 2. Database Schema Migration

Executed migration script (`migrate_models.py`) to add new columns:
- `ALTER TABLE quotations` - Added `is_active`, `is_canceled`, `canceled_at`, `canceled_reason`
- `ALTER TABLE contracts` - Added `items` JSON field, `is_active` boolean
- Applied indexing on `(order_id, is_active)` composite indices for efficient queries

### 3. Service Layer (`app/services/services.py`)

#### QuotationService - New Methods

**`approve_quotation(quotation_id, order_id)`**
- Validates quotation state before approval
- Sets `is_approved = TRUE`
- Updates lifecycle status `quotation_approved = TRUE`
- Throws ValueError if quotation cannot be approved

**`cancel_quotation(quotation_id, reason="")`**
- Sets `is_canceled = TRUE`, `is_active = FALSE`
- Records cancellation timestamp and reason
- Prevents cancellation of approved quotations

**`update_quotation(quotation_id, items, total_amount, validity_days, notes)`**
- Allows editing only if quotation not yet approved
- Updates line items, total amount, validity period, notes
- Throws ValueError if quotation already approved

**`get_active_quotation_for_order(order_id)`**
- Returns currently active (non-canceled) quotation for an order
- Query: `WHERE order_id = ? AND is_active = TRUE AND is_canceled = FALSE`

#### Enhanced Error Handling
- All methods include proper validation with descriptive error messages
- Lifecycle updates use explicit `db.session.add()` for SQLAlchemy 2.0 compatibility

###4. Routing Layer (`app/routes/dashboard_routes.py`)

#### New Routes

**`GET /quotations/<quotation_id>/view`**
- Display quotation details page
- Show approval status, items, total amount
- Display generated documents
- Render action buttons based on quotation state

**`GET/POST /quotations/<quotation_id>/edit`**
- Edit quotation form (only if not approved)
- Add/remove line items with real-time total calculation
- Validate state before allowing edit
- Redirect to view page after save

**`POST /quotations/<quotation_id>/approve`**
- Approve quotation endpoint
- Call service layer with validation
- Update lifecycle status
- Flash success/error messages

**`POST /quotations/<quotation_id>/cancel`**
- Cancel quotation with reason
- Only allow if quotation not already approved
- Update order state

### 5. Template Layer

#### New Templates

**`quotations/view.html`** - Quotation Detail Page
- Display quotation number, date, validity, amount
- Show current status (Pending/Approved/Canceled)
- List line items in tabular format
- Display generated documents
- Action buttons:
  - Edit (if editable)
  - Approve (if approvable)
  - Cancel (if cancelable)
  - Generate Document

**`quotations/edit.html`** - Quotation Edit Form
- Editable form fields for date, validity, notes
- Dynamic line item management (add/remove rows)
- Real-time total calculation via JavaScript
- Validation before submission

#### Updated Templates

**`orders/view.html`** - Order View Page
- Enhanced quotation display section
- Show all active quotations for the order
- Hide canceled quotations from main view
- Add action buttons inline:
  - View Details (links to quotation view page)
  - Approve Quotation (with confirmation dialog)
  - Generate Document (modal for format selection)
- Display approval status badge on each quotation  
- Modal dialogs for generate document action

### 6. Business Logic Constraints

#### Single Active Quotation Per Order
```python
# Application-level enforcement:
- When creating quotation: Check no other active quotation exists
- When approving: Mark as approved
- When canceling: Mark as inactive
- When loading order: Query WHERE is_active = TRUE AND is_canceled = FALSE
```

#### Single Active Contract Per Order
```python
# Similar pattern to quotations
- Only one contract with is_active = TRUE per order
- Previous contracts archived with is_active = FALSE
```

#### State Transitions
**Quotation States:**
```
Created → Pending Approval
         → Can be Edited (if not approved)
         → Can be Approved (if not canceled)
         → Can be Canceled (if not approved)
Approved → Cannot be edited
         → Locked for contract creation
Canceled → Inactive, archived
```

### 7. User Interface Improvements

#### Approval Workflow
- Clear "Approve" button on pending quotations
- Confirmation dialog before approval
- Success/error flash messages
- Status badge (Pending/Approved/Canceled)

#### Document Generation
- Modal dialog for document format selection
- Generate button on each quotation
- Download capability after generation

#### Edit Capability
- Edit button visible only on non-approved quotations
- Real-time item total calculation
- Add/remove line items dynamically
- Validation before saving

##Validation & Error Handling

### State Validation
- Quotations checked before approval/cancellation
- Contracts verified before state changes
- Lifecycle consistency ensured with explicit session management

### User Feedback
- Flash messages on all actions
- Inline error messages in forms
- Confirmation dialogs for destructive actions
- Status badges showing current state

### Database Consistency
- Foreign key constraints maintained
- Cascade deletes on document removal
- Transaction management for state transitions
- Indexes on frequently queried fields

## File Manifest

### Modified Files
- `app/models/models.py` - Enhanced Quotation & Contract models
- `app/services/services.py` - Added QuotationService methods
- `app/routes/dashboard_routes.py` - New quotation management routes
- `app/templates/orders/view.html` - Enhanced with approval actions
- `migrate_models.py` - Database schema updates

### New Files
- `app/templates/quotations/view.html` - Quotation detail page
- `app/templates/quotations/edit.html` - Quotation edit form

## Testing Checklist

- [ ] Create quotation for order OK
- [ ] View quotation details page
- [ ] Edit quotation (before approval)
- [ ] Approve quotation from order page
- [ ] Verify lifecycle status updates
- [ ] Try editing approved quotation (should fail)
- [ ] Cancel quotation with reason
- [ ] Verify canceled quotation hidden from main view
- [ ] Generate document from quotation
- [ ] Create second quotation for same order (should work after canceling first)
- [ ] Verify database constraints working
- [ ] Check order status consistency across page refreshes

## Deployment Notes

1. Run migration script: `python migrate_models.py`
2. Database schema updated with new columns and indices
3. No data loss - all existing quotations set to `is_active = TRUE` by default
4. Backward compatible - existing code continues to work
5. Restart Flask application to load new routes

## Future Enhancements

1. Batch quotation cancellation
2. Quotation version history/audit trail
3. Approval workflows with multi-step sign-off
4. Quotation comparison view (for selecting between multiple quotes)
5. Quotation templates for recurring items
6. Email notifications on approval/rejection
7. Analytics dashboard for quotation metrics

---

**Implementation Status:** ✅ COMPLETE  
**Ready for Testing:** YES  
**Production Deployment:** Recommended after QA testing
