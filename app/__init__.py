"""
Flask application factory
"""
import os
import logging
from datetime import datetime

# Read version from VERSION file at project root
_VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'VERSION')
try:
    with open(_VERSION_FILE) as _f:
        __version__ = _f.read().strip()
except FileNotFoundError:
    __version__ = 'unknown'
from flask import Flask, render_template, session, g
from app.config import init_db, config
from app.routes.auth_routes import auth_bp
from app.routes.dashboard_routes import dashboard_bp
from app.routes.admin_routes import admin_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def create_app(config_name=None):
    """Application factory"""
    
    # Determine config
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
                static_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    # Load configuration
    app.config.from_object(config[config_name])

    # Fail fast in production if SECRET_KEY was not overridden via environment.
    # (Dev/test intentionally keep a default; production MUST set its own.)
    if config_name == 'production':
        _default_key = 'dev-secret-key-change-in-production'
        if app.config.get('SECRET_KEY') in (None, '', _default_key):
            raise RuntimeError(
                "SECRET_KEY must be set via the environment in production "
                "(refusing to start with the built-in development key)."
            )

    # Create upload directories
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TEMPLATES_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DOCUMENTS_FOLDER'], exist_ok=True)
    os.makedirs(app.config['ITEMS_FOLDER'], exist_ok=True)
    
    # Initialize database
    init_db(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(admin_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden(error):
        return render_template('errors/403.html'), 403
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    # Context processors
    @app.context_processor
    def inject_user():
        """Inject user, utilities and app version into templates"""
        return dict(
            current_user=g.get('user'),
            company_id=g.get('company_id'),
            now=datetime.now,
            app_version=__version__,
        )

    @app.context_processor
    def inject_i18n():
        """Inject i18n translation helper and current language into all templates."""
        from flask import session as _session
        from app.utils.i18n import t as _t
        lang = _session.get('lang', 'vi')
        return dict(
            t=lambda key: _t(key, lang),
            current_lang=lang
        )
    
    logger.info(f"Flask app created with config: {config_name}")
    
    return app
