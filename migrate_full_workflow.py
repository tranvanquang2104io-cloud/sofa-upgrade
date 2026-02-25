"""
Migration script to update database for comprehensive workflow changes.

This script applies all changes for:
1. Add cancel fields to contracts
2. Add cancel fields to payment reports  
3. Rename delivery_reports table to handover_records and update schema
4. Update lifecycle_statuses: delivery_confirmed -> handover_confirmed
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from app.config.database import db
from app.config.config import Config
from flask import Flask

def create_app():
    """Create Flask app for migration"""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def migrate_contracts_table():
    """Add cancel fields to contracts table"""
    print("\n[1/5] Adding cancel fields to contracts table...")
    
    with db.engine.begin() as connection:
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        contracts_columns = [c['name'] for c in inspector.get_columns('contracts')]
        
        if 'is_canceled' in contracts_columns:
            print("  ✓ Cancel fields already exist in contracts table")
            return
        
        # Add columns
        connection.execute(db.text("""
            ALTER TABLE contracts 
            ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE,
            ADD COLUMN canceled_at TIMESTAMP NULL,
            ADD COLUMN canceled_reason TEXT NULL
        """))
        
        # Add index for is_canceled
        connection.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_contracts_is_canceled 
            ON contracts(is_canceled)
        """))
        
        print("  ✓ Added is_canceled, canceled_at, canceled_reason to contracts")

def migrate_payment_reports_table():
    """Add cancel fields to payment_reports table"""
    print("\n[2/5] Adding cancel fields to payment_reports table...")
    
    with db.engine.begin() as connection:
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        payment_columns = [c['name'] for c in inspector.get_columns('payment_reports')]
        
        if 'is_canceled' in payment_columns:
            print("  ✓ Cancel fields already exist in payment_reports table")
            return
        
        # Add columns
        connection.execute(db.text("""
            ALTER TABLE payment_reports 
            ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE,
            ADD COLUMN canceled_at TIMESTAMP NULL,
            ADD COLUMN canceled_reason TEXT NULL
        """))
        
        # Add index for is_canceled
        connection.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_payment_reports_is_canceled 
            ON payment_reports(is_canceled)
        """))
        
        print("  ✓ Added is_canceled, canceled_at, canceled_reason to payment_reports")

def migrate_delivery_to_handover():
    """Rename delivery_reports to handover_records and update schema"""
    print("\n[3/5] Renaming delivery_reports table to handover_records...")
    
    with db.engine.begin() as connection:
        # Check if handover_records already exists
        inspector = db.inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'handover_records' in tables:
            print("  ✓ handover_records table already exists")
            # Still need to verify columns
            handover_columns = [c['name'] for c in inspector.get_columns('handover_records')]
            
            # Check if new columns exist
            new_columns_needed = [
                'customer_representative', 'company_representative', 
                'product_condition', 'customer_signature_confirmed',
                'is_canceled', 'canceled_at', 'canceled_reason'
            ]
            
            missing_columns = [col for col in new_columns_needed if col not in handover_columns]
            
            if missing_columns:
                print(f"  Adding missing columns: {missing_columns}")
                
                for col in missing_columns:
                    if col == 'customer_representative':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN customer_representative VARCHAR(200) NULL
                        """))
                    elif col == 'company_representative':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN company_representative VARCHAR(200) NULL
                        """))
                    elif col == 'product_condition':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN product_condition TEXT NULL
                        """))
                    elif col == 'customer_signature_confirmed':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN customer_signature_confirmed BOOLEAN DEFAULT FALSE
                        """))
                    elif col == 'is_canceled':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE
                        """))
                    elif col == 'canceled_at':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN canceled_at TIMESTAMP NULL
                        """))
                    elif col == 'canceled_reason':
                        connection.execute(db.text("""
                            ALTER TABLE handover_records 
                            ADD COLUMN canceled_reason TEXT NULL
                        """))
                
                print("  ✓ Added missing columns to handover_records")
            
            # Remove old columns if they exist
            old_columns = ['work_description', 'materials_used']
            existing_old = [col for col in old_columns if col in handover_columns]
            
            if existing_old:
                print(f"  Removing old columns: {existing_old}")
                for col in existing_old:
                    connection.execute(db.text(f"""
                        ALTER TABLE handover_records DROP COLUMN {col}
                    """))
                print("  ✓ Removed old columns from handover_records")
            
            # Rename delivery_date to handover_date if needed
            if 'delivery_date' in handover_columns and 'handover_date' not in handover_columns:
                print("  Renaming delivery_date to handover_date...")
                connection.execute(db.text("""
                    ALTER TABLE handover_records RENAME COLUMN delivery_date TO handover_date
                """))
                print("  ✓ Renamed delivery_date to handover_date")
            
            return
        
        if 'delivery_reports' not in tables:
            print("  ! Neither delivery_reports nor handover_records exists - skipping")
            return
        
        # Rename table
        connection.execute(db.text("""
            ALTER TABLE delivery_reports RENAME TO handover_records
        """))
        
        print("  ✓ Renamed delivery_reports to handover_records")
        
        # Rename and update columns
        print("  Adding/updating columns in handover_records...")
        
        # Rename delivery_date to handover_date
        connection.execute(db.text("""
            ALTER TABLE handover_records RENAME COLUMN delivery_date TO handover_date
        """))
        
        # Add new columns
        connection.execute(db.text("""
            ALTER TABLE handover_records 
            ADD COLUMN customer_representative VARCHAR(200) NULL,
            ADD COLUMN company_representative VARCHAR(200) NULL,
            ADD COLUMN product_condition TEXT NULL,
            ADD COLUMN customer_signature_confirmed BOOLEAN DEFAULT FALSE,
            ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE,
            ADD COLUMN canceled_at TIMESTAMP NULL,
            ADD COLUMN canceled_reason TEXT NULL
        """))
        
        # Remove old columns
        connection.execute(db.text("""
            ALTER TABLE handover_records DROP COLUMN work_description, DROP COLUMN materials_used
        """))
        
        print("  ✓ Updated handover_records schema")

def migrate_lifecycle_statuses_table():
    """Update lifecycle_statuses: delivery_confirmed -> handover_confirmed"""
    print("\n[4/5] Updating lifecycle_statuses table...")
    
    with db.engine.begin() as connection:
        # Check if columns exist
        inspector = db.inspect(db.engine)
        lifecycle_columns = [c['name'] for c in inspector.get_columns('lifecycle_statuses')]
        
        # Check if columns already renamed
        if 'handover_confirmed' in lifecycle_columns:
            print("  ✓ Columns already renamed in lifecycle_statuses")
            return
        
        if 'delivery_confirmed' not in lifecycle_columns:
            print("  ! delivery_confirmed column not found - might have already been renamed")
            return
        
        # Rename columns
        connection.execute(db.text("""
            ALTER TABLE lifecycle_statuses RENAME COLUMN delivery_confirmed TO handover_confirmed
        """))
        
        connection.execute(db.text("""
            ALTER TABLE lifecycle_statuses RENAME COLUMN delivery_confirmed_at TO handover_confirmed_at
        """))
        
        print("  ✓ Renamed delivery_confirmed -> handover_confirmed")
        print("  ✓ Renamed delivery_confirmed_at -> handover_confirmed_at")

def migrate_documents_table():
    """Update documents table: delivery_report_id -> handover_record_id"""
    print("\n[5/5] Updating documents table...")
    
    with db.engine.begin() as connection:
        # Check if columns exist
        inspector = db.inspect(db.engine)
        document_columns = [c['name'] for c in inspector.get_columns('documents')]
        
        # Check if already renamed
        if 'handover_record_id' in document_columns:
            print("  ✓ Columns already renamed in documents")
            
            # Check if old column still exists
            if 'delivery_report_id' in document_columns:
                print("  Removing old delivery_report_id column...")
                connection.execute(db.text("""
                    ALTER TABLE documents DROP COLUMN delivery_report_id
                """))
                print("  ✓ Removed old delivery_report_id column")
            
            return
        
        if 'delivery_report_id' not in document_columns:
            print("  ! delivery_report_id column not found")
            return
        
        # Rename column
        connection.execute(db.text("""
            ALTER TABLE documents RENAME COLUMN delivery_report_id TO handover_record_id
        """))
        
        # Update foreign key constraint (PostgreSQL specific)
        print("  ✓ Renamed delivery_report_id -> handover_record_id")

def main():
    """Run all migrations"""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("SofaFlow Comprehensive Workflow Migration")
        print("=" * 60)
        print(f"Database: {Config.SQLALCHEMY_DATABASE_URI}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        try:
            migrate_contracts_table()
            migrate_payment_reports_table()
            migrate_delivery_to_handover()
            migrate_lifecycle_statuses_table()
            migrate_documents_table()
            
            print("\n" + "=" * 60)
            print("✓ All migrations completed successfully!")
            print("=" * 60)
            print("\nNext steps:")
            print("1. Restart the Flask application")
            print("2. Test order workflow: Quotation → Contract → Payment → Handover → Final Payment")
            print("3. Verify database schema changes")
            
        except Exception as e:
            print(f"\n✗ Migration failed: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()
