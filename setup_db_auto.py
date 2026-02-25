"""
Automated Database Setup for SofaFlow
Attempts to set up database with common PostgreSQL defaults
"""
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("ERROR: psycopg not installed")
    print("Please run: pip install psycopg")
    sys.exit(1)


def setup_database_auto(postgres_password=None):
    """Attempt automatic database setup"""
    
    print("=" * 70)
    print(" SofaFlow Database Setup - Automated")
    print("=" * 70)
    print()
    
    # Default PostgreSQL settings
    postgres_host = "localhost"
    postgres_port = "5432"
    postgres_user = "postgres"
    db_name = "sofa_flow"
    db_user = "sofa_user"
    db_password = "sofa_password"
    
    # If password not provided, try common credentials
    if postgres_password is None:
        # Try connecting without password first (trusted connection)
        print(f"Attempting to connect to PostgreSQL...")
        print(f"  Host: {postgres_host}")
        print(f"  Port: {postgres_port}")
        print(f"  User: {postgres_user}")
        print()
        
        # Try without password
        try:
            admin_conn = psycopg.connect(
                host=postgres_host,
                port=postgres_port,
                user=postgres_user,
                autocommit=True
            )
            print("✓ Connected to PostgreSQL (trusted connection)")
            postgres_password = None
        except psycopg.OperationalError as e:
            print(f"✗ Cannot connect without password")
            print()
            print("MANUAL SETUP REQUIRED:")
            print("-" * 70)
            print()
            print("Please run setup_db.py with PostgreSQL admin password:")
            print()
            print("  python setup_db.py")
            print()
            print("Or set up database manually using pgAdmin or psql:")
            print()
            print("1. Open pgAdmin or psql")
            print("2. Run setup_db.sql script")
            print()
            print("Or manually run these SQL commands:")
            print()
            print("  CREATE DATABASE sofa_flow;")
            print("  CREATE USER sofa_user WITH PASSWORD 'sofa_password';")
            print("  GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;")
            print()
            print("  -- Connect to sofa_flow database, then run:")
            print("  GRANT USAGE ON SCHEMA public TO sofa_user;")
            print("  GRANT CREATE ON SCHEMA public TO sofa_user;")
            print("  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;")
            print("  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;")
            print()
            sys.exit(1)
    else:
        try:
            admin_conn = psycopg.connect(
                host=postgres_host,
                port=postgres_port,
                user=postgres_user,
                password=postgres_password,
                autocommit=True
            )
            print(f"✓ Connected to PostgreSQL")
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            sys.exit(1)
    
    print()
    print("Setting up database and user...")
    print("-" * 70)
    
    try:
        with admin_conn.cursor() as cur:
            # Create database
            try:
                cur.execute(f"CREATE DATABASE {db_name}")
                print(f"✓ Created database '{db_name}'")
            except psycopg.errors.DuplicateDatabase:
                print(f"✓ Database '{db_name}' already exists")
            
            # Create user
            try:
                cur.execute(
                    f"CREATE USER {db_user} WITH PASSWORD %s",
                    (db_password,)
                )
                print(f"✓ Created user '{db_user}'")
            except psycopg.errors.DuplicateObject:
                print(f"✓ User '{db_user}' already exists")
                # Update password
                cur.execute(f"ALTER USER {db_user} WITH PASSWORD %s", (db_password,))
                print(f"  Password updated")
            
            # Grant permissions
            cur.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user}")
            print(f"✓ Granted database privileges")
    
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        admin_conn.close()
        sys.exit(1)
    
    admin_conn.close()
    
    # Connect to database for schema setup
    try:
        db_conn = psycopg.connect(
            host=postgres_host,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password if postgres_password else None,
            dbname=db_name,
            autocommit=True
        )
    except Exception as e:
        print(f"✗ Failed to connect to {db_name}: {e}")
        sys.exit(1)
    
    try:
        with db_conn.cursor() as cur:
            # Grant schema privileges
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {db_user}")
            cur.execute(f"GRANT CREATE ON SCHEMA public TO {db_user}")
            print(f"✓ Granted schema privileges")
            
            # Set default privileges
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {db_user}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {db_user}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO {db_user}"
            )
            print(f"✓ Set default privileges")
    
    except Exception as e:
        print(f"✗ Failed to grant privileges: {e}")
        db_conn.close()
        sys.exit(1)
    
    db_conn.close()
    
    print()
    print("=" * 70)
    print(" Database Setup Complete!")
    print("=" * 70)
    print()
    print("Environment variable set:")
    print(f"  DATABASE_URL=postgresql+psycopg://{db_user}:{db_password}@{postgres_host}:{postgres_port}/{db_name}")
    print()
    print("Next step - Run database initialization:")
    print(f"  python init_db.py")
    print()


if __name__ == '__main__':
    setup_database_auto()
