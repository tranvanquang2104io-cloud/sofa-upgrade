import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

from app import create_app
from app.config.database import db
from app.models import Order, LifecycleStatus, Quotation
from datetime import datetime

app = create_app('development')
with app.app_context():
    # Find the order
    order = Order.query.filter_by(order_code='ORD-001').first()
    if order:
        print(f"Updating order: {order.order_code}")
        
        # Get or create lifecycle status
        lifecycle = LifecycleStatus.query.filter_by(order_id=order.id).first()
        if lifecycle:
            # Check current state
            print(f"\nBefore update:")
            print(f"  quotation_created: {lifecycle.quotation_created}")
            print(f"  quotation_created_at: {lifecycle.quotation_created_at}")
            
            # Update lifecycle
            lifecycle.quotation_created = True
            lifecycle.quotation_created_at = datetime.utcnow()
            db.session.add(lifecycle)
            db.session.commit()
            
            print(f"\nAfter update:")
            print(f"  quotation_created: {lifecycle.quotation_created}")
            print(f"  quotation_created_at: {lifecycle.quotation_created_at}")
            
            # Verify quotations exist
            quotations = Quotation.query.filter_by(order_id=order.id).all()
            print(f"\nQuotations: {len(quotations)}")
            for q in quotations:
                print(f"  - {q.quotation_number}")
            
            print("\n[OK] Lifecycle status updated successfully!")
        else:
            print("No lifecycle status found!")
    else:
        print("Order ORD-001 not found")
