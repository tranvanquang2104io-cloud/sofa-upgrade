# Advance Payment - Document Management Implementation

## Overview
Added comprehensive document viewing and editing functionality to the Advance Payment step in the workflow. Users can now view payment details, edit payment information, manage documents, and generate payment documents.

## Changes Made

### 1. **Backend Routes** (`app/routes/dashboard_routes.py`)
Added three new routes to handle payment management:

#### **View Payment Route**
- **Endpoint:** `GET /payment/<payment_id>`
- **Function:** `view_payment(payment_id)`
- **Description:** Display detailed payment report view with all payment information and generated documents
- **Features:**
  - View payment details (amount, dates, method, status)
  - View all generated documents with download links
  - See payment status (Draft, Confirmed, or Cancelled)
  - View associated order information

#### **Edit Payment Route**
- **Endpoint:** `GET/POST /payment/<payment_id>/edit`
- **Function:** `edit_payment(payment_id)`
- **Description:** Edit payment report details (only when not confirmed or cancelled)
- **Features:**
  - Edit report number, dates, amount, and payment method
  - Edit transaction reference and notes
  - Payment type is read-only (cannot be changed)
  - Shows generated documents sidebar during editing
  - Prevents editing if payment is confirmed or cancelled

#### **Cancel Payment Route**
- **Endpoint:** `POST /payment/<payment_id>/cancel`
- **Function:** `cancel_payment(payment_id)`
- **Description:** Cancel a payment report with reason
- **Features:**
  - Records cancellation reason
  - Updates payment status
  - Only allows cancellation if not already confirmed or cancelled

### 2. **Frontend Templates**

#### **`app/templates/orders/view.html`** - Enhanced Timeline View
**Advance Payment Section Improvements:**
- Added **View** button to open full payment details page
- Added **Edit** button (visible only when payment can be edited)
- Kept **Generate Document** button for creating payment documents
- Kept **Confirm** button to mark payment as confirmed
- All buttons now properly link to dedicated routes

**Button Layout:**
```
View | Edit | Generate Document | Confirm
```

#### **`app/templates/payments/view.html`** - Full Payment View Page
**New Features:**
- Comprehensive payment detail display
- **Generated Documents Section:**
  - Shows all documents created for this payment
  - Displays document name, format (PDF/DOCX), file size, and generation date
  - Individual download buttons for each document
- **Actions Panel:**
  - Edit button (conditional visibility)
  - Confirm Payment button (conditional visibility)
  - Cancel Payment button (conditional visibility)
  - Generate Document form with format selection
- **Order Information Panel:**
  - Quick links to related order and customer info
  - Order total amount display

#### **`app/templates/payments/edit.html`** - Enhanced Edit Page
**Improvements:**
- Added side panel showing payment status and information
- Added generated documents list in sidebar for reference during editing
- Improved layout with better spacing and organization
- Shows warning if payment cannot be edited
- All form fields properly labeled and validated

## Database Models
No database schema changes required. Existing relationships leverage:
- `PaymentReport.documents` - relationship to all generated documents
- `Document.payment_report_id` - foreign key linking documents to payments

## Service Layer
Used existing services:
- `PaymentReportService.get_payment_report()` - retrieve payment details
- `PaymentReportService.mark_confirmed()` - confirm payment
- `PaymentReportService.cancel_payment()` - cancel payment
- `DocumentService.generate_payment_document()` - generate documents

## Security
All routes include:
- `@login_required` decorator - user authentication check
- Company ID validation - ensures users only access their own company's data
- Permission checks - validates user can edit/view/cancel based on payment state

## User Workflow

### Advance Payment Process
1. **Record Advance Payment** - Create payment report from order view
2. **View Payment Details** - Click "View" button in timeline to see full details
3. **Edit Payment** - Click "Edit" button to modify payment information (if not confirmed)
4. **Generate Document** - Click "Generate Document" to create PDF/DOCX payment record
5. **View Documents** - All generated documents listed in payment view
6. **Download Documents** - Download any generated document with one click
7. **Confirm Payment** - Click "Confirm" to mark payment as received/confirmed
8. **View Payment History** - All documents and details preserved for audit trail

## Testing Recommendations

### Test Cases
1. **View Payment** - Verify all payment details display correctly
2. **Edit Payment** - Test editing various fields and document visibility during edit
3. **Generate Documents** - Confirm PDF and DOCX generation works
4. **Download Documents** - Test document downloads with correct names and formats
5. **Permissions** - Verify users can only access/edit their own company's payments
6. **Workflow Validation** - Confirm payment state prevents editing when appropriate

### Test Data Needed
- Active order with contract signed
- Created advance payment records
- Generated payment documents in PDF and DOCX formats

## Integration Points
- **Order View** - Links to payment management from workflow timeline
- **Payment Confirmation** - Updates order lifecycle when confirmed
- **Document Generation** - Uses existing document service and templates
- **Download Handling** - Uses existing document download functionality

## Future Enhancements
- Payment search and filtering
- Bulk payment operations
- Payment status history/audit trail
- Email notifications for payment confirmation
- Payment reconciliation reports
- Integration with accounting system
