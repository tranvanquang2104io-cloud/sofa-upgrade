"""Fix foreign key constraint on documents table"""
from app import create_app
from app.config.database import db
from app.config.config import Config

def fix_foreign_key_constraint():
    """Update foreign key constraint to reference handover_records"""
    app = create_app()
    
    with app.app_context():
        print("Checking and fixing foreign key constraint...")
        
        with db.engine.begin() as connection:
            # Check current foreign keys
            inspector = db.inspect(db.engine)
            fks = inspector.get_foreign_keys('documents')
            
            print("\nCurrent foreign keys on documents table:")
            for fk in fks:
                print(f"  - {fk['name']}: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}")
            
            # Check if there's a foreign key pointing to delivery_reports
            has_old_fk = any(fk.get('referred_table') == 'delivery_reports' for fk in fks)
            has_new_fk = any(fk.get('referred_table') == 'handover_records' for fk in fks)
            
            if has_old_fk:
                print("\n✗ Found old foreign key referencing delivery_reports")
                print("  Dropping old constraint...")
                
                # Drop old foreign key constraint
                connection.execute(db.text("""
                    ALTER TABLE documents DROP CONSTRAINT IF EXISTS documents_delivery_report_id_fkey
                """))
                
                print("  ✓ Dropped old constraint")
            
            if not has_new_fk:
                print("\n  Creating new foreign key constraint...")
                
                # Create new foreign key constraint
                connection.execute(db.text("""
                    ALTER TABLE documents 
                    ADD CONSTRAINT documents_handover_record_id_fkey 
                    FOREIGN KEY (handover_record_id) REFERENCES handover_records(id) ON DELETE CASCADE
                """))
                
                print("  ✓ Created new constraint referencing handover_records")
            else:
                print("\n✓ Foreign key constraint is already correct")
            
            print("\n" + "=" * 60)
            print("✓ Foreign key constraint fix completed!")
            print("=" * 60)

if __name__ == '__main__':
    fix_foreign_key_constraint()
