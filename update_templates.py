#!/usr/bin/env python
"""
Script to update document templates with RTF-formatted content
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config.database import db
from app.models import DocumentTemplate  
from datetime import datetime
import logging

# Suppress SQLAlchemy debug logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

def update_templates():
    """Update templates with RTF content"""
    app = create_app('development')
    
    with app.app_context():
        try:
            # Quotation template
            quotation_rtf = r'''{\rtf1\ansi\ansicpg1252\cocoartf2\cuc
{\fonttbl\f0\fswiss Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\margtsxn1440\margbsxn1440\mghdr720\mgft720\headery720\footery720\headsep360\footersep360
\deftab720
\pard\pardeftab720\sl480\partightenfactor100

\f0\fs24 \cf0 {\b QUOTATION}\
\
Quotation Number: {{quotation_number}}\
Date: {{quotation_date}}\
Valid for: {{validity_days}} days\
\
CUSTOMER INFORMATION\
Name: {{customer_name}}\
Code: {{customer_code}}\
Phone: {{customer_phone}}\
Email: {{customer_email}}\
Address: {{customer_address}}\
\
ORDER DETAILS\
Order Code: {{order_code}}\
Title: {{order_title}}\
\
ITEMS\
{{items}}\
\
Total Amount: ${{total_amount}}\
\
Notes:\
{{notes}}\
\
Generated: {{generated_date}}}'''

            contract_rtf = r'''{\rtf1\ansi\ansicpg1252\cocoartf2\cuc
{\fonttbl\f0\fswiss Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\margtsxn1440\margbsxn1440\mghdr720\mgft720\headery720\footery720\headsep360\footersep360
\deftab720
\pard\pardeftab720\sl480\partightenfactor100

\f0\fs24 \cf0 {\b CONTRACT}\
\
Contract Number: {{contract_number}}\
Date: {{contract_date}}\
\
CUSTOMER\
Name: {{customer_name}}\
Code: {{customer_code}}\
Phone: {{customer_phone}}\
Email: {{customer_email}}\
\
ORDER DETAILS\
Order Code: {{order_code}}\
Title: {{order_title}}\
\
CONTRACT TERMS\
Contract Value: ${{contract_value}}\
\
Terms and Conditions:\
{{terms_and_conditions}}\
\
Signature: ____________\
Date: ____________\
\
Generated: {{generated_date}}}'''

            delivery_rtf = r'''{\rtf1\ansi\ansicpg1252\cocoartf2\cuc
{\fonttbl\f0\fswiss Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\margtsxn1440\margbsxn1440\mghdr720\mgft720\headery720\footery720\headsep360\footersep360
\deftab720
\pard\pardeftab720\sl480\partightenfactor100

\f0\fs24 \cf0 {\b DELIVERY REPORT}\
\
Report Number: {{report_number}}\
Report Date: {{report_date}}\
Delivery Date: {{delivery_date}}\
\
CUSTOMER\
Name: {{customer_name}}\
Code: {{customer_code}}\
Address: {{customer_address}}\
\
ORDER DETAILS\
Order Code: {{order_code}}\
Title: {{order_title}}\
\
DELIVERY INFORMATION\
Work Description:\
{{work_description}}\
\
Materials Used:\
{{materials_used}}\
\
Notes:\
{{notes}}\
\
Delivered By: ____________\
Received By: ____________\
\
Generated: {{generated_date}}}'''

            payment_rtf = r'''{\rtf1\ansi\ansicpg1252\cocoartf2\cuc
{\fonttbl\f0\fswiss Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\margtsxn1440\margbsxn1440\mghdr720\mgft720\headery720\footery720\headsep360\footersep360
\deftab720
\pard\pardeftab720\sl480\partightenfactor100

\f0\fs24 \cf0 {\b PAYMENT REPORT}\
\
Report Number: {{report_number}}\
Report Date: {{report_date}}\
Payment Date: {{payment_date}}\
Payment Type: {{payment_type}}\
\
CUSTOMER\
Name: {{customer_name}}\
Code: {{customer_code}}\
\
ORDER DETAILS\
Order Code: {{order_code}}\
Title: {{order_title}}\
\
PAYMENT INFORMATION\
Amount: ${{amount}}\
Payment Method: {{payment_method}}\
Transaction Reference: {{transaction_reference}}\
\
Notes:\
{{notes}}\
\
Received By: ____________\
Date: ____________\
\
Generated: {{generated_date}}}'''

            # Update templates
            print("Starting template updates...")
            
            template = DocumentTemplate.query.filter_by(name='Standard Quotation').first()
            if template:
                template.template_content = quotation_rtf
                template.updated_at = datetime.utcnow()
                db.session.commit()
                print("✓ Updated: Standard Quotation")
            else:
                print("✗ Not found: Standard Quotation")

            template = DocumentTemplate.query.filter_by(name='Standard Contract').first()
            if template:
                template.template_content = contract_rtf
                template.updated_at = datetime.utcnow()
                db.session.commit()
                print("✓ Updated: Standard Contract")
            else:
                print("✗ Not found: Standard Contract")

            template = DocumentTemplate.query.filter_by(name='Standard Delivery Report').first()
            if template:
                template.template_content = delivery_rtf
                template.updated_at = datetime.utcnow()
                db.session.commit()
                print("✓ Updated: Standard Delivery Report")
            else:
                print("✗ Not found: Standard Delivery Report")

            template = DocumentTemplate.query.filter_by(name='Standard Payment Report').first()
            if template:
                template.template_content = payment_rtf
                template.updated_at = datetime.utcnow()
                db.session.commit()
                print("✓ Updated: Standard Payment Report")
            else:
                print("✗ Not found: Standard Payment Report")

            print("\n✓ All templates updated successfully!")
            
        except Exception as e:
            print(f"✗ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    update_templates()

