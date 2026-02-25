# Architecture Overview - SofaFlow

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────┐   │
│  │  Bootstrap  │  │  Jinja2     │  │  JavaScript    │   │
│  │  HTML/CSS   │  │  Templates  │  │  (Alpine/Vanilla)  │
│  └─────────────┘  └─────────────┘  └────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓ HTTP/HTTPS
┌─────────────────────────────────────────────────────────┐
│                  Application Layer (Flask)              │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Routes (Blueprint)                              │   │
│  │  ├─ auth_routes.py (Authentication)            │   │
│  │  └─ dashboard_routes.py (Main Application)     │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Middleware Layer                                │   │
│  │  ├─ Authentication & Authorization              │   │
│  │  ├─ Tenant Isolation                            │   │
│  │  └─ Error Handling                              │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Business Logic Layer (Services)            │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Services (Business Rules)                       │   │
│  │  ├─ CompanyService                             │   │
│  │  ├─ UserService                                │   │
│  │  ├─ CustomerService                           │   │
│  │  ├─ OrderService                              │   │
│  │  ├─ QuotationService                          │   │
│  │  ├─ ContractService                           │   │
│  │  ├─ DeliveryReportService                     │   │
│  │  ├─ PaymentReportService                      │   │
│  │  └─ DocumentService                           │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Template Engine (Document Generation)          │   │
│  │  ├─ TemplateEngine (RTF Processing)           │   │
│  │  └─ DocumentVariableCollector                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│              Data Access Layer (Repositories)           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Repository Pattern                              │   │
│  │  ├─ CompanyRepository                           │   │
│  │  ├─ StoreRepository                            │   │
│  │  ├─ UserRepository                             │   │
│  │  ├─ CustomerRepository                         │   │
│  │  ├─ OrderRepository                            │   │
│  │  ├─ QuotationRepository                        │   │
│  │  ├─ ContractRepository                         │   │
│  │  ├─ DeliveryReportRepository                   │   │
│  │  ├─ PaymentReportRepository                    │   │
│  │  ├─ DocumentRepository                         │   │
│  │  └─ DocumentTemplateRepository                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓ ORM (SQLAlchemy)
┌─────────────────────────────────────────────────────────┐
│              Database Models (SQLAlchemy)               │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Models                                          │   │
│  │  ├─ Company, Store, User                        │   │
│  │  ├─ Customer, Order, LifecycleStatus           │   │
│  │  ├─ Quotation, Contract                        │   │
│  │  ├─ DeliveryReport, PaymentReport              │   │
│  │  ├─ Document, DocumentTemplate                 │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                          ↓ SQL
┌─────────────────────────────────────────────────────────┐
│                   Persistence Layer                     │
│  ┌──────────────────────────────────────────────────┐   │
│  │  PostgreSQL Database                             │   │
│  │  ├─ Multi-Tenant Schema                         │   │
│  │  ├─ Automated Backups                           │   │
│  │  └─ Connection Pooling                          │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────┐   │
│  │  File Storage                                    │   │
│  │  ├─ Generated Documents                         │   │
│  │  ├─ RTF Templates                               │   │
│  │  └─ Upload Directory                            │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Architecture Components

### 1. Frontend Layer
- **Technology**: Bootstrap 5, Jinja2 Templates, Vanilla JavaScript
- **Responsibilities**:
  - User interface rendering
  - Form validation
  - Event handling
  - Dynamic updates

### 2. Application Layer (Flask)
- **Routes**: URL routing and HTTP handling
- **Blueprints**: Modular application organization
- **Middleware**: Authentication, authorization, error handling
- **Context Processors**: Data injection into templates

### 3. Business Logic Layer (Services)
- **Service Classes**: Encapsulate business rules
- **Transaction Management**: Database transaction handling
- **Document Generation**: Template processing and file generation
- **Validation**: Input validation and business rule enforcement

### 4. Data Access Layer (Repositories)
- **Repository Pattern**: Abstract database access
- **Query Building**: Centralized query logic
- **Multi-Tenant Filtering**: Company/Store isolation
- **Caching Ready**: Future optimization

### 5. Database Models (SQLAlchemy)
- **ORM Mapping**: Python objects to database tables
- **Relationships**: Foreign key relationships
- **Constraints**: Unique constraints, indexes
- **Validation**: Data type validation

### 6. Persistence Layer
- **PostgreSQL Database**: Relational database
- **File Storage**: Generated documents and templates
- **Connection Pool**: Efficient database connections

## Data Flow

### Creating an Order (Example)

```
1. User clicks "Create Order" in UI
                    ↓
2. Route Handler (@dashboard_bp.route)
   ├─ Validates request
   ├─ Checks authentication
   └─ Calls OrderService.create_order()
                    ↓
3. OrderService
   ├─ Validates business rules
   ├─ Calls OrderRepository.create()
   ├─ Creates LifecycleStatus
   └─ Returns Order object
                    ↓
4. OrderRepository
   ├─ Creates model instance
   ├─ Adds to SQLAlchemy session
   └─ Commits transaction
                    ↓
5. SQLAlchemy
   ├─ Generates SQL INSERT
   └─ Executes via connection pool
                    ↓
6. PostgreSQL Database
   ├─ Validates constraints
   ├─ Inserts record
   └─ Returns affected rows
                    ↓
7. Response rendered as HTML/JSON
   └─ User sees updated page
```

## Multi-Tenant Isolation

### Tenant Context
Every request includes tenant identification:

```python
# In route handler
company_id = get_current_company_id()  # From session

# Service usage
order = order_service.get_order(order_id, company_id)

# Repository query
def get_order(order_id):
    return Order.query.filter_by(
        id=order_id,
        company_id=company_id  # ← Tenant filter
    ).first()
```

### Data Isolation Guarantees
1. **Database Level**: Tenant ID in every table
2. **Application Level**: Tenant validation on all operations
3. **Query Level**: Automatic tenant filtering
4. **Access Control**: No cross-tenant data access

## Request/Response Cycle

```
┌─────────────────────┐
│  User Browser       │
│  (HTML/JavaScript)  │
└─────────┬───────────┘
          │ HTTP Request
          ↓
┌─────────────────────────────────────┐
│  Nginx / Load Balancer              │
│  (SSL/TLS, Compression)             │
└─────────┬───────────────────────────┘
          │
          ↓
┌─────────────────────────────────────┐
│  Gunicorn Application Server        │
│  (Multiple Worker Processes)        │
└─────────┬───────────────────────────┘
          │
          ↓
┌─────────────────────────────────────┐
│  Flask Application                  │
│  1. Route Matching                  │
│  2. Request Context                 │
│  3. Authentication                  │
│  4. Authorization                   │
│  5. Business Logic                  │
│  6. Database Access                 │
│  7. Response Generation             │
└─────────┬───────────────────────────┘
          │
          ↓
┌─────────────────────────────────────┐
│  SQLAlchemy ORM                     │
│  (Connection Pool, Query Building)  │
└─────────┬───────────────────────────┘
          │
          ↓
┌─────────────────────────────────────┐
│  PostgreSQL Database                │
│  (Transaction, Constraints, Indexes)│
└─────────┬───────────────────────────┘
          │
          ↓ Response
┌─────────────────────┐
│  User Browser       │
│  (HTML Rendered)    │
└─────────────────────┘
```

## Document Generation Pipeline

```
1. Template Selection
   └─ Get RTF template from DocumentTemplate table
                    ↓
2. Variable Collection
   └─ Collect data from related records (Customer, Order, etc.)
                    ↓
3. Template Rendering
   ├─ Replace {{variable}} placeholders
   └─ Handle formatting
                    ↓
4. Document Generation
   ├─ Option A: Generate DOCX using python-docx
   └─ Option B: Generate PDF via ReportLab or LibreOffice
                    ↓
5. File Storage
   ├─ Save to filesystem
   └─ Create Database record
                    ↓
6. Download/Distribution
   └─ Send to user or email (future)
```

## Scalability Considerations

### Horizontal Scaling
```
                     ┌──────────────┐
                     │  PostgreSQL  │
                     │  (Shared DB) │
                     └──────┬───────┘
                            ↑
          ┌─────────────────┼─────────────────┐
          ↓                 ↓                 ↓
    ┌─────────┐      ┌─────────┐      ┌─────────┐
    │Gunicorn1│      │Gunicorn2│      │Gunicorn3│
    │App1     │      │App2     │      │App3     │
    └────┬────┘      └────┬────┘      └────┬────┘
         ↓                ↓                ↓
         └────────┬───────┴────────┬───────┘
                  ↓                ↓
           ┌────────────────────────────┐
           │   Load Balancer (HAProxy)  │
           └────────────┬───────────────┘
                        ↓
                   User Requests
```

### Vertical Scaling
- Increase server resources (CPU, RAM)
- Optimize database queries
- Enable Redis caching layer
- Connection pooling tuning

## Security Architecture

### Authentication Flow
```
Login Request
    ↓
Validate Company Code
    ↓
Validate Username/Password
    ↓
Create Session
    ↓
Set Session Cookie
    ↓
Redirect to Dashboard
```

### Authorization Flow
```
@login_required decorator
    ↓
Check session['user_id']
    ↓
Verify user is active
    ↓
Set g.user, g.company_id
    ↓
Evaluate tenant access
    ↓
Call route handler
```

### Tenant Isolation Flow
```
Every Operation
    ↓
Get current_company_id from session
    ↓
Add company_id filter to all queries
    ↓
Verify company_id match
    ↓
Allow operation OR deny with 403
```

## Performance Optimization

### Database
- Connection pooling (10 connections)
- Query indexing on foreign keys and company_id
- Pre-ping for stale connections

### Application
- Jinja2 template caching
- Lazy loading relationships
- Query optimization

### Frontend
- CSS/JavaScript minification
- Static file caching
- Responsive images

## Error Handling

```
┌──────────────────────┐
│  Exception Raised    │
└──────┬───────────────┘
       ↓
┌──────────────────────────────────────┐
│  Check Exception Type                │
├──────────────────────────────────────┤
│  ├─ Validation Error → 400          │
│  ├─ Auth Error → 401/403            │
│  ├─ Not Found → 404                 │
│  ├─ Server Error → 500              │
│  └─ Other → 500                     │
└──────┬───────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Log Error Details                   │
└──────┬───────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Render Error Template               │
└──────┬───────────────────────────────┘
       ↓
┌──────────────────────────────────────┐
│  Return to User                      │
└──────────────────────────────────────┘
```

## Deployment Architecture

```
┌─────────────────────────────────────┐
│         Internet / CDN              │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│   SSL/TLS Certificate (Let's Encrypt)
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│      Nginx (Reverse Proxy)          │
│      (Static Files, Compression)    │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│    Supervisor (Process Manager)     │
│    (Auto-restart, Logging)          │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│    Gunicorn (WSGI Server)           │
│    (Multiple Worker Processes)      │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│    Flask Application                │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│    PostgreSQL Database              │
│    (Automated Backups, Replication) │
└─────────────────────────────────────┘
```

---

For implementation details, see:
- [models.py](app/models/models.py) - Database models
- [services.py](app/services/services.py) - Business logic
- [repository.py](app/repositories/repository.py) - Data access
- [dashboard_routes.py](app/routes/dashboard_routes.py) - Route handlers
