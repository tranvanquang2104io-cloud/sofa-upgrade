-- PostgreSQL Database Setup Script for SofaFlow
-- Complete initialization with tables and demo data
-- Run this as postgres (admin) user to set up the database properly

-- ======================================
-- Part 1: Create Database and User
-- ======================================

-- Create database
CREATE DATABASE sofa_flow;

-- Create user
CREATE USER sofa_user WITH PASSWORD 'sofa_password';

-- Grant privileges on database
GRANT ALL PRIVILEGES ON DATABASE sofa_flow TO sofa_user;

-- ======================================
-- Connect to sofa_flow database
-- ======================================
\c sofa_flow

-- Grant schema privileges (essential for table creation)
GRANT USAGE ON SCHEMA public TO sofa_user;
GRANT CREATE ON SCHEMA public TO sofa_user;

-- Grant default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO sofa_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO sofa_user;

-- ======================================
-- Part 2: Create All Tables
-- ======================================

CREATE TABLE IF NOT EXISTS companies (
    id UUID NOT NULL,
    company_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    timezone VARCHAR(50),
    is_active BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    UNIQUE (company_code)
);

CREATE TABLE IF NOT EXISTS stores (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    store_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    manager_name VARCHAR(255),
    phone VARCHAR(20),
    address TEXT,
    city VARCHAR(100),
    is_active BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id),
    UNIQUE (company_id, store_code)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50),
    is_active BOOLEAN,
    last_login TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id)
);

CREATE TABLE IF NOT EXISTS customers (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    store_id UUID NOT NULL,
    customer_code VARCHAR(50) NOT NULL,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    city VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(100),
    notes TEXT,
    is_active BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id),
    FOREIGN KEY (store_id) REFERENCES stores (id),
    UNIQUE (store_id, customer_code)
);

CREATE TABLE IF NOT EXISTS orders (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    store_id UUID NOT NULL,
    customer_id UUID NOT NULL,
    order_code VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    total_amount NUMERIC(15, 2),
    advance_amount NUMERIC(15, 2),
    final_amount NUMERIC(15, 2),
    notes TEXT,
    is_active BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id),
    FOREIGN KEY (store_id) REFERENCES stores (id),
    FOREIGN KEY (customer_id) REFERENCES customers (id),
    UNIQUE (store_id, order_code)
);

CREATE TABLE IF NOT EXISTS lifecycle_statuses (
    id UUID NOT NULL,
    order_id UUID NOT NULL,
    quotation_created BOOLEAN,
    quotation_created_at TIMESTAMP WITHOUT TIME ZONE,
    quotation_approved BOOLEAN,
    quotation_approved_at TIMESTAMP WITHOUT TIME ZONE,
    contract_signed BOOLEAN,
    contract_signed_at TIMESTAMP WITHOUT TIME ZONE,
    delivery_confirmed BOOLEAN,
    delivery_confirmed_at TIMESTAMP WITHOUT TIME ZONE,
    advance_paid BOOLEAN,
    advance_paid_at TIMESTAMP WITHOUT TIME ZONE,
    fully_paid BOOLEAN,
    fully_paid_at TIMESTAMP WITHOUT TIME ZONE,
    completed BOOLEAN,
    completed_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (id)
);

CREATE TABLE IF NOT EXISTS quotations (
    id UUID NOT NULL,
    order_id UUID NOT NULL,
    quotation_number VARCHAR(50) NOT NULL,
    quotation_date DATE NOT NULL,
    validity_days INTEGER,
    items JSON,
    total_amount NUMERIC(15, 2) NOT NULL,
    notes TEXT,
    is_approved BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (id),
    UNIQUE (quotation_number)
);

CREATE TABLE IF NOT EXISTS contracts (
    id UUID NOT NULL,
    order_id UUID NOT NULL,
    quotation_id UUID,
    contract_number VARCHAR(50) NOT NULL,
    contract_date DATE NOT NULL,
    contract_value NUMERIC(15, 2) NOT NULL,
    terms_and_conditions TEXT,
    is_signed BOOLEAN,
    signed_date TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (id),
    FOREIGN KEY (quotation_id) REFERENCES quotations (id),
    UNIQUE (contract_number)
);

CREATE TABLE IF NOT EXISTS delivery_reports (
    id UUID NOT NULL,
    order_id UUID NOT NULL,
    report_number VARCHAR(50) NOT NULL,
    report_date DATE NOT NULL,
    delivery_date DATE NOT NULL,
    work_description TEXT,
    materials_used TEXT,
    notes TEXT,
    is_confirmed BOOLEAN,
    confirmed_date TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (id),
    UNIQUE (report_number)
);

CREATE TABLE IF NOT EXISTS payment_reports (
    id UUID NOT NULL,
    order_id UUID NOT NULL,
    report_number VARCHAR(50) NOT NULL,
    payment_type VARCHAR(50) NOT NULL,
    report_date DATE NOT NULL,
    payment_date DATE NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    payment_method VARCHAR(100),
    transaction_reference VARCHAR(100),
    notes TEXT,
    is_confirmed BOOLEAN,
    confirmed_date TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders (id),
    UNIQUE (report_number)
);

CREATE TABLE IF NOT EXISTS document_templates (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    description TEXT,
    template_file VARCHAR(255),
    template_content TEXT,
    variables JSON,
    is_active BOOLEAN,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id)
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID NOT NULL,
    company_id UUID NOT NULL,
    order_id UUID NOT NULL,
    template_id UUID,
    quotation_id UUID,
    contract_id UUID,
    delivery_report_id UUID,
    payment_report_id UUID,
    document_name VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    document_format VARCHAR(10) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER,
    variables_used JSON,
    generated_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE,
    updated_at TIMESTAMP WITHOUT TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY (company_id) REFERENCES companies (id),
    FOREIGN KEY (order_id) REFERENCES orders (id),
    FOREIGN KEY (template_id) REFERENCES document_templates (id),
    FOREIGN KEY (quotation_id) REFERENCES quotations (id),
    FOREIGN KEY (contract_id) REFERENCES contracts (id),
    FOREIGN KEY (delivery_report_id) REFERENCES delivery_reports (id),
    FOREIGN KEY (payment_report_id) REFERENCES payment_reports (id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_companies_company_code ON companies (company_code);
CREATE INDEX IF NOT EXISTS idx_companies_is_active ON companies (is_active);
CREATE INDEX IF NOT EXISTS idx_stores_company_id ON stores (company_id);
CREATE INDEX IF NOT EXISTS idx_stores_is_active ON stores (is_active);
CREATE INDEX IF NOT EXISTS idx_users_company_id ON users (company_id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users (is_active);
CREATE INDEX IF NOT EXISTS idx_customers_company_id ON customers (company_id);
CREATE INDEX IF NOT EXISTS idx_customers_store_id ON customers (store_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers (name);
CREATE INDEX IF NOT EXISTS idx_customers_is_active ON customers (is_active);
CREATE INDEX IF NOT EXISTS idx_orders_company_id ON orders (company_id);
CREATE INDEX IF NOT EXISTS idx_orders_store_id ON orders (store_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_is_active ON orders (is_active);
CREATE INDEX IF NOT EXISTS idx_quotations_order_id ON quotations (order_id);
CREATE INDEX IF NOT EXISTS idx_quotations_is_approved ON quotations (is_approved);
CREATE INDEX IF NOT EXISTS idx_contracts_order_id ON contracts (order_id);
CREATE INDEX IF NOT EXISTS idx_contracts_is_signed ON contracts (is_signed);
CREATE INDEX IF NOT EXISTS idx_delivery_reports_order_id ON delivery_reports (order_id);
CREATE INDEX IF NOT EXISTS idx_delivery_reports_is_confirmed ON delivery_reports (is_confirmed);
CREATE INDEX IF NOT EXISTS idx_payment_reports_order_id ON payment_reports (order_id);
CREATE INDEX IF NOT EXISTS idx_payment_reports_is_confirmed ON payment_reports (is_confirmed);
CREATE INDEX IF NOT EXISTS idx_document_templates_company_id ON document_templates (company_id);
CREATE INDEX IF NOT EXISTS idx_document_templates_is_active ON document_templates (is_active);
CREATE INDEX IF NOT EXISTS idx_documents_company_id ON documents (company_id);
CREATE INDEX IF NOT EXISTS idx_documents_order_id ON documents (order_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_statuses_order_id ON lifecycle_statuses (order_id);

-- ======================================
-- Part 3: Insert Demo Data
-- ======================================

-- Insert demo company
INSERT INTO companies (
    id, company_code, name, email, phone, address, city, country, timezone, is_active, created_at, updated_at
) VALUES (
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'DEMO',
    'Demo Sofa Company',
    'demo@sofaflow.local',
    '555-0001',
    '123 Main St',
    'Demo City',
    'Demo Country',
    'UTC',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (company_code) DO NOTHING;

-- Insert demo store
INSERT INTO stores (
    id, company_id, store_code, name, manager_name, phone, address, city, is_active, created_at, updated_at
) VALUES (
    'b179fae3-10b2-412b-a0c0-94ad890336fa',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'STORE-001',
    'Main Store',
    'John Manager',
    '555-0001',
    '123 Main St',
    'Demo City',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (company_id, store_code) DO NOTHING;

-- Insert demo admin user
-- Password: admin123 (hashed with werkzeug PBKDF2)
INSERT INTO users (
    id, company_id, username, email, password_hash, full_name, role, is_active, created_at, updated_at
) VALUES (
    '6e63f25b-2a2c-48bb-b3a6-46474c397858',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'admin',
    'admin@sofaflow.local',
    'pbkdf2:sha256:600000$wtDApJdlAv04FMl4$456e886481d0c010d88b32e98f196a18c09480d01d531ef69221536761627116',
    'Admin User',
    'admin',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Insert demo customer
INSERT INTO customers (
    id, company_id, store_id, customer_code, name, phone, email, address, city, postal_code, country, notes, is_active, created_at, updated_at
) VALUES (
    '6f1d1d3e-54c3-4cae-afff-ca38694a0003',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'b179fae3-10b2-412b-a0c0-94ad890336fa',
    'CUST-001',
    'John Smith',
    '555-1234',
    'john@example.com',
    '456 Oak Avenue',
    'Demo City',
    '12345',
    'Demo Country',
    'Demo customer for testing',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (store_id, customer_code) DO NOTHING;

-- Insert demo order
INSERT INTO orders (
    id, company_id, store_id, customer_id, order_code, title, description, total_amount, advance_amount, final_amount, notes, is_active, created_at, updated_at
) VALUES (
    '6763bc6c-4f31-4edd-b294-316be281aa9a',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'b179fae3-10b2-412b-a0c0-94ad890336fa',
    '6f1d1d3e-54c3-4cae-afff-ca38694a0003',
    'ORD-001',
    'Sofa Repair and Restoration',
    'Complete restoration and repair of premium leather sofa',
    1500.00,
    500.00,
    1000.00,
    'Demo order for workflow testing',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (store_id, order_code) DO NOTHING;

-- Insert lifecycle status for demo order
INSERT INTO lifecycle_statuses (
    id, order_id, quotation_created, quotation_approved, contract_signed, 
    delivery_confirmed, advance_paid, fully_paid, completed, created_at, updated_at
) VALUES (
    '2a26de2f-efc1-43bd-9ffc-e79e1108446e',
    '6763bc6c-4f31-4edd-b294-316be281aa9a',
    false, false, false, false, false, false, false,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT DO NOTHING;

-- Insert document templates
INSERT INTO document_templates (
    id, company_id, name, document_type, description, template_file, template_content, variables, is_active, created_at, updated_at
) VALUES
(
    'a7d8f012-6add-4dc3-b2ed-18a9edad830c',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'Standard Quotation',
    'quotation',
    'Standard template for quotations',
    'quotation_template.docx',
    'QUOTATION

Quotation Number: {{quotation_number}}
Date: {{quotation_date}}
Valid for: {{validity_days}} days

CUSTOMER INFORMATION
Name: {{customer_name}}
Code: {{customer_code}}
Phone: {{customer_phone}}
Email: {{customer_email}}
Address: {{customer_address}}

ORDER DETAILS
Order Code: {{order_code}}
Title: {{order_title}}

ITEMS
{{items}}

Total Amount: ${{total_amount}}

Notes:
{{notes}}

Generated: {{generated_date}}',
    '{"quotation_number": "Quotation number", "quotation_date": "Date of quotation", "customer_name": "Customer full name", "total_amount": "Total quotation amount"}',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'cbef3627-090e-433a-b40c-fd2f247f6f9a',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'Standard Contract',
    'contract',
    'Standard template for contracts',
    'contract_template.docx',
    'CONTRACT

Contract Number: {{contract_number}}
Date: {{contract_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}
Phone: {{customer_phone}}
Email: {{customer_email}}

ORDER DETAILS
Order Code: {{order_code}}
Title: {{order_title}}
Contract Value: ${{contract_value}}

TERMS AND CONDITIONS
{{terms_and_conditions}}

Generated: {{generated_date}}',
    '{"contract_number": "Contract number", "contract_date": "Date of contract", "contract_value": "Contract value in currency"}',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    'b66cdea2-4eca-461d-ab6b-a4b205d68fdf',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'Standard Delivery Report',
    'delivery',
    'Standard template for delivery reports',
    'delivery_template.docx',
    'DELIVERY REPORT

Report Number: {{report_number}}
Report Date: {{report_date}}
Delivery Date: {{delivery_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}

ORDER
Order Code: {{order_code}}
Title: {{order_title}}

WORK DESCRIPTION
{{work_description}}

MATERIALS USED
{{materials_used}}

Notes:
{{notes}}

Generated: {{generated_date}}',
    '{"report_number": "Delivery report number", "report_date": "Date of report", "work_description": "Description of work performed"}',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
),
(
    '0b00be54-97f7-4950-948a-de3073c6f082',
    'a3b97c4a-f637-4e30-8b7b-759d44aa5a16',
    'Standard Payment Report',
    'payment',
    'Standard template for payment reports',
    'payment_template.docx',
    'PAYMENT REPORT

Report Number: {{report_number}}
Payment Type: {{payment_type}}
Report Date: {{report_date}}
Payment Date: {{payment_date}}

CUSTOMER
Name: {{customer_name}}
Code: {{customer_code}}

ORDER
Order Code: {{order_code}}
Title: {{order_title}}

PAYMENT DETAILS
Amount: ${{amount}}
Payment Method: {{payment_method}}
Transaction Reference: {{transaction_reference}}

Notes:
{{notes}}

Generated: {{generated_date}}',
    '{"report_number": "Payment report number", "payment_type": "Type of payment (advance/final)", "amount": "Payment amount"}',
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
);

-- ======================================
-- Verification
-- ======================================

-- Verify demo company created
SELECT 'Demo Company Created' as status, COUNT(*) as count FROM companies WHERE company_code = 'DEMO';

-- Verify demo store created
SELECT 'Demo Store Created' as status, COUNT(*) as count FROM stores WHERE store_code = 'STORE-001';

-- Verify demo user created
SELECT 'Demo User Created' as status, COUNT(*) as count FROM users WHERE username = 'admin';

-- Verify demo customer created
SELECT 'Demo Customer Created' as status, COUNT(*) as count FROM customers WHERE customer_code = 'CUST-001';

-- Verify demo order created
SELECT 'Demo Order Created' as status, COUNT(*) as count FROM orders WHERE order_code = 'ORD-001';

-- Verify document templates created
SELECT 'Document Templates Created' as status, COUNT(*) as count FROM document_templates WHERE company_id = 'a3b97c4a-f637-4e30-8b7b-759d44aa5a16';

-- Summary
SELECT 'Setup Complete!' as message;
