"""Every migration must actually run, and the schema it builds must match the models.

`tests/conftest.py` builds the test database with `db.create_all()`. That is
fast and it is what every other test in this suite stands on — but it means no
migration in this repository has ever been executed by the suite. The models
are tested; the path that takes a REAL database from one version to the next is
not tested at all.

That gap has been harmless so far because the migrations to date add columns.
It stops being harmless at the next one: separating warehouses from stores has
to move stock quantities between rows, and a mistake there is not a failed
deploy, it is a company's inventory quietly becoming wrong. A migration that
moves data and has no test is the riskiest thing in this plan.

Two properties, and the second is the one that catches drift:

* `alembic upgrade head` completes on an empty database — every revision in the
  chain runs, in order, with no missing dependency and no broken SQL;
* the schema it produces contains the tables the models declare. `create_all()`
  and the migration chain are two descriptions of the same schema, maintained
  by hand, and nothing has been comparing them. A column added to a model and
  forgotten in a migration works perfectly in every test and fails on the first
  real deployment.
"""
import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


@pytest.fixture()
def empty_database(tmp_path):
    """A file database at revision zero, the state a new deployment starts in."""
    path = tmp_path / 'migrate.db'
    return 'sqlite:///' + str(path).replace('\\', '/')


def _alembic(url, *args):
    environment = dict(os.environ)
    environment['DATABASE_URL'] = url
    environment['PYTHONIOENCODING'] = 'utf-8'
    # encoding/errors given explicitly: this box's console is cp1252, and the
    # migrations carry Vietnamese docstrings, so the default decoder raises
    # UnicodeDecodeError on alembic's own output — a failure about the console,
    # reported as a failure of the migration.
    return subprocess.run(
        [sys.executable, '-m', 'alembic', *args],
        cwd=str(ROOT), env=environment, capture_output=True, text=True,
        encoding='utf-8', errors='replace')


def test_the_whole_migration_chain_runs_on_an_empty_database(empty_database):
    pytest.importorskip('alembic')
    result = _alembic(empty_database, 'upgrade', 'head')
    assert result.returncode == 0, (
        'alembic upgrade head failed on an empty database:\n'
        f'{result.stdout}\n{result.stderr}')


def test_the_migrated_schema_has_the_tables_the_models_declare(empty_database):
    """The two descriptions of the schema must not drift apart.

    A column added to a model and forgotten in a migration passes every test in
    this suite — they all build the schema from the models — and fails the
    first time a real database is upgraded.
    """
    pytest.importorskip('alembic')
    import sqlalchemy as sa

    result = _alembic(empty_database, 'upgrade', 'head')
    assert result.returncode == 0, result.stderr

    from app.config import db  # noqa: F401  (registers the models)
    import app.models.models  # noqa: F401

    engine = sa.create_engine(empty_database)
    migrated = set(sa.inspect(engine).get_table_names())
    declared = set(db.metadata.tables)

    missing = sorted(declared - migrated - {'alembic_version'})
    assert missing == [], (
        'these tables exist in the models but no migration creates them, so a '
        f'real deployment would not have them: {missing}')
