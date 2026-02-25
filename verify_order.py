import logging
import sys
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)

try:
    from app import create_app
    from app.config.database import db
    from app.models import Order, LifecycleStatus, Quotation

    app = create_app('development')
    with app.app_context():
        # Find the order
        order = Order.query.filter_by(order_code='ORD-001').first()
        if order:
            print(f"Order: {order.order_code}")
            print(f"Order ID: {order.id}")
            
            # Check lifecycle status
            lifecycle = LifecycleStatus.query.filter_by(order_id=order.id).first()
            if lifecycle:
                print(f"\nLifecycle Status:")
                print(f"  quotation_created: {lifecycle.quotation_created}")
                print(f"  quotation_created_at: {lifecycle.quotation_created_at}")
            else:
                print("No lifecycle status found!")
            
            # Check quotations
            quotations = Quotation.query.filter_by(order_id=order.id).all()
            print(f"\nQuotations: {len(quotations)}")
            for q in quotations:
                print(f"  - {q.quotation_number} (amount: ${q.total_amount})")
        else:
            print("Order ORD-001 not found")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
