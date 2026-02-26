"""
Migration script to add cancellation fields to orders table
"""
from app import create_app
from app.config.database import db
from sqlalchemy import text
import sys

def add_order_cancellation_fields():
    """Add is_canceled, canceled_at, and canceled_reason fields to orders table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            result = db.session.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'orders' 
                AND column_name IN ('is_canceled', 'canceled_at', 'canceled_reason')
            """))
            existing_columns = [row[0] for row in result]
            
            if len(existing_columns) == 3:
                print("✓ All cancellation fields already exist in orders table")
                return
            
            print(f"Found {len(existing_columns)} existing columns: {existing_columns}")
            print("Adding missing cancellation fields to orders table...")
            
            # Add is_canceled column if it doesn't exist
            if 'is_canceled' not in existing_columns:
                print("  Adding is_canceled column...")
                db.session.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE
                """))
                print("  ✓ is_canceled added")
            
            # Add canceled_at column if it doesn't exist
            if 'canceled_at' not in existing_columns:
                print("  Adding canceled_at column...")
                db.session.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN canceled_at TIMESTAMP
                """))
                print("  ✓ canceled_at added")
            
            # Add canceled_reason column if it doesn't exist
            if 'canceled_reason' not in existing_columns:
                print("  Adding canceled_reason column...")
                db.session.execute(text("""
                    ALTER TABLE orders 
                    ADD COLUMN canceled_reason TEXT
                """))
                print("  ✓ canceled_reason added")
            
            # Create index on is_canceled if it doesn't exist
            print("  Creating index on is_canceled...")
            try:
                db.session.execute(text("""
                    CREATE INDEX idx_orders_is_canceled 
                    ON orders(is_canceled)
                """))
                print("  ✓ Index created")
            except Exception as e:
                if "already exists" in str(e):
                    print("  ✓ Index already exists")
                else:
                    raise
            
            db.session.commit()
            print("\n✓ Successfully added cancellation fields to orders table")
            
        except Exception as e:
            print(f"\n✗ Error adding cancellation fields: {str(e)}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            sys.exit(1)

if __name__ == '__main__':
    add_order_cancellation_fields()
