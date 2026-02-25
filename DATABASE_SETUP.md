# Database Setup Instructions for SofaFlow

## Problem
Your PostgreSQL user `sofa_user` doesn't have permission to create tables in the `public` schema.

## Solution 

Choose ONE of the options below:

### Option 1: Using pgAdmin (Easiest - Graphical)

1. Open pgAdmin (usually at http://localhost/pgadmin4)
2. Right-click on "Servers" and select "Register > Server"
3. Enter connection details:
   - Name: `sofa_flow_setup`
   - Host: `localhost`
   - Port: `5432`
   - Username: `postgres`
   - Password: (your PostgreSQL admin password)

4. Once connected, go to your `sofa_flow` database
5. Click on "Query Tool" (or Tools > Query Tool)
6. Copy and paste this SQL and execute it:

```sql
-- Run these commands to fix permissions
GRANT USAGE ON SCHEMA public TO sofa_user;
GRANT CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sofa_user;
```

7. Once complete, you can run: `python init_db.py`

### Option 2: Using Command Line (psql)

Open Command Prompt or PowerShell:

```bash
# First, as postgres user, set up the initial database and user
psql -U postgres -c "CREATE DATABASE sofa_flow;"
psql -U postgres -c "CREATE USER sofa_user WITH PASSWORD 'sofa_password';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;"

# Then, as postgres user, grant schema permissions
psql -U postgres -d sofa_flow -f setup_db.sql
```

Or all in one command (you'll be prompted for the postgres password):

```bash
psql -U postgres -d sofa_flow << EOF
GRANT USAGE ON SCHEMA public TO sofa_user;
GRANT CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sofa_user;
EOF
```

### Option 3: Using the Shell Script

Save your postgres password in an environment variable and run:

```bash
# Set the postgres password
set PGPASSWORD=your_postgres_password

# Run the SQL setup
psql -U postgres -d sofa_flow -f setup_db.sql

# Clear the password
set PGPASSWORD=
```

### Option 4: Using Python (if you know the postgres password)

```bash
# Create a .env file with:
POSTGRES_PASSWORD=your_actual_postgres_password

# Then run:
python setup_db.py
```

## After You Fix the Permissions

Set the environment variable:

```bash
set DATABASE_URL=postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow
```

Then run the initialization:

```bash
python init_db.py
```

## Still Having Issues?

### Check PostgreSQL Status
```bash
# Verify PostgreSQL is running (Windows Services)
sc query PostgreSQL14  # or PostgreSQL13, PostgreSQL15, etc.
```

### Verify Database Exists
```bash
psql -U postgres -l  # List all databases
```

### Verify User Exists and Permissions
```bash
psql -U postgres -d sofa_flow -c "\du"  # List users and roles
psql -U postgres -d sofa_flow -c "\dn+"  # List schemas and permissions
```

### Full Database Reinit
If you want to start fresh:

```bash
# As postgres user:
psql -U postgres -c "DROP DATABASE sofa_flow;"
psql -U postgres -c "DROP USER sofa_user;"

# Then recreate using one of the options above
```

## Quick Verification

After fixing permissions, verify with:

```bash
python -c "
import psycopg
conn = psycopg.connect('postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow')
print('Database connection: OK')
with conn.cursor() as cur:
    cur.execute('CREATE TABLE test (id INT); DROP TABLE test;')
print('Create table permission: OK')
conn.close()
"
```
