#!/usr/bin/env python
"""
Comprehensive diagnostic script to identify lifecycle status update issues
Thisscript will:
1. Check if the quotation creation code has the lifecycle fix
2. Verify the database has lifecycle records
3. Trace through a quotation creation to ensure all updates are persisted
"""

import os
import sys
from datetime import datetime, date

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_DEBUG', 'True')

from app import create_app
from app.config.database import db
from app.models import Order, LifecycleStatus, Quotation
from app.services.services import QuotationService, OrderService
from app.repositories.repository import LifecycleStatusRepository

def check_code_has_fix():
    """Check if services.py has the db.session.add(lifecycle) fix"""
    with open('app/services/services.py', 'r') as f:
        content = f.read()
        
    print("=" * 80)
    print("1. CHECKING CODE FOR LIFECYCLE FIX")
    print("=" * 80)
    
    # Look for the db.session.add(lifecycle) in create_quotation
    if 'db.session.add(lifecycle)' in content:
        print("✓ GOOD: db.session.add(lifecycle) found in code")
        
        # Count how many times it appears
        count = content.count('db.session.add(lifecycle)')
        print(f"  Found {count} occurrences of db.session.add(lifecycle)")
        
        # Check specifically in create_quotation
        section_start = content.find('def create_quotation')
        section_end = content.find('def get_quotation')
        if section_start != -1 and section_end != -1:
            create_quotation_code = content[section_start:section_end]
            if 'db.session.add(lifecycle)' in create_quotation_code:
                print("✓ GOOD: db.session.add(lifecycle) found in create_quotation method")
            else:
                print("✗ ERROR: db.session.add(lifecycle) NOT found in create_quotation method")
    else:
        print("✗ ERROR: db.session.add(lifecycle) NOT found in code")
    
    print()

def check_database_state():
    """Check current database state"""
    print("=" * 80)
    print("2. CHECKING DATABASE STATE")
    print("=" * 80)
    
    app = create_app()
    with app.app_context():
        # Get all orders
        orders = Order.query.all()
        print(f"Total orders in database: {len(orders)}")
        
        for order in orders[:5]:  # Show first 5 orders
            print(f"\nOrder: {order.order_code} (ID: {order.id})")
            print(f"  Created: {order.created_at}")
            print(f"  Total Amount: {order.total_amount}")
            
            # Check lifecycle
            if order.lifecycle:
                lifecycle = order.lifecycle
                print(f"  Lifecycle Status:")
                print(f"    quotation_created: {lifecycle.quotation_created} (at {lifecycle.quotation_created_at})")
                print(f"    quotation_approved: {lifecycle.quotation_approved}")
                print(f"    contract_signed: {lifecycle.contract_signed}")
                print(f"    delivery_confirmed: {lifecycle.delivery_confirmed}")
            else:
                print(f"  ✗ NO LIFECYCLE RECORD FOUND")
            
            # Check quotations
            quotations = Quotation.query.filter_by(order_id=order.id).all()
            print(f"  Quotations: {len(quotations)}")
            for q in quotations:
                print(f"    - {q.quotation_number} (Amount: {q.total_amount}, Created: {q.created_at})")
    
    print()

def test_quotation_creation_flow():
    """Test creating a quotation and trace the lifecycle update"""
    print("=" * 80)
    print("3. TESTING QUOTATION CREATION FLOW")
    print("=" * 80)
    
    app = create_app()
    with app.app_context():
        try:
            # Get first order or create one
            order = Order.query.first()
            if not order:
                print("✗ No orders in database. Create an order first.")
                return
            
            print(f"Using order: {order.order_code} (ID: {order.id})")
            
            # Check lifecycle before creation
            lifecycle_before = LifecycleStatus.query.filter_by(order_id=order.id).first()
            if lifecycle_before:
                quotation_created_before = lifecycle_before.quotation_created
                print(f"Before: quotation_created = {quotation_created_before}")
            else:
                print(f"Before: NO LIFECYCLE RECORD")
                quotation_created_before = None
            
            # Create a quotation
            quotation_service = QuotationService()
            test_items = [
                {'name': 'Test Item', 'quantity': 1, 'unit_price': 100, 'total': 100}
            ]
            
            test_quotation_number = f"TEST-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            print(f"\nCreating quotation: {test_quotation_number}")
            
            quotation = quotation_service.create_quotation(
                order_id=order.id,
                quotation_number=test_quotation_number,
                quotation_date=date.today(),
                items=test_items,
                total_amount=100,
                validity_days=30,
                notes="Test quotation for diagnostics"
            )
            
            print(f"✓ Quotation created: {quotation.quotation_number}")
            
            # Check lifecycle after creation (fresh query from database)
            print("\nQuerying database after creation...")
            db.session.expunge_all()  # Clear session cache
            
            lifecycle_after = LifecycleStatus.query.filter_by(order_id=order.id).first()
            if lifecycle_after:
                quotation_created_after = lifecycle_after.quotation_created
                print(f"After: quotation_created = {quotation_created_after}")
                print(f"After: quotation_created_at = {lifecycle_after.quotation_created_at}")
                
                if quotation_created_before is not None:
                    if quotation_created_before != quotation_created_after:
                        print(f"✓ GOOD: Lifecycle status CHANGED from {quotation_created_before} to {quotation_created_after}")
                    else:
                        print(f"✗ ERROR: Lifecycle status UNCHANGED (still {quotation_created_before})")
                else:
                    print(f"✓ Lifecycle status: {quotation_created_after}")
            else:
                print(f"✗ ERROR: NO LIFECYCLE RECORD FOUND AFTER CREATION")
            
            # Also check the order object's lifecycle relationship
            print("\nChecking order.lifecycle relationship...")
            db.session.expunge_all()  # Clear session cache
            order_fresh = Order.query.filter_by(id=order.id).first()
            if order_fresh and order_fresh.lifecycle:
                print(f"✓ Order has lifecycle relationship")
                print(f"  quotation_created: {order_fresh.lifecycle.quotation_created}")
            else:
                print(f"✗ ERROR: Order lifecycle relationship missing")
                
        except Exception as e:
            print(f"✗ ERROR during test: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print()

def check_repository_methods():
    """Check that repository methods are working correctly"""
    print("=" * 80)
    print("4. CHECKING REPOSITORY METHODS")
    print("=" * 80)
    
    app = create_app()
    with app.app_context():
        try:
            repo = LifecycleStatusRepository()
            
            # Get first order
            order = Order.query.first()
            if not order:
                print("No orders found")
                return
            
            print(f"Testing LifecycleStatusRepository with order: {order.order_code}")
            
            # Test get_for_order
            lifecycle = repo.get_for_order(order.id)
            if lifecycle:
                print(f"✓ get_for_order returned: {lifecycle}")
                print(f"  quotation_created: {lifecycle.quotation_created}")
            else:
                print(f"✗ get_for_order returned None")
            
            # Test get_or_create_for_order
            print(f"\nTesting get_or_create_for_order...")
            lifecycle2 = repo.get_or_create_for_order(order.id)
            print(f"✓ get_or_create_for_order returned: {lifecycle2}")
            
        except Exception as e:
            print(f"✗ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
    
    print()

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("LIFECYCLE STATUS DIAGNOSTIC REPORT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now()}\n")
    
    try:
        check_code_has_fix()
        check_database_state()
        check_repository_methods()
        test_quotation_creation_flow()
        
        print("=" * 80)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
