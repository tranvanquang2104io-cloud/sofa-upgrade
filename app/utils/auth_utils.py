"""
Authentication utilities with Role-Based Access Control (RBAC)

Role hierarchy:
  company_admin  - highest; manages company, all stores, all users
  store_admin    - manages one store; cannot edit company-level settings
  user           - end-user; assigned to one store; handles operational documents
"""
from functools import wraps
from flask import session, redirect, url_for, g, abort, current_app
from app.models import User, Company, Store
from app.config.database import db


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def set_user_context(user: User):
    """Persist user identity into the session after a successful login."""
    session['user_id']    = str(user.id)
    session['company_id'] = str(user.company_id)
    session['store_id']   = str(user.store_id) if user.store_id else None
    session['username']   = user.username
    session['full_name']  = user.full_name
    session['role']       = user.role
    user.last_login = db.func.now()
    db.session.commit()


def clear_user_context():
    """Clear all session data (logout)."""
    session.clear()


def get_current_user() -> User | None:
    """Return the currently logged-in User ORM object, or None."""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def get_current_company_id() -> str | None:
    """Return the current user's company UUID string."""
    return session.get('company_id')


def get_current_store_id() -> str | None:
    """Return the current user's store UUID string, or None for company admins."""
    return session.get('store_id')


def get_accessible_store_ids(company_id: str) -> list:
    """
    Return the list of store UUIDs the current user may access.

    - company_admin  → all active stores in the company
    - store_admin    → only their own store
    - user           → only their own store
    """
    role     = session.get('role')
    store_id = session.get('store_id')

    if role == User.ROLE_COMPANY_ADMIN:
        stores = Store.query.filter_by(company_id=company_id, is_active=True).all()
        return [s.id for s in stores]

    if store_id:
        import uuid as _uuid
        try:
            return [_uuid.UUID(store_id)]
        except (ValueError, AttributeError):
            return []
    return []


def get_current_role() -> str | None:
    return session.get('role')


def is_company_admin() -> bool:
    return session.get('role') == User.ROLE_COMPANY_ADMIN


def is_store_admin() -> bool:
    return session.get('role') == User.ROLE_STORE_ADMIN


def is_any_admin() -> bool:
    return session.get('role') in (User.ROLE_COMPANY_ADMIN, User.ROLE_STORE_ADMIN)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def _load_user_to_g():
    """Load the current user ORM object into g."""
    user = User.query.get(session['user_id'])
    if not user or not user.is_active:
        session.clear()
        return None
    g.user       = user
    g.company_id = user.company_id
    g.store_id   = user.store_id
    g.role       = user.role
    return user


def login_required(f):
    """Require the user to be logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = _load_user_to_g()
        if user is None:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def company_admin_required(f):
    """Restrict to company_admin only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = _load_user_to_g()
        if user is None:
            return redirect(url_for('auth.login'))
        if user.role != User.ROLE_COMPANY_ADMIN:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def store_admin_required(f):
    """Restrict to store_admin OR company_admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = _load_user_to_g()
        if user is None:
            return redirect(url_for('auth.login'))
        if user.role not in (User.ROLE_COMPANY_ADMIN, User.ROLE_STORE_ADMIN):
            abort(403)
        return f(*args, **kwargs)
    return decorated


# Keep backward-compat alias (old code uses admin_required)
def admin_required(f):
    """Backward-compat: same as store_admin_required (any admin)."""
    return store_admin_required(f)


# ---------------------------------------------------------------------------
# Tenant / store access guards
# ---------------------------------------------------------------------------

def ensure_tenant_access(resource_company_id):
    """Abort 403 if the current user does not belong to resource_company_id."""
    current = get_current_company_id()
    if str(resource_company_id) != str(current):
        abort(403)


def ensure_store_access(store_id):
    """
    Abort 403 if the current user cannot access the given store.

    company_admin may access any store in their company.
    store_admin / user may only access their assigned store.
    """
    role            = session.get('role')
    current_store   = session.get('store_id')
    company_id      = session.get('company_id')

    if role == User.ROLE_COMPANY_ADMIN:
        # Verify the store belongs to this company
        store = Store.query.filter_by(id=store_id, company_id=company_id, is_active=True).first()
        if not store:
            abort(403)
    else:
        if str(store_id) != str(current_store):
            abort(403)
