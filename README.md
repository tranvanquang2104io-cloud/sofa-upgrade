# SofaFlow

SaaS system for managing the customer lifecycle and automating document generation for sofa repair and manufacturing businesses.

## Features

- **Multi-Tenant Architecture**  complete data isolation between companies
- **Order Lifecycle Tracking**  visual timeline from quotation to final payment
- **Customer & Store Management**  multi-store support per company
- **Quotation / Contract / Handover / Payment**  full document workflow with Vietnamese templates
- **Document Generation**  DOCX output via configurable per-company templates
- **Role-Based Access**  `company_admin`, `store_admin`, and `user` roles
- **Bilingual UI**  English / Vietnamese language switcher on every page

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, Flask 2.3, SQLAlchemy 2.0 |
| Database | PostgreSQL 14+ |
| Frontend | Bootstrap 5.3, Vanilla JS |
| Documents | python-docx / docxtpl |
| WSGI | Gunicorn |

## Project Structure

```
sofa-flow/
 app/
    __init__.py            # App factory, context processors
    config/
       config.py          # Flask config classes
       database.py        # SQLAlchemy init
    models/
       models.py          # All ORM models
    repositories/
       repository.py      # Data access layer
    services/
       services.py        # Business logic
    routes/
       auth_routes.py     # /auth/* endpoints
       dashboard_routes.py# All app endpoints
    utils/
       auth_utils.py      # Session / permission helpers
       i18n.py            # EN  VI translation dictionary
       template_engine.py # DOCX variable substitution
    templates/             # Jinja2 HTML templates
    static/                # CSS / JS
    uploads/
        templates/         # DOCX template files
        documents/         # Generated output files
 wsgi.py                    # WSGI entry point
 requirements.txt
 create_master_admin.py     # Bootstrap a master-admin account
 create_sample_data.py      # Populate a full demo environment
 create_docx_templates.py   # Generate starter DOCX template files
 seed_docx_templates.py     # Register DOCX templates in the DB
```

## Quick Start

### 1. Prerequisites

- Python 3.11+
- PostgreSQL 14+

### 2. Clone & Install

```bash
cd sofa-flow

# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Create the Database

Connect to PostgreSQL as a superuser and run:

```sql
CREATE DATABASE sofa_flow;
CREATE USER sofa_user WITH PASSWORD 'sofa_password';
GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;

-- PostgreSQL 15+ also requires:
\c sofa_flow
GRANT USAGE, CREATE ON SCHEMA public TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
```

### 4. Configure Environment

```bash
# Windows
set DATABASE_URL=postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow
set SECRET_KEY=change-me-in-production

# Linux / macOS
export DATABASE_URL=postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow
export SECRET_KEY=change-me-in-production
```

### 5. Initialise & Seed

```bash
# Create tables + default document templates
python create_docx_templates.py
python seed_docx_templates.py

# (Optional) load a full demo dataset
python create_sample_data.py
```

`create_sample_data.py` outputs demo credentials printed to the console.

### 6. Run

```bash
python wsgi.py
#  http://127.0.0.1:5000
```

## Utility Scripts

| Script | Purpose | Run again? |
|--------|---------|-----------|
| `create_master_admin.py` | Create / reset a master-admin account | Yes, safe to re-run |
| `create_sample_data.py` | Populate demo company, stores, users, orders | Yes, creates new records |
| `create_docx_templates.py` | Regenerate starter `.docx` template files on disk | Yes, overwrites files |
| `seed_docx_templates.py` | Register / update template records in the DB | Yes, upserts records |

```bash
# Example: create a master admin with custom credentials
python create_master_admin.py --username myadmin --password "S3cur3!" --name "Admin"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` |  | PostgreSQL connection string (required) |
| `SECRET_KEY` | `dev-secret-key` | Flask session key (change in production) |
| `FLASK_ENV` | `development` | Set to `production` for prod |
| `FLASK_DEBUG` | `True` | Set to `False` in production |
| `FLASK_HOST` | `127.0.0.1` | Bind address |
| `FLASK_PORT` | `5000` | Bind port |

## Order Lifecycle

```
Order Created
     Quotation (draft  approved)
             Contract (draft  signed)
                     Handover Record (draft  confirmed)
                             Advance Payment
                                     Final Payment  Order Complete
```

Each stage generates a DOCX document from a per-company template.

## Language Support

The UI supports English and Vietnamese. Switch via the flag icon in the top-right navbar. All static UI strings are wrapped in `{{ t('...') }}` (Jinja2) and resolved by `app/utils/i18n.py`.

## Production Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for a full guide covering Gunicorn, Nginx, Supervisor, SSL, and backups.
