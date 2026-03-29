"""
Migration: add shipping_fee and another_fee to financial documents
- quotations
- contracts
- handover_records
- payment_reports

Run with project interpreter (Flask app context).
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.config.database import db


def migrate():
    app = create_app()
    with app.app_context():
        conn = db.engine.connect()
        trans = conn.begin()
        try:
            statements = [
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS shipping_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS another_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS shipping_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS another_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE handover_records ADD COLUMN IF NOT EXISTS shipping_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE handover_records ADD COLUMN IF NOT EXISTS another_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE payment_reports ADD COLUMN IF NOT EXISTS shipping_fee NUMERIC(15,2) DEFAULT 0",
                "ALTER TABLE payment_reports ADD COLUMN IF NOT EXISTS another_fee NUMERIC(15,2) DEFAULT 0",
            ]
            for sql in statements:
                print(f"Running: {sql}")
                conn.execute(db.text(sql))
            trans.commit()
            print("Migration completed successfully.")
        except Exception as e:
            trans.rollback()
            print(f"Migration failed: {e}")
            raise
        finally:
            conn.close()


if __name__ == "__main__":
    migrate()
