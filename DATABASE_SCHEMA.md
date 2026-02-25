# Database Schema Documentation

## Overview
SofaFlow uses a multi-tenant PostgreSQL database design to support multiple companies with complete data isolation.

## Core Tables

### companies
Represents a company/tenant in the system.

```sql
CREATE TABLE companies (
    id UUID PRIMARY KEY,
    company_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50) DEFAULT 'UTC',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### stores
Stores within each company.

```sql
CREATE TABLE stores (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    store_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    manager_name VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, store_code)
);
```

### users
Application users with role-based access control.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',  -- admin, manager, user
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Customer and Order Tables

### customers
Customer information.

```sql
CREATE TABLE customers (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    store_id UUID NOT NULL REFERENCES stores(id),
    customer_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(store_id, customer_code)
);
```

### orders
Main order/lifecycle tracking table.

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    store_id UUID NOT NULL REFERENCES stores(id),
    customer_id UUID NOT NULL REFERENCES customers(id),
    order_code VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    total_amount DECIMAL(15,2) DEFAULT 0,
    advance_amount DECIMAL(15,2) DEFAULT 0,
    final_amount DECIMAL(15,2) DEFAULT 0,
    notes TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(store_id, order_code)
);
```

### lifecycle_statuses
Tracks the status of each order through the lifecycle.

```sql
CREATE TABLE lifecycle_statuses (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL UNIQUE REFERENCES orders(id),
    
    quotation_created BOOLEAN DEFAULT FALSE,
    quotation_created_at TIMESTAMP,
    
    quotation_approved BOOLEAN DEFAULT FALSE,
    quotation_approved_at TIMESTAMP,
    
    contract_signed BOOLEAN DEFAULT FALSE,
    contract_signed_at TIMESTAMP,
    
    delivery_confirmed BOOLEAN DEFAULT FALSE,
    delivery_confirmed_at TIMESTAMP,
    
    advance_paid BOOLEAN DEFAULT FALSE,
    advance_paid_at TIMESTAMP,
    
    fully_paid BOOLEAN DEFAULT FALSE,
    fully_paid_at TIMESTAMP,
    
    completed BOOLEAN DEFAULT FALSE,
    completed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Document Tables

### quotations
Quotation details with line items.

```sql
CREATE TABLE quotations (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    quotation_number VARCHAR(50) NOT NULL UNIQUE,
    quotation_date DATE NOT NULL,
    validity_days INTEGER DEFAULT 30,
    items JSON DEFAULT '[]',  -- [{name, quantity, unit_price, total}]
    total_amount DECIMAL(15,2) NOT NULL,
    notes TEXT,
    is_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### contracts
Contract information derived from quotations.

```sql
CREATE TABLE contracts (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    quotation_id UUID REFERENCES quotations(id),
    contract_number VARCHAR(50) NOT NULL UNIQUE,
    contract_date DATE NOT NULL,
    contract_value DECIMAL(15,2) NOT NULL,
    terms_and_conditions TEXT,
    is_signed BOOLEAN DEFAULT FALSE,
    signed_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### delivery_reports
Work completion and delivery information.

```sql
CREATE TABLE delivery_reports (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    report_number VARCHAR(50) NOT NULL UNIQUE,
    report_date DATE NOT NULL,
    delivery_date DATE NOT NULL,
    work_description TEXT,
    materials_used TEXT,
    notes TEXT,
    is_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### payment_reports
Payment tracking for advance and final payments.

```sql
CREATE TABLE payment_reports (
    id UUID PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES orders(id),
    report_number VARCHAR(50) NOT NULL UNIQUE,
    payment_type VARCHAR(50) NOT NULL,  -- 'advance' or 'final'
    report_date DATE NOT NULL,
    payment_date DATE NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    payment_method VARCHAR(100),
    transaction_reference VARCHAR(100),
    notes TEXT,
    is_confirmed BOOLEAN DEFAULT FALSE,
    confirmed_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Template and Document Tables

### document_templates
RTF templates for document generation.

```sql
CREATE TABLE document_templates (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    description TEXT,
    template_file VARCHAR(255) NOT NULL,
    template_content TEXT,
    variables JSON DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### documents
Generated documents with file references.

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    company_id UUID NOT NULL REFERENCES companies(id),
    order_id UUID NOT NULL REFERENCES orders(id),
    template_id UUID REFERENCES document_templates(id),
    quotation_id UUID REFERENCES quotations(id),
    contract_id UUID REFERENCES contracts(id),
    delivery_report_id UUID REFERENCES delivery_reports(id),
    payment_report_id UUID REFERENCES payment_reports(id),
    
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    document_format VARCHAR(10) NOT NULL,  -- 'pdf' or 'docx'
    
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    
    variables_used JSON DEFAULT '{}',
    generated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## Indexes

```sql
-- Performance indexes
CREATE INDEX idx_companies_active ON companies(is_active);
CREATE INDEX idx_users_company_id ON users(company_id);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_customers_company_id ON customers(company_id);
CREATE INDEX idx_customers_store_id ON customers(store_id);
CREATE INDEX idx_customers_active ON customers(is_active);
CREATE INDEX idx_orders_company_id ON orders(company_id);
CREATE INDEX idx_orders_store_id ON orders(store_id);
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_active ON orders(is_active);
CREATE INDEX idx_lifecycle_order_id ON lifecycle_statuses(order_id);
CREATE INDEX idx_quotations_order_id ON quotations(order_id);
CREATE INDEX idx_contracts_order_id ON contracts(order_id);
CREATE INDEX idx_delivery_order_id ON delivery_reports(order_id);
CREATE INDEX idx_payment_order_id ON payment_reports(order_id);
CREATE INDEX idx_documents_company_id ON documents(company_id);
CREATE INDEX idx_documents_order_id ON documents(order_id);
```

## Multi-Tenant Data Isolation

Every table includes `company_id` to ensure data isolation. Application should:

1. **Always filter by company_id** on all queries
2. **Verify company_id match** before any operation
3. **Never allow cross-company access** through application logic

Example query:
```sql
SELECT * FROM orders 
WHERE company_id = $1 AND id = $2;
```

## Relationships

```
companies
├── stores
├── users
├── customers
│   └── orders
│       ├── quotations
│       ├── contracts
│       ├── delivery_reports
│       ├── payment_reports
│       ├── documents
│       └── lifecycle_statuses
└── document_templates
```

## Backup and Recovery

### Backup Strategy
- Daily automated backups
- Backup retention: 30 days
- Location: Separate secure storage

### Recovery Procedure
```bash
# Full backup
pg_dump sofa_flow > backup.sql

# Restore from backup
psql sofa_flow < backup.sql
```

---

For detailed schema implementation, see [models.py](app/models/models.py)
