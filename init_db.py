"""
Database initialization script - sets up initial templates and sample data
"""
import os
import sys
from datetime import datetime, date

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config.database import db
from app.models import Company, Store, User, DocumentTemplate
from app.services.services import UserService, CompanyService, StoreService

def init_database():
    """Initialize database with sample data"""
    
    app = create_app('development')
    
    with app.app_context():
        print("Creating tables...")
        db.create_all()
        print("✓ Tables created")
        
        # Check if demo data exists
        existing_company = Company.query.filter_by(company_code='DEMO').first()
        if existing_company:
            print("✓ Demo company already exists, skipping sample data creation")
            return
        
        print("\nCreating sample data...")
        
        # Create sample company
        company_service = CompanyService()
        company = company_service.create_company(
            company_code='DEMO',
            name='Demo Sofa Company',
            email='demo@sofaflow.local',
            phone='555-0001',
            address='123 Main St',
            city='Demo City',
            country='Demo Country'
        )
        print(f"✓ Company created: {company.company_code}")
        
        # Create sample store
        store_service = StoreService()
        store = store_service.create_store(
            company_id=company.id,
            store_code='STORE-001',
            name='Main Store',
            manager_name='John Manager',
            phone='555-0001',
            address='123 Main St',
            city='Demo City'
        )
        print(f"✓ Store created: {store.store_code}")
        
        # Create admin user
        user_service = UserService()
        user = user_service.create_user(
            company_id=company.id,
            username='admin',
            email='admin@sofaflow.local',
            password='admin123',
            full_name='Admin User',
            role='admin'
        )
        print(f"✓ User created: {user.username}")
        
        # Create sample document templates
        quotation_template = DocumentTemplate.query.filter_by(
            company_id=company.id,
            document_type='quotation'
        ).first()
        
        if not quotation_template:
            templates_data = [
                {
                    'name': 'Standard Quotation',
                    'document_type': 'quotation',
                    'template_content': '''QUOTATION

Quotation Number: {{quotation_number}}
Date: {{quotation_date}}
Valid for: {{validity_days}} days

CUSTOMER INFORMATION
Name: {{customer_name}}
Code: {{customer_code}}
Phone: {{customer_phone}}
Email: {{customer_email}}
Address: {{customer_address}}

ORDER DETAILS
Order Code: {{order_code}}
Title: {{order_title}}

ITEMS
{{items}}

Total Amount: ${{total_amount}}

Notes:
{{notes}}

Generated: {{generated_date}}
''',
                },
                {
                    'name': 'Standard Contract',
                    'document_type': 'contract',
                    'template_content': '''CONTRACT

Contract Number: {{contract_number}}
Date: {{contract_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}
Phone: {{customer_phone}}
Email: {{customer_email}}

ORDER DETAILS
Order Code: {{order_code}}
Title: {{order_title}}
Contract Value: ${{contract_value}}

TERMS AND CONDITIONS
{{terms_and_conditions}}

Generated: {{generated_date}}
''',
                },
                {
                    'name': 'Standard Delivery Report',
                    'document_type': 'delivery',
                    'template_content': '''DELIVERY REPORT

Report Number: {{report_number}}
Report Date: {{report_date}}
Delivery Date: {{delivery_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}

ORDER
Order Code: {{order_code}}
Title: {{order_title}}

WORK DESCRIPTION
{{work_description}}

MATERIALS USED
{{materials_used}}

Notes:
{{notes}}

Generated: {{generated_date}}
''',
                },
                {
                    'name': 'Standard Payment Report',
                    'document_type': 'payment',
                    'template_content': '''PAYMENT REPORT

Report Number: {{report_number}}
Payment Type: {{payment_type}}
Report Date: {{report_date}}
Payment Date: {{payment_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}

ORDER
Order Code: {{order_code}}
Title: {{order_title}}

PAYMENT DETAILS
Amount: ${{amount}}
Payment Method: {{payment_method}}
Transaction Reference: {{transaction_reference}}

Notes:
{{notes}}

Generated: {{generated_date}}
''',
                },
            ]
            
            for template_data in templates_data:
                template = DocumentTemplate(
                    company_id=company.id,
                    name=template_data['name'],
                    document_type=template_data['document_type'],
                    template_content=template_data['template_content']
                )
                db.session.add(template)
            
            db.session.commit()
            print(f"✓ Document templates created: {len(templates_data)}")
        
        print("\n✓ Database initialization complete!")
        print("\nDemo credentials:")
        print("  Company Code: DEMO")
        print("  Username: admin")
        print("  Password: admin123")

if __name__ == '__main__':
    init_database()
