# SofaFlow - Customer Lifecycle and Document Management SaaS

A production-ready SaaS system for managing customer lifecycle and automated document generation for sofa repair and manufacturing businesses.

## Features

### Core Features
- **Multi-Tenant Architecture**: Complete data isolation between companies
- **Customer Management**: Create, edit, and manage customer information
- **Order Lifecycle Tracking**: Visual timeline of customer orders from quotation to final payment
- **Quotation Management**: Create and manage quotations with automatic calculation
- **Contract Management**: Generate contracts from approved quotations
- **Delivery Reports**: Track work completion and delivery
- **Payment Management**: Track advance and final payments
- **Document Generation**: Automatic PDF/DOCX generation from configurable templates
- **Role-Based Access**: Admin and user roles with appropriate permissions

### Technical Architecture
- **Backend**: Python Flask with SQLAlchemy ORM
- **Database**: PostgreSQL with multi-tenant design
- **Frontend**: Bootstrap 5 responsive UI
- **Document Engine**: Python-docx for DOCX generation, ReportLab for PDF
- **Template System**: RTF-based template with variable substitution
- **Authentication**: Session-based with password hashing

## Project Structure

```
sofa-flow/
├── app/
│   ├── config/              # Configuration management
│   │   ├── config.py       # Flask configuration
│   │   └── database.py     # Database initialization
│   ├── models/              # SQLAlchemy models
│   │   └── models.py       # All database models
│   ├── repositories/        # Data access layer
│   │   └── repository.py   # Repository pattern implementation
│   ├── services/           # Business logic layer
│   │   └── services.py     # Service layer for all features
│   ├── routes/             # Flask blueprints
│   │   ├── auth_routes.py     # Authentication routes
│   │   └── dashboard_routes.py # Main application routes
│   ├── utils/              # Utility functions
│   │   ├── auth_utils.py       # Authentication helpers
│   │   └── template_engine.py  # Document template engine
│   ├── templates/          # Jinja2 templates
│   ├── static/             # CSS, JavaScript, images
│   ├── uploads/            # File storage
│   │   ├── templates/      # RTF templates
│   │   └── documents/      # Generated documents
│   └── __init__.py        # Flask app factory
├── migrations/             # Database migrations
├── init_db.py             # Database initialization script
├── wsgi.py                # WSGI entry point
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Database Schema

### Core Tables
- **companies**: Multi-tenant companies/organizations
- **stores**: Stores within each company
- **users**: Application users
- **customers**: Customer information
- **orders**: Customer orders (lifecycle tracking)
- **lifecycle_statuses**: Order status at each stage

### Document Tables
- **quotations**: Quotation information
- **contracts**: Contract information
- **delivery_reports**: Delivery/completion reports
- **payment_reports**: Payment tracking (advance, final)
- **documents**: Generated document records
- **document_templates**: RTF templates for document generation

## Installation & Setup

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- LibreOffice (optional, for advanced PDF generation)

### Step 1: Clone and Setup Virtual Environment

```bash
cd sofa-flow
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Database

Create a PostgreSQL database:

```sql
CREATE DATABASE sofa_flow;
CREATE USER sofa_user WITH PASSWORD 'sofa_password';
GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;
```

Set environment variable (Windows):
```bash
set DATABASE_URL=postgresql://sofa_user:sofa_password@localhost:5432/sofa_flow
```

Or Linux/Mac:
```bash
export DATABASE_URL=postgresql://sofa_user:sofa_password@localhost:5432/sofa_flow
```

### Step 4: Initialize Database

```bash
python init_db.py
```

This will:
- Create all database tables
- Create a demo company
- Create a demo store
- Create an admin user
- Create default document templates

### Step 5: Run Development Server

```bash
python wsgi.py
```

The application will be available at `http://localhost:5000`

### Demo Credentials
- **Company Code**: DEMO
- **Username**: admin
- **Password**: admin123

## Usage

### Creating a New Company

1. Go to `/auth/register`
2. Fill in company details and admin user credentials
3. Login with the new credentials

### Creating Orders

1. Dashboard → Create Order
2. Select Store and Customer
3. Fill order details
4. Click Create Order

### Order Lifecycle

The order follows this workflow:

1. **Create Quotation**: From order details, create a quotation with items and pricing
2. **Generate Quotation Document**: Generate PDF/DOCX from template
3. **Approve Quotation**: Mark quotation as approved
4. **Create Contract**: Create contract from approved quotation
5. **Sign Contract**: Mark contract as signed
6. **Create Delivery Report**: Record delivery/work completion
7. **Confirm Delivery**: Mark delivery as confirmed
8. **Record Advance Payment**: Record advance payment
9. **Record Final Payment**: Mark order as fully paid and complete

### Document Generation

1. From Order View, click "Generate" button
2. Select document format (PDF or DOCX)
3. Document is automatically generated and saved
4. Download from Documents list

### Template System

Templates are stored as plain text with variable substitution.

**Available variables**:
- ```{{customer_name}}```
- ```{{customer_code}}```
- ```{{quotation_number}}```
- ```{{total_amount}}```
- And many more specific to each document type

Edit templates in the DocumentTemplate model to customize documents.

## API Endpoints

### Authentication
- `GET/POST /auth/login` - Login
- `GET/POST /auth/register` - Register new company
- `GET /auth/logout` - Logout

### Dashboard
- `GET /` - Main dashboard
- `GET /orders` - List all orders
- `GET /orders/<order_id>` - View order
- `GET /customers` - List customers
- `POST /customers/create` - Create customer

### Documents
- `POST /documents/generate/<doc_type>/<ref_id>` - Generate document
- `GET /documents/<document_id>/download` - Download document

## Multi-Tenant Security

### Data Isolation
- Every query includes `company_id` filter
- Users only see data for their company
- Tenant verification on every operation

### Authentication
- Session-based authentication
- Password hashing with Werkzeug
- Automatic session timeout

### Access Control
- Role-based access (admin, user)
- Company-level isolation
- Store-level access control

## Production Deployment

### Environment Variables

```bash
FLASK_ENV=production
FLASK_DEBUG=False
DATABASE_URL=postgresql://user:pass@host/dbname
SECRET_KEY=your-secret-key-here
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y postgresql-client

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
```

Build and run:

```bash
docker build -t sofaflow:latest .
docker run -p 5000:5000 -e DATABASE_URL=... sofaflow:latest
```

### Production Checklist

- [ ] Set `FLASK_DEBUG=False`
- [ ] Use strong `SECRET_KEY`
- [ ] Configure proper logging
- [ ] Set up database backups
- [ ] Configure HTTPS/SSL
- [ ] Set up monitoring and alerting
- [ ] Configure rate limiting
- [ ] Set up email integration (future feature)
- [ ] Configure file upload restrictions
- [ ] Regular security updates

## Future Enhancements

- [ ] Email integration for quotations and contracts
- [ ] Online document signing
- [ ] Dashboard analytics and reports
- [ ] Workflow customization
- [ ] User roles and permissions management
- [ ] API for third-party integrations
- [ ] Mobile app
- [ ] Invoice generation
- [ ] Inventory management
- [ ] Payment gateway integration

## Technology Stack

### Backend
- **Framework**: Flask 2.3.3
- **ORM**: SQLAlchemy 2.0
- **Database**: PostgreSQL
- **Authentication**: Werkzeug (built-in)

### Frontend
- **Framework**: Bootstrap 5.3
- **Icons**: Bootstrap Icons
- **JavaScript**: Vanilla JS (no frameworks)

### Document Generation
- **DOCX**: python-docx
- **PDF**: reportlab, LibreOffice (optional)

### DevOps
- **Containerization**: Docker
- **WSGI**: Gunicorn
- **Reverse Proxy**: Nginx

## Code Quality

- Clean Architecture with separation of concerns
- Service layer for business logic
- Repository pattern for data access
- Comprehensive error handling
- Security best practices
- Type hints (partial)
- Logging throughout

## License

This software is provided as-is for use by customers.

## Support

For issues, feature requests, or questions, please contact the development team.

---

**SofaFlow** - Making sofa repair business management simple and scalable.
