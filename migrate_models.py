#!/usr/bin/env python
"""
Database migration script to add new columns and constraints for quotation/contract management
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'development')

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from app.config.database import db

def migrate():
    """Apply database migrations"""
    from app import create_app
    app = create_app()
    
    with app.app_context():
        print("Starting database migration...")
        print()
        
        try:
            # Add new columns to quotations table
            print("1. Adding new columns to quotations table...")
            migration_sql = [
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS is_canceled BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS canceled_at TIMESTAMP;",
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS canceled_reason TEXT;",
            ]
            
            for sql in migration_sql:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"   OK: {sql}")
                except Exception as e:
                    print(f"   SKIP: {sql} - {str(e)}")
            
            print()
            print("2. Adding new columns to contracts table...")
            contract_sql = [
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS items JSON DEFAULT '[]';",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",
            ]
            
            for sql in contract_sql:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"   OK: {sql}")
                except Exception as e:
                    print(f"   SKIP: {sql} - {str(e)}")
            
            print()
            print("3. Creating unique constraints...")
            constraint_sql = [
                """ALTER TABLE quotations 
                   ADD CONSTRAINT uq_order_active_quotation 
                   UNIQUE (order_id) 
                   WHERE is_active = true;""",
                """ALTER TABLE contracts 
                   ADD CONSTRAINT uq_order_active_contract 
                   UNIQUE (order_id) 
                   WHERE is_active = true;""",
            ]
            
            for sql in constraint_sql:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"   OK: Constraint created")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print(f"   SKIP: Constraint already exists")
                    else:
                        print(f"   ERROR: {str(e)}")
            
            print()
            print("4. Adding indexes...")
            index_sql = [
                "CREATE INDEX IF NOT EXISTS idx_quotations_order_active ON quotations(order_id, is_active);",
                "CREATE INDEX IF NOT EXISTS idx_contracts_order_active ON contracts(order_id, is_active);",
            ]
            
            for sql in index_sql:
                try:
                    db.session.execute(text(sql))
                    db.session.commit()
                    print(f"   OK: {sql}")
                except Exception as e:
                    print(f"   SKIP: {sql} - {str(e)}")
            
            print()
            print("=" * 80)
            print("MIGRATION COMPLETE")
            print("=" * 80)
            print()
            print("Summary of changes:")
            print("- Added is_active, is_canceled, canceled_at, canceled_reason to quotations")
            print("- Added items, is_active to contracts")
            print("- Added unique constraints for one active quotation/contract per order")
            print("- Added indexes for query optimization")
            print()
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate()
