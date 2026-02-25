#!/usr/bin/env python
"""
Simple test to verify lifecycle status is updating correctly
"""
import os
import sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from app.models import Order, LifecycleStatus, Quotation
from app.services.services import QuotationService

print("=" * 80)
print("TESTING LIFECYCLE STATUS UPDATE")
print("=" * 80)
print()

app = create_app()
with app.app_context():
    try:
        # Get first order
        order = Order.query.first()
        if not order:
            print("ERROR: No orders in database")
            sys.exit(1)
        
        print(f"Order: {order.order_code} (ID: {order.id})")
        print()
        
        # Check lifecycle before
        print("BEFORE quotation creation:")
        if order.lifecycle:
            print(f"  lifecycle.quotation_created = {order.lifecycle.quotation_created}")
        else:
            print("  lifecycle = NONE")
        print()
        
        # Create quotation
        quotation_service = QuotationService()
        test_number = f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        print(f"Creating quotation: {test_number}")
        quotation = quotation_service.create_quotation(
            order_id=order.id,
            quotation_number=test_number,
            quotation_date=date.today(),
            items=[{'name': 'Item', 'quantity': 1, 'unit_price': 100, 'total': 100}],
            total_amount=100,
            validity_days=30
        )
        print("Created successfully")
        print()
        
        # Check lifecycle after (fresh query)
        print("AFTER quotation creation (fresh query from DB):")
        from app.config.database import db
        db.session.expunge_all()  # Clear cache
        
        order_fresh = Order.query.filter_by(id=order.id).first()
        if order_fresh.lifecycle:
            print(f"  lifecycle.quotation_created = {order_fresh.lifecycle.quotation_created}")
            print(f"  SUCCESS: Lifecycle status updated!")
        else:
            print("  ERROR: lifecycle = NONE")
        
        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
