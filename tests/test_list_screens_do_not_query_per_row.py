"""A list screen must cost the same number of queries for 2 rows as for 8.

Measured on the demo data before this test existed: the orders list issued one
lifecycle query per row, the materials list one stock query per row, and the
purchase-suggestions screen — which reads EVERY active material, unpaginated —
three per material. Nothing looked wrong: each page rendered, and a demo company
with a dozen rows answers in milliseconds. It is a real catalogue of a few
hundred materials that makes the suggestions page a thousand queries long.

Two of these were not missing eager loads. The orders and production lists
DECLARED `joinedload(...)`, and `db.paginate(query)` re-executed the legacy
Query without its `.options()` — so the code read as optimised while running
exactly as if the line were absent. Only counting the queries could tell.

Each row below gets its OWN customer / unit / stock row on purpose: a shared one
is served from the session's identity map after the first lazy load, which hides
an N+1 behind a single query.
"""
import pathlib
from decimal import Decimal

import pytest
from sqlalchemy import event

from app.config import db


def _count_queries(app, client, url):
    statements = []

    def _record(conn, cursor, statement, params, context, executemany):
        statements.append(statement)

    with app.app_context():
        engine = db.engine
    event.listen(engine, 'before_cursor_execute', _record)
    try:
        response = client.get(url)
    finally:
        event.remove(engine, 'before_cursor_execute', _record)
    assert response.status_code == 200, (url, response.status_code)
    return len(statements)


def _add_orders(app, seed, start, count):
    from app.models.models import Customer, LifecycleStatus, Order
    with app.app_context():
        for i in range(start, start + count):
            customer = Customer(company_id=seed['company_id'], store_id=seed['store_id'],
                                customer_code=f'C-{i:03d}', name=f'Khách {i}')
            db.session.add(customer)
            db.session.flush()
            order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                          customer_id=customer.id, order_code=f'ORD-{i:03d}',
                          title=f'Bọc lại sofa {i}')
            db.session.add(order)
            db.session.flush()
            db.session.add(LifecycleStatus(order_id=order.id))
        db.session.commit()


def _add_low_stock_materials(app, seed, start, count):
    """Materials below their minimum, so they also appear as suggestions."""
    from app.models.models import Material, MaterialStock, MaterialUnit
    with app.app_context():
        for i in range(start, start + count):
            unit = MaterialUnit(company_id=seed['company_id'], name=f'đv{i}')
            db.session.add(unit)
            db.session.flush()
            material = Material(company_id=seed['company_id'], material_code=f'NVL-{i:03d}',
                                name=f'Vải nhung {i}', unit_id=unit.id,
                                min_stock_level=10, unit_price=Decimal('50000'))
            db.session.add(material)
            db.session.flush()
            db.session.add(MaterialStock(material_id=material.id, company_id=seed['company_id'],
                                         store_id=seed['store_id'], current_quantity=1))
        db.session.commit()


def _add_requisitions(app, seed, start, count):
    from app.models.models import Material, PurchaseRequisition, PurchaseRequisitionLine
    with app.app_context():
        material = Material.query.filter_by(company_id=seed['company_id']).first()
        for i in range(start, start + count):
            pr = PurchaseRequisition(company_id=seed['company_id'], store_id=seed['store_id'],
                                     pr_number=f'PR-{i:03d}')
            db.session.add(pr)
            db.session.flush()
            db.session.add(PurchaseRequisitionLine(pr_id=pr.id, material_id=material.id,
                                                   quantity=2))
        db.session.commit()


@pytest.mark.parametrize('url, add_rows', [
    ('/orders', _add_orders),
    ('/materials/', _add_low_stock_materials),
    ('/materials/purchase-suggestions', _add_low_stock_materials),
    ('/requisitions', _add_requisitions),
])
def test_query_count_does_not_grow_with_rows(app, client, seed, login, url, add_rows):
    if add_rows is _add_requisitions:
        _add_low_stock_materials(app, seed, 900, 1)
    login('admin')

    add_rows(app, seed, 0, 2)
    with_two = _count_queries(app, client, url)

    add_rows(app, seed, 2, 6)
    with_eight = _count_queries(app, client, url)

    assert with_eight == with_two, (
        f'{url}: {with_two} queries for 2 rows, {with_eight} for 8 — '
        f'something on this screen is loaded one row at a time')


def test_order_advice_reads_the_workflow_rules_once(app, seeded_order):
    """The order screen asks every action for advice; one read serves them all."""
    from app.models.models import Order
    from app.services.workflow_service import ALL_ACTIONS, WorkflowService

    with app.app_context():
        order = Order.query.get(seeded_order['order_id'])
        order.lifecycle  # loaded here so only rule reads are counted below
        rule_reads = []

        def _record(conn, cursor, statement, params, context, executemany):
            if 'FROM workflow_rules' in statement:
                rule_reads.append(statement)

        event.listen(db.engine, 'before_cursor_execute', _record)
        try:
            WorkflowService.advisories(order)
        finally:
            event.remove(db.engine, 'before_cursor_execute', _record)

    assert len(ALL_ACTIONS) > 1
    assert len(rule_reads) == 1, (
        f'{len(rule_reads)} reads of workflow_rules for {len(ALL_ACTIONS)} actions')


def test_no_code_passes_a_legacy_query_to_db_paginate():
    """`db.paginate(Model.query...)` is the wrong call for a legacy Query.

    On SQLAlchemy 2.0 it silently drops the query's `.options()` (the per-row
    queries above). On 2.1 — which a fresh production image installs under the
    `<3.0` pin — it raises "Not an executable object", which took the whole
    customers list down when the suite was run on the production stack.
    Use `query.paginate(...)`.
    """
    import re
    app_dir = pathlib.Path(__file__).resolve().parents[1] / 'app'
    offenders = []
    for path in app_dir.rglob('*.py'):
        for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if re.search(r'(?<![\w.])db\.paginate\(', line.split('#', 1)[0]):
                offenders.append(f'{path.name}:{lineno}')
    assert offenders == [], f'db.paginate(...) calls: {offenders}'
