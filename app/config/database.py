"""
Database initialization module
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine
import logging

db = SQLAlchemy()

logger = logging.getLogger(__name__)


def init_db(app):
    """Initialize database with app context"""
    db.init_app(app)
    
    # Create tables
    with app.app_context():
        db.create_all()
        logger.info("Database initialized successfully")
    
    return db


@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log SQL queries in development"""
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Query: %s", statement)
