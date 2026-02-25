"""
Authentication routes
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from app.services.services import UserService, CompanyService
from app.utils.auth_utils import set_user_context, clear_user_context, login_required
from app.models import Company
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    if request.method == 'POST':
        company_code = request.form.get('company_code', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not all([company_code, username, password]):
            flash('Please enter company code, username, and password', 'error')
            return redirect(url_for('auth.login'))
        
        try:
            # Get company
            company_service = CompanyService()
            company = company_service.repo.get_by_code(company_code)
            
            if not company:
                flash('Invalid company code', 'error')
                return redirect(url_for('auth.login'))
            
            # Authenticate user
            user_service = UserService()
            user = user_service.authenticate_user(username, password, company.id)
            
            if user:
                set_user_context(user)
                logger.info(f"User logged in: {username} ({company_code})")
                return redirect(url_for('dashboard.index'))
            else:
                flash('Invalid username or password', 'error')
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('Login failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    """Logout user"""
    username = session.get('username', 'Unknown')
    clear_user_context()
    logger.info(f"User logged out: {username}")
    flash('You have been logged out', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register new company (admin feature)"""
    if request.method == 'POST':
        company_code = request.form.get('company_code', '').strip()
        company_name = request.form.get('company_name', '').strip()
        email = request.form.get('email', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        full_name = request.form.get('full_name', '').strip()
        
        if not all([company_code, company_name, email, username, password, full_name]):
            flash('All fields are required', 'error')
            return redirect(url_for('auth.register'))
        
        try:
            company_service = CompanyService()
            user_service = UserService()
            
            # Create company
            company = company_service.create_company(
                company_code=company_code,
                name=company_name,
                email=email
            )
            
            # Create admin user
            user = user_service.create_user(
                company_id=company.id,
                username=username,
                email=email,
                password=password,
                full_name=full_name,
                role='admin'
            )
            
            logger.info(f"Company registered: {company_code}")
            flash('Company registered successfully. Please login.', 'success')
            return redirect(url_for('auth.login'))
            
        except ValueError as e:
            flash(str(e), 'error')
            return redirect(url_for('auth.register'))
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('auth.register'))
    
    return render_template('auth/register.html')
