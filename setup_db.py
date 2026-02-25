"""
Database setup script for SofaFlow
Configures PostgreSQL database and user with proper permissions
"""
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg is not installed. Please run: pip install psycopg")
    sys.exit(1)


def setup_database():
    """Set up SofaFlow database with proper permissions"""
    
    print("=" * 60)
    print(" SofaFlow Database Setup")
    print("=" * 60)
    print()
    
    # Get PostgreSQL connection details
    print("PostgreSQL Connection Details:")
    print("-" * 60)
    
    postgres_host = input("PostgreSQL Host [localhost]: ").strip() or "localhost"
    postgres_port = input("PostgreSQL Port [5432]: ").strip() or "5432"
    postgres_user = input("PostgreSQL Admin User [postgres]: ").strip() or "postgres"
    postgres_password = input("PostgreSQL Admin Password: ").strip()
    
    print()
    print("SofaFlow Configuration:")
    print("-" * 60)
    
    db_name = "sofa_flow"
    db_user = "sofa_user"
    db_password = "sofa_password"
    
    print(f"Database Name: {db_name}")
    print(f"Database User: {db_user}")
    print()
    
    # Connect as admin
    try:
        print(f"Connecting to PostgreSQL as {postgres_user}...")
        admin_conn = psycopg.connect(
            host=postgres_host,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            autocommit=True
        )
        print("✓ Connected successfully")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        print()
        print("Troubleshooting:")
        print("1. Verify PostgreSQL is running")
        print("2. Check the host and port are correct")
        print("3. Verify PostgreSQL admin credentials")
        sys.exit(1)
    
    print()
    print("Setting up database...")
    print("-" * 60)
    
    try:
        with admin_conn.cursor() as cur:
            # Check if database exists
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,)
            )
            db_exists = cur.fetchone() is not None
            
            if db_exists:
                print(f"✓ Database '{db_name}' already exists")
            else:
                print(f"  Creating database '{db_name}'...")
                cur.execute(f"CREATE DATABASE {db_name}")
                print(f"✓ Database '{db_name}' created")
            
            # Check if user exists
            cur.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (db_user,)
            )
            user_exists = cur.fetchone() is not None
            
            if user_exists:
                print(f"✓ User '{db_user}' already exists")
                # Update password anyway
                print(f"  Updating password for '{db_user}'...")
                cur.execute(
                    f"ALTER USER {db_user} WITH PASSWORD %s",
                    (db_password,)
                )
                print(f"✓ Password updated")
            else:
                print(f"  Creating user '{db_user}'...")
                cur.execute(
                    f"CREATE USER {db_user} WITH PASSWORD %s",
                    (db_password,)
                )
                print(f"✓ User '{db_user}' created")
            
            # Grant database privileges
            print(f"  Granting database privileges...")
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user}")
            print(f"✓ Database privileges granted")
    
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        admin_conn.close()
        sys.exit(1)
    
    admin_conn.close()
    
    # Connect to the database to set schema privileges
    try:
        print()
        print(f"Connecting to '{db_name}' database...")
        db_conn = psycopg.connect(
            host=postgres_host,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            dbname=db_name,
            autocommit=True
        )
        print("✓ Connected successfully")
    except Exception as e:
        print(f"✗ Connection to {db_name} failed: {e}")
        sys.exit(1)
    
    try:
        with db_conn.cursor() as cur:
            print(f"  Granting schema privileges...")
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {db_user}")
            cur.execute(f"GRANT CREATE ON SCHEMA public TO {db_user}")
            print(f"✓ Schema privileges granted")
            
            print(f"  Setting default privileges...")
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {db_user}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {db_user}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO {db_user}"
            )
            print(f"✓ Default privileges set")
    
    except Exception as e:
        print(f"✗ Failed to grant schema privileges: {e}")
        db_conn.close()
        sys.exit(1)
    
    db_conn.close()
    
    print()
    print("=" * 60)
    print(" Database Setup Complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"1. Set environment variable:")
    print(f"   set DATABASE_URL=postgresql+psycopg://{db_user}:{db_password}@{postgres_host}:{postgres_port}/{db_name}")
    print()
    print(f"2. Run database initialization:")
    print(f"   python init_db.py")
    print()


if __name__ == '__main__':
    setup_database()
