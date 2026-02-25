# PostgreSQL Permission Error - Quick Fix Guide

## The Problem

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.InsufficientPrivilege) 
permission denied for schema public
```

This means the `sofa_user` account can connect to the database but cannot create tables.

## The Fix (Choose Easiest Option)

### FASTEST OPTION: Using pgAdmin (Recommended for Windows)

1. Open pgAdmin at `http://localhost/pgadmin4`
2. Click on your **sofa_flow** database in the left tree
3. Go to **Tools** > **Query Tool** (or press Alt+E)
4. Run this SQL query exactly:

```sql
GRANT USAGE ON SCHEMA public TO sofa_user;
GRANT CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sofa_user;
```

5. Click **Execute** (F5 or the play button)
6. You should see "Query executed successfully"

### ALTERNATIVE: Using psql Command

Open Command Prompt (Windows) or Terminal:

```bash
psql -U postgres -d sofa_flow
```

Then paste and run these commands:

```sql
GRANT USAGE ON SCHEMA public TO sofa_user;
GRANT CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sofa_user;
```

Then type `\q` to exit.

## Verify It Worked

Run:

```bash
python init_db.py
```

You should see:
```
Creating tables...
✓ Tables created

Creating sample data...
✓ Company created: DEMO
✓ Store created: STORE-001
✓ User created: admin
✓ Document templates created: 4

✓ Database initialization complete!

Demo credentials:
  Company Code: DEMO
  Username: admin
  Password: admin123
```

## If It Still Doesn't Work

1. **Make sure you're connected as postgres (admin) user** - not sofa_user
2. **Make sure you're IN the sofa_flow database** when running the GRANT commands
3. **Check the database exists:** `psql -U postgres -l | grep sofa_flow`
4. **Check the user exists:** `psql -U postgres -c "\du" | grep sofa_user`

## Still Having Issues?

See [DATABASE_SETUP.md](DATABASE_SETUP.md) for more detailed troubleshooting.
