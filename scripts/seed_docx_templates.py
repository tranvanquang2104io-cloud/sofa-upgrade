"""
seed_docx_templates.py
======================
Registers (or updates) the four DOCX document templates in the database.

• If a template of the given type already exists for the company it is
  updated (file path + format changed to .docx).
• If no template exists yet a new record is created.

Run AFTER create_docx_templates.py:
  python create_docx_templates.py     # generates the .docx files
  python seed_docx_templates.py       # registers them in the DB
"""

import os
from app import create_app
from app.config.database import db
from app.models.models import DocumentTemplate, Company

app = create_app()

# Mapping:  document_type  →  (display_name, filename, variable_description)
TEMPLATES = {
    'quotation': (
        'Báo Giá (Quotation)',
        'quotation_template.docx',
        {
            'company_name':     'Company name',
            'quotation_number': 'Quotation number',
            'quotation_date':   'Quotation date (dd/mm/yyyy)',
            'validity_days':    'Validity in days',
            'customer_name':    'Customer full name',
            'customer_code':    'Customer code',
            'customer_phone':   'Customer phone',
            'customer_email':   'Customer email',
            'customer_address': 'Customer address',
            'order_code':       'Order code',
            'order_title':      'Order title/description',
            'items':            'List of product items [{stt, name, unit, quantity, unit_price, total, notes}]',
            'total_amount':     'Total amount (formatted)',
            'notes':            'Quotation notes',
            'generated_date':   'Document generation date/time',
        },
    ),
    'contract': (
        'Hợp Đồng (Contract)',
        'contract_template.docx',
        {
            'company_name':         'Company name',
            'contract_number':      'Contract number',
            'contract_date':        'Contract date (dd/mm/yyyy)',
            'quotation_number':     'Referenced quotation number',
            'contract_value':       'Contract value (formatted)',
            'customer_name':        'Customer full name',
            'customer_code':        'Customer code',
            'customer_phone':       'Customer phone',
            'customer_email':       'Customer email',
            'customer_address':     'Customer address',
            'order_code':           'Order code',
            'order_title':          'Order title/description',
            'items':                'List of product items [{stt, name, unit, quantity, unit_price, total, notes}]',
            'terms_and_conditions': 'Contract terms and conditions',
            'notes':                'Contract notes',
            'generated_date':       'Document generation date/time',
        },
    ),
    'delivery': (
        'Biên Bản Bàn Giao (Handover Record)',
        'handover_template.docx',
        {
            'company_name':             'Company name',
            'report_number':            'Handover record number',
            'report_date':              'Record date (dd/mm/yyyy)',
            'handover_date':            'Handover date (dd/mm/yyyy)',
            'customer_name':            'Customer full name',
            'customer_code':            'Customer code',
            'customer_phone':           'Customer phone',
            'customer_address':         'Customer address',
            'order_code':               'Order code',
            'order_title':              'Order title',
            'items':                    'List of handover items [{stt, name, unit, delivered_qty, accepted_qty, accepted, rejection_reason, notes}]',
            'company_representative':   'Company representative name',
            'customer_representative':  'Customer representative name',
            'product_condition':        'Product condition description',
            'notes':                    'Notes',
            'generated_date':           'Document generation date/time',
        },
    ),
    'payment': (
        'Biên Nhận Thanh Toán (Payment Receipt)',
        'payment_template.docx',
        {
            'company_name':          'Company name',
            'report_number':         'Payment receipt number',
            'payment_type':          'Payment type (advance / final)',
            'payment_type_display':  'Payment type display label',
            'report_date':           'Report date (dd/mm/yyyy)',
            'payment_date':          'Payment date (dd/mm/yyyy)',
            'customer_name':         'Customer full name',
            'customer_code':         'Customer code',
            'order_code':            'Order code',
            'order_title':           'Order title',
            'amount':                'Payment amount (formatted)',
            'payment_method':        'Payment method (cash / bank transfer …)',
            'transaction_reference': 'Bank / transaction reference',
            'notes':                 'Notes',
            'generated_date':        'Document generation date/time',
        },
    ),
}


def seed():
    with app.app_context():
        templates_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'templates')

        # Work with every active company
        companies = Company.query.filter_by(is_active=True).all()
        if not companies:
            print('⚠  No active companies found.  Creating templates without company binding.')
            companies = [None]

        for company in companies:
            company_id   = company.id   if company else None
            company_name = company.name if company else '(all companies)'
            print(f'\nCompany: {company_name}')

            for doc_type, (display_name, filename, variables) in TEMPLATES.items():
                file_path = os.path.join(templates_dir, filename)
                if not os.path.exists(file_path):
                    print(f'  ✗  File not found – skipping: {file_path}')
                    print(f'       Run `python create_docx_templates.py` first.')
                    continue

                # Check for existing template
                query = DocumentTemplate.query.filter_by(
                    document_type = doc_type,
                    is_active     = True,
                )
                if company_id:
                    query = query.filter_by(company_id=company_id)
                existing = query.first()

                if existing:
                    existing.template_file    = filename
                    existing.template_content = None   # no longer used for docx templates
                    existing.variables        = variables
                    existing.name             = display_name
                    action = 'Updated'
                else:
                    new_tpl = DocumentTemplate(
                        company_id       = company_id,
                        name             = display_name,
                        document_type    = doc_type,
                        description      = f'Default {display_name} template (DOCX/docxtpl)',
                        template_file    = filename,
                        template_content = None,
                        variables        = variables,
                        is_active        = True,
                    )
                    db.session.add(new_tpl)
                    action = 'Created'

                print(f'  {action}: [{doc_type}] {display_name}  ->  {filename}')

        db.session.commit()
        print('\n✓ All templates seeded successfully.')

        # Summary
        print('\n' + '=' * 60)
        print('Template Summary:')
        print('=' * 60)
        for tpl in DocumentTemplate.query.filter_by(is_active=True).order_by(
                DocumentTemplate.document_type).all():
            print(f'  {tpl.document_type:<12} | {tpl.name:<45} | {tpl.template_file}')


if __name__ == '__main__':
    seed()
