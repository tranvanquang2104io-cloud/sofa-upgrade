"""Simple migration to add cancellation fields to orders"""
import psycopg2

# Get database connection (from app config default)
db_url = 'postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow'
# Convert SQLAlchemy URL to psycopg2 format
db_url = db_url.replace('postgresql+psycopg://', 'postgresql://')

conn = psycopg2.connect(db_url)
conn.autocommit = False
cur = conn.cursor()

try:
    # Check existing columns
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'orders' 
        AND column_name IN ('is_canceled', 'canceled_at', 'canceled_reason')
    """)
    existing = [row[0] for row in cur.fetchall()]
    print(f"Existing columns: {existing}")
    
    if len(existing) == 3:
        print("All columns exist!")
        conn.close()
        exit(0)
    
    # Add missing columns
    if 'is_canceled' not in existing:
        print("Adding is_canceled...")
        cur.execute("ALTER TABLE orders ADD COLUMN is_canceled BOOLEAN DEFAULT FALSE")
        print("✓ Added is_canceled")
    
    if 'canceled_at' not in existing:
        print("Adding canceled_at...")
        cur.execute("ALTER TABLE orders ADD COLUMN canceled_at TIMESTAMP")
        print("✓ Added canceled_at")
    
    if 'canceled_reason' not in existing:
        print("Adding canceled_reason...")
        cur.execute("ALTER TABLE orders ADD COLUMN canceled_reason TEXT")
        print("✓ Added canceled_reason")
    
    # Create index
    try:
        print("Creating index...")
        cur.execute("CREATE INDEX idx_orders_is_canceled ON orders(is_canceled)")
        print("✓ Created index")
    except Exception as e:
        if "already exists" in str(e):
            print("✓ Index already exists")
        else:
            raise
    
    conn.commit()
    print("\n✓ Migration completed successfully!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
