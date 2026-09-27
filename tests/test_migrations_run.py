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


# --------------------------------------------------------------------------
# A migration that moves DATA is not tested by running it on an empty database.
# --------------------------------------------------------------------------

def test_the_warehouse_migration_moves_stock_without_changing_any_total(
        empty_database):
    """Seed stock at the revision before, upgrade, and count it again.

    The two tests above run the chain on an empty database. That proves the SQL
    is valid and proves nothing at all about a backfill, because there is
    nothing to back-fill — which is the state every data migration would pass
    in. This one puts rows in first.

    What it pins is the thing a company would actually lose: the quantities.
    Rows move from a location to a warehouse; the numbers on them do not
    change, and neither does their sum per material.
    """
    pytest.importorskip('alembic')
    import sqlalchemy as sa

    before_revision = 'b3c4d5e6f7a8'
    result = _alembic(empty_database, 'upgrade', before_revision)
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(empty_database)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO companies (id, company_code, name, email, is_active) "
            "VALUES ('c1', 'DEMO', 'Nội Thất An Phát', 'a@b.test', 1)"))
        connection.execute(sa.text(
            "INSERT INTO stores (id, company_id, store_code, name, is_active, "
            "created_at) VALUES "
            "('s1', 'c1', 'SR-HN', 'Showroom', 1, '2026-01-01'),"
            "('s2', 'c1', 'XUONG', 'Xưởng', 1, '2026-01-02')"))
        connection.execute(sa.text(
            "INSERT INTO materials (id, company_id, material_code, name, "
            "is_active) VALUES ('m1', 'c1', 'VAI-BO', 'Vải bố', 1)"))
        # One row per store, and one company-level row — the three shapes the
        # old model allowed.
        connection.execute(sa.text(
            "INSERT INTO material_stock (id, material_id, company_id, "
            "store_id, current_quantity) VALUES "
            "('k1', 'm1', 'c1', 's1', 12.5),"
            "('k2', 'm1', 'c1', 's2', 30),"
            "('k3', 'm1', 'c1', NULL, 7.25)"))

    result = _alembic(empty_database, 'upgrade', 'head')
    assert result.returncode == 0, (
        f'the warehouse migration failed:\n{result.stdout}\n{result.stderr}')

    with engine.begin() as connection:
        total = connection.execute(sa.text(
            'SELECT SUM(current_quantity) FROM material_stock '
            "WHERE material_id = 'm1'")).scalar()
        assert float(total) == 49.75, (
            f'stock changed during the migration: {total} instead of 49.75')

        unplaced = connection.execute(sa.text(
            'SELECT COUNT(*) FROM material_stock WHERE warehouse_id IS NULL')
        ).scalar()
        assert unplaced == 0, (
            f'{unplaced} stock rows are in no warehouse, so nothing can reach '
            'them')

        # Each location got its own warehouse, and the company-level rows got
        # one of their own rather than being folded into somebody's branch.
        names = sorted(r[0] for r in connection.execute(sa.text(
            'SELECT name FROM warehouses ORDER BY name')).all())
        assert names == ['Kho Showroom', 'Kho Xưởng', 'Kho công ty'], names

        # The company-level stock did not land in a branch warehouse.
        company_row = connection.execute(sa.text(
            "SELECT w.name FROM material_stock s JOIN warehouses w "
            "ON w.id = s.warehouse_id WHERE s.id = 'k3'")).scalar()
        assert company_row == 'Kho công ty', (
            f"the company-level row was folded into {company_row!r}")


def test_the_document_source_backfill_reaches_every_linked_row(empty_database):
    """A data migration run on an empty database proves nothing about a backfill.

    Seeded at the revision before, so there are rows for it to move.
    """
    pytest.importorskip('alembic')
    import sqlalchemy as sa

    result = _alembic(empty_database, 'upgrade', 'd1e2f3a4b5c6')
    assert result.returncode == 0, result.stderr

    engine = sa.create_engine(empty_database)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO companies (id, company_code, name, email, is_active) "
            "VALUES ('c9', 'DOCS', 'Nội Thất An Phát', 'a@b.test', 1)"))
        connection.execute(sa.text(
            "INSERT INTO stores (id, company_id, store_code, name, is_active) "
            "VALUES ('s9', 'c9', 'SR', 'Showroom', 1)"))
        connection.execute(sa.text(
            "INSERT INTO customers (id, company_id, store_id, "
            "customer_code, name, is_active) VALUES "
            "('cu9', 'c9', 's9', 'KH', 'Chị Hà', 1)"))
        connection.execute(sa.text(
            "INSERT INTO orders (id, company_id, store_id, customer_id, "
            "order_code, title, is_active) VALUES "
            "('o9', 'c9', 's9', 'cu9', 'DH-9', 'Sofa', 1)"))
        connection.execute(sa.text(
            "INSERT INTO quotations (id, company_id, order_id, "
            "quotation_number, quotation_date, total_amount) VALUES "
            "('q9', 'c9', 'o9', 'BG-9', '2026-09-01', 1000000)"))
        connection.execute(sa.text(
            "INSERT INTO documents (id, company_id, order_id, quotation_id, "
            "document_name, document_type, document_format, file_path) "
            "VALUES ('d9', 'c9', 'o9', 'q9', 'BG-9', 'quotation', 'docx', "
            "'q.docx')"))
        # A document with no per-kind link at all — it must survive untouched
        # rather than being given a source somebody guessed.
        connection.execute(sa.text(
            "INSERT INTO documents (id, company_id, order_id, document_name, "
            "document_type, document_format, file_path) VALUES "
            "('d10', 'c9', 'o9', 'KHAC', 'other', 'pdf', 'x.pdf')"))

    result = _alembic(empty_database, 'upgrade', 'head')
    assert result.returncode == 0, (
        f'the document source migration failed:\n{result.stdout}\n'
        f'{result.stderr}')

    with engine.begin() as connection:
        linked = connection.execute(sa.text(
            "SELECT source_type, source_id FROM documents WHERE id = 'd9'")
        ).one()
        assert linked == ('quotation', 'q9'), linked

        unlinked = connection.execute(sa.text(
            "SELECT source_type, source_id FROM documents WHERE id = 'd10'")
        ).one()
        assert unlinked == (None, None), (
            'a document with no link was given a source nobody recorded')

        assert connection.execute(
            sa.text('SELECT COUNT(*) FROM documents')).scalar() == 2
