"""
Authentication utilities
"""
from functools import wraps
from flask import session, redirect, url_for, g, abort, current_app
from app.models import User, Company
from app.config.database import db


def login_required(f):
    """Decorator for routes that require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            session.clear()
            return redirect(url_for('auth.login'))
        
        g.user = user
        g.company_id = user.company_id
        return f(*args, **kwargs)
    
    return decorated_function


def admin_required(f):
    """Decorator for routes that require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_active or user.role != 'admin':
            abort(403)
        
        g.user = user
        g.company_id = user.company_id
        return f(*args, **kwargs)
    
    return decorated_function


def set_user_context(user):
    """Set user context in session"""
    session['user_id'] = str(user.id)
    session['company_id'] = str(user.company_id)
    session['username'] = user.username
    session['full_name'] = user.full_name
    session['role'] = user.role
    user.last_login = db.func.now()
    db.session.commit()


def clear_user_context():
    """Clear user context from session"""
    session.clear()


def get_current_user():
    """Get current user from session"""
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None


def get_current_company_id():
    """Get current company ID from session"""
    return session.get('company_id')


def ensure_tenant_access(resource_company_id):
    """Ensure user has access to the requested company/tenant"""
    current_company_id = get_current_company_id()
    if str(resource_company_id) != str(current_company_id):
        abort(403)  # Forbidden
