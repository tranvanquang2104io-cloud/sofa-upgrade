"""Alembic environment for SofaFlow.

Metadata comes from the SQLAlchemy models (imported directly so table
definitions register on ``db.metadata`` without building a Flask app — building
the app would trigger ``create_all`` and defeat autogenerate). The database URL
is taken from ``DATABASE_URL`` or the selected app Config, so migrations run
against the same database the app uses (PostgreSQL in prod, SQLite in tests).
"""
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import models so every table is registered on db.metadata (no app / no create_all).
from app.config.database import db
import app.models.models  # noqa: F401  (registers models on db.metadata)
from app.config.config import config as app_config_map

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Resolve the database URL: explicit env var wins, else the app Config default.
_env = os.environ.get("FLASK_ENV", "development")
_app_cfg = app_config_map.get(_env, app_config_map["default"])
database_url = os.environ.get("DATABASE_URL") or _app_cfg.SQLALCHEMY_DATABASE_URI
# Escape % so ConfigParser interpolation does not choke on URLs/passwords.
config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

target_metadata = db.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,  # SQLite-friendly ALTERs
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
