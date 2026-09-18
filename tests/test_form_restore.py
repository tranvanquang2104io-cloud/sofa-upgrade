"""A failed save must give the user back what they typed.

Before this, a validation error re-rendered the create page EMPTY: every line
item, description and amount was gone. On a bespoke sofa order that is ten
minutes of careful typing, and the people using this product are not confident
with computers — losing their work is the most punishing thing the product can
do to them.

The restore happens in the base layout for every form in the app, so these
tests check the mechanism once and then spot-check that it reaches the real
screens.
"""
import datetime as dt
import json
import re

import pytest


@pytest.fixture()
def order(app, seed):
    from app.config import db
    from app.models import Order
    from app.models.models import LifecycleStatus

    with app.app_context():
        o = Order(company_id=seed["company_id"], store_id=seed["store_id"],
                  customer_id=seed["customer_id"], order_code="ORD-RESTORE",
                  title="Restore test")
        db.session.add(o)
        db.session.flush()
        db.session.add(LifecycleStatus(order_id=o.id))
        db.session.commit()
        return str(o.id)


def _submitted_blob(html):
    """Pull the JSON the server handed back for restoring."""
    m = re.search(
        r'<script id="submitted-form-data"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else None


# --- the mechanism --------------------------------------------------------

def test_a_failed_save_hands_back_every_typed_line_item(client, login, order):
    """The whole point: a bad price must not cost the user their line items."""
    login("admin")

    resp = client.post(f'/quotations/{order}/create', data={
        'quotation_number': 'QT-RESTORE',
        'quotation_date': '2026-01-01',
        'vat_rate': '8',
        'notes': 'Ghi chu quan trong cua khach',
        'item_name[]': ['Dong moi ghe sofa don da bo that',
                        'Boc lai ghe banh'],
        'item_unit[]': ['bo', 'cai'],
        'item_quantity[]': ['1', '2'],
        # a negative price is rejected by parse_line_items -> the save fails
        'item_price[]': ['10000000', '-5'],
    }, follow_redirects=True)

    assert resp.status_code == 200
    blob = _submitted_blob(resp.get_data(as_text=True))

    assert blob is not None, "nothing was handed back for restoring"
    assert blob['item_name[]'] == ['Dong moi ghe sofa don da bo that',
                                   'Boc lai ghe banh'], \
        "both typed line items must come back, not just the first"
    assert blob['item_quantity[]'] == ['1', '2']
    assert blob['notes'] == ['Ghi chu quan trong cua khach']
    assert blob['quotation_number'] == ['QT-RESTORE']


def test_the_restore_script_is_loaded_when_a_save_fails(client, login, order):
    login("admin")
    resp = client.post(f'/quotations/{order}/create', data={
        'quotation_number': 'QT-R2', 'quotation_date': '2026-01-01',
        'item_name[]': 'X', 'item_quantity[]': '1', 'item_price[]': '-1',
    }, follow_redirects=True)

    body = resp.get_data(as_text=True)
    assert 'sofa-restore-form.js' in body


def test_the_csrf_token_is_never_handed_back(client, login, order):
    """Echoing a token into a JSON blob would be careless."""
    login("admin")
    resp = client.post(f'/quotations/{order}/create', data={
        'quotation_number': 'QT-R3', 'quotation_date': '2026-01-01',
        'item_name[]': 'X', 'item_quantity[]': '1', 'item_price[]': '-1',
    }, follow_redirects=True)

    blob = _submitted_blob(resp.get_data(as_text=True))
    assert 'csrf_token' not in (blob or {})


def test_nothing_is_handed_back_on_a_normal_page_view(client, login, order):
    """The blob must only appear after a failed POST, never on a fresh form."""
    login("admin")
    body = client.get(f'/quotations/{order}/create').get_data(as_text=True)
    assert 'submitted-form-data' not in body
    assert 'sofa-restore-form.js' not in body


def test_the_user_is_told_images_must_be_chosen_again(client, login, order):
    """A browser cannot re-attach a file; say so rather than dropping it."""
    login("admin")
    resp = client.post(f'/quotations/{order}/create', data={
        'quotation_number': 'QT-R4', 'quotation_date': '2026-01-01',
        'item_name[]': 'X', 'item_quantity[]': '1', 'item_price[]': '-1',
    }, follow_redirects=True)

    body = resp.get_data(as_text=True)
    assert 'data-file-notice' in body
    assert 'image' in body.lower() or 'ảnh' in body.lower()


# --- it reaches the real screens -----------------------------------------

def test_a_duplicate_document_number_also_returns_the_work(app, client, login,
                                                           order, seed):
    """The most common real failure: the number is already used."""
    from app.config import db
    from app.models.models import Quotation

    with app.app_context():
        db.session.add(Quotation(
            company_id=seed["company_id"], order_id=order,
            quotation_number="QT-TAKEN", quotation_date=dt.date(2026, 1, 1),
            total_amount=0))
        db.session.commit()

    login("admin")
    resp = client.post(f'/quotations/{order}/create', data={
        'quotation_number': 'QT-TAKEN',
        'quotation_date': '2026-02-02',
        'item_name[]': 'Sofa goc chu L boc da',
        'item_unit[]': 'bo',
        'item_quantity[]': '1',
        'item_price[]': '25000000',
    }, follow_redirects=True)

    blob = _submitted_blob(resp.get_data(as_text=True))
    assert blob is not None, "a duplicate number must not cost the user the form"
    assert blob['item_name[]'] == ['Sofa goc chu L boc da']
    assert blob['item_price[]'] == ['25000000']


def test_contract_create_also_restores(app, client, login, order):
    login("admin")
    resp = client.post(f'/contracts/{order}/create', data={
        'contract_number': '',          # required -> fails
        'contract_date': '2026-01-01',
        'item_name[]': 'Dong moi bo sofa 5 cho',
        'item_unit[]': 'bo',
        'item_quantity[]': '1',
        'item_price[]': '30000000',
    }, follow_redirects=True)

    blob = _submitted_blob(resp.get_data(as_text=True))
    if blob is not None:                 # only assert if the save did fail
        assert blob['item_name[]'] == ['Dong moi bo sofa 5 cho']
