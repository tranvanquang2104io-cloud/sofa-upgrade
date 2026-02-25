"""
Database migration script to add contract_created fields to lifecycle_statuses table
Run this script to update the database schema
"""
import os
import sys
import logging
from sqlalchemy import text

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config.database import db
from app import create_app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    """Apply database migration"""
    app = create_app()
    
    with app.app_context():
        try:
            # Get database connection
            connection = db.engine.raw_connection()
            cursor = connection.cursor()
            
            logger.info("Starting database migration...")
            
            # Check if columns already exist
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'lifecycle_statuses' AND column_name = 'contract_created'
            """)
            
            if cursor.fetchone():
                logger.info("Column 'contract_created' already exists, skipping...")
            else:
                logger.info("Adding contract_created column to lifecycle_statuses table...")
                cursor.execute("""
                    ALTER TABLE lifecycle_statuses 
                    ADD COLUMN contract_created BOOLEAN DEFAULT FALSE
                """)
                logger.info("✓ Added contract_created column")
            
            # Check for contract_created_at column
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'lifecycle_statuses' AND column_name = 'contract_created_at'
            """)
            
            if cursor.fetchone():
                logger.info("Column 'contract_created_at' already exists, skipping...")
            else:
                logger.info("Adding contract_created_at column to lifecycle_statuses table...")
                cursor.execute("""
                    ALTER TABLE lifecycle_statuses 
                    ADD COLUMN contract_created_at TIMESTAMP
                """)
                logger.info("✓ Added contract_created_at column")
            
            connection.commit()
            cursor.close()
            connection.close()
            
            logger.info("✅ Database migration completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
