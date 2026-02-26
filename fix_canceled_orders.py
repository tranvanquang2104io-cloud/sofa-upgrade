"""Fix canceled orders to be visible in the list"""
from app import create_app
from app.models.models import Order
from app.config.database import db

app = create_app()

with app.app_context():
    # Find canceled orders that are marked as inactive
    canceled_orders = Order.query.filter_by(is_canceled=True, is_active=False).all()
    
    print(f"Found {len(canceled_orders)} canceled orders with is_active=False")
    
    for order in canceled_orders:
        print(f"  - Updating order {order.order_code}")
        order.is_active = True
    
    db.session.commit()
    print("✓ All canceled orders updated to be active")
    
    # Verify
    all_canceled = Order.query.filter_by(is_canceled=True).all()
    print(f"\nTotal canceled orders: {len(all_canceled)}")
    for order in all_canceled:
        print(f"  - {order.order_code}: is_active={order.is_active}, is_canceled={order.is_canceled}")
