# SofaFlow Comprehensive Workflow Update

## Overview

This document outlines the complete refactoring of the SofaFlow order management system to implement the correct workflow sequence:

**Quotation → Contract → Advance Payment → Handover Record (Biên Bản Bàn Giao) → Final Payment**

## Changes Implemented

### 1. Data Model Updates (`app/models/models.py`)

#### Contract Model Enhancements
- Added `is_canceled` (Boolean, indexed)
- Added `canceled_at` (DateTime)
- Added `canceled_reason` (Text)
- Updated `can_edit()` method to check cancellation status
- Updated `can_sign()` method to check cancellation status
- New method: `can_cancel()` - permits cancellation only if not signed and not already canceled

#### DeliveryReport → HandoverRecord Rename
- Renamed model class from `DeliveryReport` to `HandoverRecord`
- Renamed database table from `delivery_reports` to `handover_records`
- **Removed fields:**
  - `work_description`
  - `materials_used`
  
- **Added fields for customer acceptance:**
  - `handover_date` (Date) - date of actual handover
  - `customer_representative` (String 200) - customer's representative name
  - `company_representative` (String 200) - company's representative name  
  - `product_condition` (Text) - description of product/service condition
  - `customer_signature_confirmed` (Boolean) - confirms customer receipt
  - `is_canceled` (Boolean, indexed)
  - `canceled_at` (DateTime)
  - `canceled_reason` (Text)

- **New methods:**
  - `can_edit()` - allows editing if not confirmed and not canceled
  - `can_confirm()` - permits confirmation if not confirmed and not canceled
  - `can_cancel()` - permits cancellation if not confirmed and not canceled

#### PaymentReport Model Enhancements
- Added `is_canceled` (Boolean, indexed)
- Added `canceled_at` (DateTime)
- Added `canceled_reason` (Text)
- New methods:
  - `can_edit()` - allows editing if not confirmed and not canceled
  - `can_confirm()` - permits confirmation if not confirmed and not canceled
  - `can_cancel()` - permits cancellation if not confirmed and not canceled

#### LifecycleStatus Model Updates
- Renamed `delivery_confirmed` → `handover_confirmed`
- Renamed `delivery_confirmed_at` → `handover_confirmed_at`

#### Document Model Updates
- Renamed foreign key from `delivery_report_id` → `handover_record_id`

#### Order Model Relationship Updates
- Changed `delivery_reports` relationship → `handover_records`

### 2. Service Layer Updates (`app/services/services.py`)

#### ContractService Enhancements
- **New method: `cancel_contract(contract_id, order_id, reason="")`**
  - Sets `is_canceled = True`, `is_active = False`
  - Sets `canceled_at = datetime.utcnow()`, `canceled_reason = reason`
  - Rolls back lifecycle only if no other active contracts exist
  - Atomically updates both contract and lifecycle

#### DeliveryReportService → HandoverRecordService Rename
Complete class rename with method updates:
  - `create_delivery_report()` → `create_handover_record()`
  - `mark_confirmed()` → `confirm_handover()`
  - **New method: `cancel_handover(record_id, order_id, reason="")`**
    - Similar to cancel_quotation pattern
    - Does not revert lifecycle (handover can be recreated)

Key constraint: Handover record can only be created when `lifecycle.advance_paid == True`

#### PaymentReportService Enhancements
- **Workflow validation in `create_payment_report()`:**
  - Advance payment requires: `contract_signed == True`
  - Final payment requires: `handover_confirmed == True`
  
- **New method: `cancel_payment(payment_id, order_id, reason="")`**
  - Permits cancellation of draft payments
  - Does not revert lifecycle (payment can be recreated)

- **Updated `mark_confirmed()` for workflow sequencing:**
  - Advance payment: sets `advance_paid = True`
  - Final payment: sets `fully_paid = True`, `completed = True`

### 3. Repository Layer Updates (`app/repositories/repository.py`)

- Renamed `DeliveryReportRepository` → `HandoverRecordRepository`
- Updated model reference from `DeliveryReport` → `HandoverRecord`
- All method names remain unchanged (`get_by_number()`, `get_for_order()`, etc.)

### 4. Routes Layer Updates (`app/routes/dashboard_routes.py`)

#### Import Updates
- Changed: `DeliveryReportService` → `HandoverRecordService`

#### New Routes Needed (To be implemented)

**Contract Management:**
- `POST /contracts/<contract_id>/cancel` - Cancel contract with reason

**Handover Record Management:**
- `GET /handover/<order_id>/create` - Create handover record form
- `POST /handover/<order_id>/create` - Submit handover record
- `GET /handover/<record_id>/view` - View handover record
- `GET /handover/<record_id>/edit` - Edit form
- `POST /handover/<record_id>/edit` - Update handover
- `POST /handover/<record_id>/confirm` - Confirm/approve handover
- `POST /handover/<record_id>/cancel` - Cancel handover

**Payment Management:**
- `GET /payments/<payment_id>/view` - View payment report
- `GET /payments/<payment_id>/edit` - Edit form
- `POST /payments/<payment_id>/edit` - Update payment
- `POST /payments/<payment_id>/cancel` - Cancel payment

### 5. Template Updates

#### New Templates Created

**Handover Templates:**
- `app/templates/handover/create.html` - Form for creating handover records
- `app/templates/handover/view.html` - Display handover record with actions
- `app/templates/handover/edit.html` - Form for editing handover records

**Payment Templates:**
- `app/templates/payments/view.html` - Display payment with full action panel
- `app/templates/payments/edit.html` - Form for editing payments

#### Templates to Update

**`app/templates/orders/view.html`:**
- Reorder timeline steps to match correct workflow:
  1. Quotation Created
  2. Quotation Approved
  3. Contract Created
  4. Contract Signed
  5. Advance Payment
  6. Handover Record (renamed from Delivery Completed)
  7. Final Payment

- Update all `delivery_confirmed` references → `handover_confirmed`
- Add cancel buttons next to existing action buttons for contracts
- Update Quick Actions section:
  - Show "Create Contract" when quotation approved
  - Show "Create Advance Payment" when contract signed
  - Show "Create Handover Record" when advance paid
  - Show "Create Final Payment" when handover confirmed

**`app/templates/contracts/view.html`:**
- Add "Cancel Contract" button when `contract.can_cancel()` is True
- Show cancellation reason if canceled

**General Updates:**
- Update all delivery-related button labels/paths to handover equivalents
- Update all route references from `/delivery/` to `/handover/`

### 6. Database Migration Script (`migrate_full_workflow.py`)

Comprehensive migration script that safely applies all changes:

**Operations:**
1. Add cancel fields to `contracts` table with indexes
2. Add cancel fields to `payment_reports` table with indexes
3. Migrate `delivery_reports` → `handover_records`:
   - Rename table
   - Rename `delivery_date` → `handover_date`
   - Remove `work_description`, `materials_used`
   - Add new handover-specific columns
4. Update `lifecycle_statuses`:
   - Rename `delivery_confirmed` → `handover_confirmed`
   - Rename `delivery_confirmed_at` → `handover_confirmed_at`
5. Update `documents` table:
   - Rename `delivery_report_id` → `handover_record_id`

**Safety Features:**
- Check column existence before adding/removing
- Idempotent operations (safe to run multiple times)
- Proper error handling with rollback
- Detailed logging of all changes

**Usage:**
```bash
python migrate_full_workflow.py
```

## Workflow Summary

### Correct Order: Quotation → Contract → Advance Payment → Handover → Final Payment

#### Step 1: Quotation (Báo Giá)
- Create quotation with line items
- Edit items and pricing
- Approve quotation
- Generate document (PDF/DOCX)
- Cancel if needed

#### Step 2: Contract (Hợp Đồng)
- Create contract based on quotation
- Can modify items (add products)
- Edit terms and conditions
- Sign contract to lock terms
- Cancel contract (only if unsigned)
- Generate document (PDF/DOCX)

#### Step 3: Advance Payment (Tạm Ứng)
- Available only after contract signed
- Create advance payment record
- Record payment details (method, reference)
- Confirm payment to unlock next step
- Cancel payment if needed
- Generate document (PDF/DOCX)

#### Step 4: Handover Record (Biên Bản Bàn Giao)
- Available only after advance payment confirmed
- Create handover record with customer/company representatives
- Document product condition at handover
- Confirm customer acceptance
- Cancel handover if needed
- Generate document (PDF/DOCX)

#### Step 5: Final Payment (Thanh Toán)
- Available only after handover confirmed
- Create final payment record
- Record remaining payment
- Confirm payment to mark order complete
- Cancel payment if needed
- Generate document (PDF/DOCX)

## Validation Enhancements

### Payment Sequencing
```python
# Advance Payment requires:
- Contract must be signed
- Workflow: Contract Signed → Advance Payment

# Final Payment requires:
- Handover record must be confirmed
- Workflow: Handover Confirmed → Final Payment
```

### Handover Sequencing
```python
# Handover Record requires:
- Advance payment must be confirmed
- Workflow: Advance Payment → Handover Record
```

## UI/UX Improvements

### Consistent View Pattern
Each document type (Quotation, Contract, Handover, Payment) follows identical pattern:
1. **Header** with document number and status badge
2. **Details Card** showing all fields
3. **Line Items** (where applicable)
4. **Action Sidebar** with context-sensitive buttons:
   - Edit (if editable)
   - Cancel (if cancelable) - triggers modal with reason
   - Confirm/Approve/Sign (if approvable)
   - Generate Document button
5. **Generated Documents** section with download links
6. **Order Summary** with quick reference to parent order

### Quick Actions
Timeline-based quick action buttons in order view:
- Shows correct buttons at each workflow stage
- Disabled when prerequisites not met
- Indicates which step is active
- Provides clear visual progression

### Status Badges
Color-coded status indicators:
- `DRAFT` (Gray) - not yet signed/confirmed
- `CONFIRMED`/`SIGNED` (Green) - actively confirmed
- `CANCELLED` (Red) - canceled with reason shown
- `PENDING` (Blue) - awaiting action

## Testing Checklist

- [ ] Quotation creation, approval, canceling workflow
- [ ] Contract creation with different items than quotation
- [ ] Contract signing prevents editing (except additions)
- [ ] Contract cancellation reverts lifecycle only if no other contracts
- [ ] Advance payment requires signed contract
- [ ] Handover record requires confirmed advance payment
- [ ] Final payment requires confirmed handover
- [ ] Cancel operations preserve audit trail (canceled_at, canceled_reason)
- [ ] Document generation works for all document types
- [ ] Database migration runs without errors
- [ ] All new routes respond correctly
- [ ] Template rendering without missing fields
- [ ] Error handling for out-of-sequence operations

##Deployment Steps

1. **Backup database** (critical)
   ```bash
   pg_dump $DATABASE_URL > backup_$(date +%s).sql
   ```

2. **Run migration script**
   ```bash
   python migrate_full_workflow.py
   ```

3. **Clear application cache**
   ```bash
   flask cache clear
   ```

4. **Restart Flask application**
   ```bash
   supervisorctl restart sofa-flow
   ```

5. **Verify workflow**
   - Test order creation through all steps
   - Confirm all buttons appear at correct workflow stages
   - Verify workflow validation (try out-of-sequence actions)

## Files Modified Summary

| File | Type | Changes |
|------|------|---------|
| `app/models/models.py` | Models | Contract, HandoverRecord, PaymentReport enhancements; Lifecycle updates |
| `app/repositories/repository.py` | Repositories | DeliveryReportRepository renamed |
| `app/services/services.py` | Services | ContractService.cancel_contract(), HandoverRecordService additions, PaymentReportService.cancel_payment() |
| `app/routes/dashboard_routes.py` | Routes | Import updates |
| `app/templates/handover/create.html` | Template | New handover creation form |
| `app/templates/handover/view.html` | Template | New handover detail view |
| `app/templates/handover/edit.html` | Template | New handover edit form |
| `app/templates/payments/view.html` | Template | New payment detail view |
| `app/templates/payments/edit.html` | Template | New payment edit form |
| `migrate_full_workflow.py` | Migration | Database migration script (new) |

## Notes

- All changes maintain backward compatibility at the database level
- Migration script is idempotent (safe to run multiple times)
- Cancellation operations create audit trails
- Workflow validation prevents out-of-sequence operations
- All new methods follow existing service layer patterns
- Templates use consistent Bootstrap styling
