# Quick Start Guide - SofaFlow

Get up and running with SofaFlow in 5 minutes!

## Windows Quick Start

### 1. Prerequisites
- Python 3.8+ installed
- PostgreSQL installed and running
- Git (optional)

### 2. Setup

```bash
# Clone or extract the project
cd sofa-flow

# Create virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Database

The database requires proper PostgreSQL permissions to create tables.

**Quick Setup:**
1. See [DATABASE_SETUP.md](DATABASE_SETUP.md) for detailed instructions
2. Choose the easiest option for your setup (pgAdmin recommended for Windows)
3. Run the provided SQL to grant schema permissions

**Environment Variable:**

After fixing database permissions, set:
```bash
set DATABASE_URL=postgresql+psycopg://sofa_user:sofa_password@localhost:5432/sofa_flow
```

### 4. Initialize Database

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

### 5. Run Application

```bash
python wsgi.py
```

The application will start:
```
 * Serving Flask app
 * Running on http://127.0.0.1:5000
```

### 6. Login

1. Open browser: `http://localhost:5000`
2. Enter credentials:
   - Company Code: `DEMO`
   - Username: `admin`
   - Password: `admin123`
3. Click "Login"

## First Use Walkthrough

### Step 1: Explore Dashboard
- View the demonstration dashboard
- See recent orders and statistics
- Familiarize yourself with navigation

### Step 2: Create a Customer
1. Click "Customers" in navigation
2. Click "Add Customer"
3. Fill in customer details:
   - Customer Code: `CUST-001`
   - Name: `John Smith`
   - Phone: `555-1234`
   - Email: `john@example.com`
4. Click "Create Customer"

### Step 3: Create an Order
1. Click "Orders" in navigation
2. Click "Create Order"
3. Fill in order details:
   - Store: Select "Main Store"
   - Customer: Select "John Smith"
   - Order Code: `ORD-001`
   - Order Title: `Sofa Repair`
4. Click "Create Order"

### Step 4: Create a Quotation
1. From the order view, scroll to "Quotation Created" section
2. Click "Create Quotation"
3. Fill in quotation details:
   - Quotation Number: `QT-001`
   - Add items:
     - Item: "Fabric Replacement", Qty: 1, Price: 500.00
     - Item: "Springs Repair", Qty: 1, Price: 200.00
4. Click "Create Quotation"

### Step 5: Generate a Document
1. In the "Quotation Created" section, click "Generate"
2. Select format: "PDF"
3. Click Submit
4. Document is generated
5. Click "Download" in Documents list

### Step 6: Continue Lifecycle
- Create Contract → Generate → Sign
- Create Delivery Report → Generate → Confirm
- Record Payments → Generate → Confirm

## Common Tasks

### Generate a PDF Document
1. Go to Order View
2. Find the section (Quotation, Contract, etc.)
3. Click "Generate" under that section
4. Select "PDF" or "DOCX"
5. Download from Documents list

### Export Document
1. Go to Order → Documents
2. Click "Download" next to the document
3. File saves to your downloads folder

### View Order Timeline
1. Click on any order from the list
2. See the visual timeline of all lifecycle stages
3. Each completed stage shows status and timestamp

### Create New Company
1. Click "Login" if on login page
2. Click "Register here"
3. Fill in company and admin user details
4. Click "Register"
5. Login with new credentials

## Troubleshooting

### "Database connection error"
- Verify PostgreSQL is running
- Check DATABASE_URL is set correctly
- Verify username/password

### "ModuleNotFoundError: No module named 'psycopg2'" 
- This occurs when dependencies aren't fully installed
- Solution: Run `pip install -r requirements.txt --upgrade` again
- This installs psycopg2-binary which is required for PostgreSQL connections

### "Application won't start"
- Activate virtual environment: `venv\Scripts\activate`
- Reinstall dependencies: `pip install -r requirements.txt --upgrade`
- Check Python version: `python --version` (should be 3.8+)

### "Button doesn't work"
- Make sure JavaScript is enabled in browser
- Try refreshing the page
- Check browser console for errors (F12)

### "Template not found"
- Verify templates were created by init_db.py
- Check PostgreSQL database has data

## Next Steps

1. **Customize Templates**
   - Edit templates to match your documents
   - Add company logo and branding
   - Modify terms and conditions

2. **Create Users**
   - Add team members as users
   - Assign roles (admin, manager, user)
   - Set permissions

3. **Backup Data**
   - Regular PostgreSQL backups
   - Export orders and documents

4. **Explore Reports**
   - View order statistics
   - Track payments
   - Generate reports

## File Locations (Important)

- **Configuration**: `app/config/config.py`
- **Database Models**: `app/models/models.py`
- **Business Logic**: `app/services/services.py`
- **Templates**: `app/templates/`
- **Generated Documents**: `app/uploads/documents/`
- **Document Templates**: `app/uploads/templates/`

## Environment Variables

```
DATABASE_URL=postgresql://user:password@localhost:5432/sofa_flow
FLASK_ENV=development
FLASK_DEBUG=True
SECRET_KEY=your-secret-key
```

## Default Routes

| Path | Purpose |
|------|---------|
| `/` | Dashboard (requires login) |
| `/auth/login` | Login page |
| `/auth/register` | Register new company |
| `/auth/logout` | Logout |
| `/customers` | Customer list |
| `/orders` | Order list |
| `/orders/<id>` | Order detail (with lifecycle) |

## Tips & Tricks

1. **Quick Navigation**: Use top navigation bar
2. **Timeline View**: Best way to see order progress
3. **Bulk Operations**: Many items searchable/filterable
4. **Document Backup**: Always download important documents
5. **Mobile**: Responsive design works on tablets

## Getting Help

- Check [README.md](README.md) for full documentation
- See [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) for schema details
- Review [DEPLOYMENT.md](DEPLOYMENT.md) for production setup

## Moving to Production

When ready to deploy:

1. Read [DEPLOYMENT.md](DEPLOYMENT.md)
2. Set up Linux server
3. Configure PostgreSQL production database
4. Set up Nginx
5. Configure SSL
6. Set environment variables for production
7. Enable monitoring

---

**Now you're ready to use SofaFlow!**

Start by creating a customer and order to see the system in action.
