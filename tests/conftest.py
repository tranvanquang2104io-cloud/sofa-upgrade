"""
Pytest fixtures for SofaFlow.

DB strategy (see AUDIT/DECISIONS.md D2): a fresh **file-based** SQLite database
per test. `:memory:` is avoided because SQLAlchemy opens more than one
connection and each in-memory connection gets its own empty database, which
produces confusing false failures.
"""
import os

os.environ.setdefault("FLASK_ENV", "testing")

import pytest

from app.config.config import TestingConfig


@pytest.fixture()
def app(tmp_path):
    """A fresh Flask app bound to an isolated SQLite file for each test."""
    db_file = tmp_path / "test.db"
    # create_app reads the URI off TestingConfig via from_object, so set it
    # before the app is built.
    TestingConfig.SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_file}"

    from app import create_app
    from app.config import db

    application = create_app("testing")
    with application.app_context():
        db.create_all()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def db_session(app):
    """Expose the SQLAlchemy session inside an app context."""
    from app.config import db

    with app.app_context():
        yield db.session


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seed(app):
    """Seed a minimal tenant: 1 company, 1 store, a company_admin, a store user,
    and a customer. Returns a dict of string ids/codes usable across requests."""
    from app.config import db
    from app.models import Company, Store, User, Customer

    data = {}
    with app.app_context():
        company = Company(company_code="ACME", name="Acme Sofa Co", email="a@acme.test")
        db.session.add(company)
        db.session.flush()

        store = Store(company_id=company.id, store_code="S1", name="Main Store")
        db.session.add(store)
        db.session.flush()

        admin = User(
            company_id=company.id, username="admin", email="admin@acme.test",
            full_name="Company Admin", role="company_admin",
        )
        admin.set_password("secret123")

        staff = User(
            company_id=company.id, store_id=store.id, username="staff",
            email="staff@acme.test", full_name="Store Staff", role="user",
        )
        staff.set_password("secret123")
        db.session.add_all([admin, staff])
        db.session.flush()

        customer = Customer(
            company_id=company.id, store_id=store.id,
            customer_code="CUST-001", name="Nguyễn Văn A", phone="0900000000",
        )
        db.session.add(customer)
        db.session.commit()

        data = {
            "company_code": "ACME",
            "company_id": str(company.id),
            "store_id": str(store.id),
            "admin_id": str(admin.id),
            "staff_id": str(staff.id),
            "customer_id": str(customer.id),
        }
    return data


@pytest.fixture()
def seeded_order(app, seed):
    """Create an Order in the seeded ACME company/store; return ids incl. order_id."""
    from app.config import db
    from app.models import Order

    with app.app_context():
        order = Order(
            company_id=seed["company_id"],
            store_id=seed["store_id"],
            customer_id=seed["customer_id"],
            order_code="ORD-001",
            title="Reupholster sofa",
        )
        db.session.add(order)
        db.session.commit()
        seed = {**seed, "order_id": str(order.id)}
    return seed


@pytest.fixture()
def login(client, seed, app):
    """Log a seeded user in via the real (email + password) login flow.

    Still accepts ``username=`` for convenience — it is resolved to that user's
    email so existing callers keep working after the email-login switch.
    """
    def _login(username="admin", password="secret123", company_code=None, email=None):
        if email is None:
            from app.models.models import User
            with app.app_context():
                u = User.query.filter_by(username=username).first()
                email = u.email if u else username
        return client.post("/auth/login", data={"email": email, "password": password},
                           follow_redirects=True)
    return _login
