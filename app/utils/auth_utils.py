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
    """Persist user identity into the session after a successful login.

    The session is cleared first (rotating it) so that any value an attacker may
    have planted in a pre-authentication session cannot survive login — mitigating
    session fixation (AUDIT S4). The language preference is preserved.
    """
    lang = session.get('lang')
    session.clear()
    if lang:
        session['lang'] = lang
    session['user_id']    = str(user.id)
    session['company_id'] = str(user.company_id)
    session['store_id']   = str(user.store_id) if user.store_id else None
    session['username']   = user.username
    session['full_name']  = user.full_name
    session['role']       = user.role
    session['features']   = list(user.allowed_features or [])
    user.last_login = db.func.now()
    db.session.commit()


# ---------------------------------------------------------------------------
# Feature-level access control (RBAC) — see User.can_feature / FEATURE_KEYS
# ---------------------------------------------------------------------------

# The map used to live here and inferred an endpoint's area by matching
# substrings of its name. It is now written out by hand, one line per endpoint,
# in app/utils/permission_map.py — see that module for why. Re-exported here so
# the callers and tests that know this name keep working.
from app.utils.permission_map import (  # noqa: E402,F401
    UnmappedEndpoint, feature_for_endpoint,
)


def current_user_can(feature):
    """Session-based RBAC check (no DB hit): admins pass; users need the grant."""
    if session.get('role') in (User.ROLE_COMPANY_ADMIN, User.ROLE_STORE_ADMIN):
        return True
    return feature in (session.get('features') or [])


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


def get_current_company():
    """Return the current user's Company row, or None.

    Used where company-level *settings* are needed rather than just the id —
    e.g. the configured default VAT rate. Cached on ``g`` so a request that
    needs it several times issues one query.
    """
    company_id = get_current_company_id()
    if not company_id:
        return None
    cached = getattr(g, '_current_company', None)
    if cached is not None and str(cached.id) == str(company_id):
        return cached
    company = Company.query.get(company_id)
    g._current_company = company
    return company


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
    # Marks the view as role-gated so a test can check that a screen which is
    # in NO permission area really does carry a decorator. Without the mark,
    # "ungated here because gated there" is an unverifiable claim.
    decorated._role_required = User.ROLE_COMPANY_ADMIN
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
    decorated._role_required = User.ROLE_STORE_ADMIN
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
