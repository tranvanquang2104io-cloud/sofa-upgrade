"""A field on a form must reach the record, or it must not be on the form.

The handover create screen asks for "Thời gian bàn giao" as a single `<input
type="time" name="handover_time">`. No column of that name exists on
`HandoverRecord`, and no line of Python reads the value. The user types the time
the sofa was delivered, presses Save, and it is gone — with a success message.

The model has `start_time` and `end_time`, a FROM and a TO, which is what a
biên bản bàn giao actually records: the delivery team arrived at 08:00 and
finished at 10:00. The edit screen offers both, correctly, plus `copies_count`
— so re-opening a record shows fields the create screen never asked about, and
hides the one it did.

That asymmetry is how the dead field survived: nobody comparing the two screens
would see `handover_time` on the second one to wonder where it went.

This is the worst shape a form field can have. A missing field is visibly
missing. A field that accepts input and discards it looks like it worked.
"""
import datetime as dt
import io
import pathlib
import re

import pytest

TEMPLATES = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'templates'


@pytest.fixture()
def order_ready_for_handover(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import Contract, LifecycleStatus

    with app.app_context():
        order = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                      customer_id=seed['customer_id'], order_code='DH-TIME',
                      title='Sofa góc L', total_amount=20_000_000)
        db.session.add(order)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=order.id,
                                       quotation_created=True,
                                       contract_created=True,
                                       contract_signed=True))
        db.session.add(Contract(
            company_id=seed['company_id'], order_id=order.id,
            contract_number='HD-TIME', contract_date=dt.date(2026, 9, 1),
            contract_value=20_000_000, advance_percentage=0,
            is_signed=True, is_active=True))
        db.session.commit()
        return {**seed, 'order_id': str(order.id)}


def test_the_create_form_asks_for_the_fields_the_record_has():
    """`handover_time` is on no model and read by no code."""
    text = io.open(TEMPLATES / 'handover' / 'create.html', encoding='utf-8').read()
    assert 'name="handover_time"' not in text, (
        'the form still collects a value nothing stores'
    )


@pytest.mark.parametrize('field', ['start_time', 'end_time'])
def test_the_create_form_offers_both_ends_of_the_window(field):
    """A biên bản records from-and-to, which is what the model holds."""
    text = io.open(TEMPLATES / 'handover' / 'create.html', encoding='utf-8').read()
    assert f'name="{field}"' in text, f'{field} cannot be entered at creation'


def test_the_times_survive_being_saved(client, login, app,
                                       order_ready_for_handover):
    """Through the screen, because the point is that it was silently lost."""
    from app.models.models import HandoverRecord

    login('admin')
    client.post(f"/handover/{order_ready_for_handover['order_id']}/create",
                data={
                    'report_number': 'BB-TIME',
                    'report_date': '2026-09-20',
                    'handover_date': '2026-09-20',
                    'start_time': '08:00',
                    'end_time': '10:30',
                    'item_name[]': ['Sofa góc L'],
                    'item_quantity[]': ['1'],
                    'item_price[]': ['20000000'],
                }, follow_redirects=True)

    with app.app_context():
        record = HandoverRecord.query.filter_by(report_number='BB-TIME').first()
        assert record is not None, 'the handover was not created at all'
        assert record.start_time == '08:00', (
            f'the start time was discarded (stored {record.start_time!r})')
        assert record.end_time == '10:30', (
            f'the end time was discarded (stored {record.end_time!r})')


def test_no_form_field_is_read_by_nothing():
    """Close the class: every named input must be looked for somewhere.

    Scoped to the handover screens, since a product-wide sweep turns up
    JavaScript-only fields and would need its own exemption list. This one
    keeps the pair honest with each other.
    """
    import pathlib as _p

    routes = io.open(
        _p.Path(__file__).resolve().parents[1] / 'app' / 'routes'
        / 'dashboard_routes.py', encoding='utf-8').read()

    orphans = []
    for screen in ('handover/create.html', 'handover/edit.html'):
        text = io.open(TEMPLATES / screen, encoding='utf-8').read()
        for name in set(re.findall(r'name="([a-z_]+)"', text)):
            if name in ('csrf_token',):
                continue
            if f"'{name}'" in routes or f'"{name}"' in routes:
                continue
            orphans.append(f'{screen}: {name}')

    assert orphans == [], (
        'these inputs accept what the user types and nothing ever reads them: '
        f'{sorted(orphans)}')
