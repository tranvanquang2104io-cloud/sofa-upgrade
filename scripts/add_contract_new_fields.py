"""
Migration: Add new fields to contracts table
- amount_in_words: Số tiền bằng chữ
- contract_start_date: Ngày bắt đầu thực hiện hợp đồng
- selected_bank_index: Index ngân hàng thanh toán được chọn
- num_date_notice_cancel: Số ngày báo trước nếu muốn hủy hợp đồng
"""
import sys
import os
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
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS amount_in_words TEXT",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS contract_start_date DATE",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS selected_bank_index INTEGER DEFAULT 0",
                "ALTER TABLE contracts ADD COLUMN IF NOT EXISTS num_date_notice_cancel INTEGER DEFAULT 7",
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

if __name__ == '__main__':
    migrate()
