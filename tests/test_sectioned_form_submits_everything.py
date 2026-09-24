"""Splitting a form into sections must not drop what comes after a section.

The quotation form was grouped into three `form_section(...)` blocks. A wrapper
closed in the wrong place would leave the later fields OUTSIDE the `<form>`,
and the browser would simply not send them — a silent loss with a success
message, which is the same failure shape as the handover time field that no
column held.

The third section holds the notes, payment terms and amount-in-words. This
creates a quotation through the screen and checks the last of them arrives.
"""
import datetime as dt

import pytest


@pytest.fixture()
def order(app, seed):
    from app.config import db
    from app.models import Order

    with app.app_context():
        record = Order(company_id=seed['company_id'], store_id=seed['store_id'],
                       customer_id=seed['customer_id'], order_code='DH-SECT',
                       title='Sofa góc L')
        db.session.add(record)
        db.session.commit()
        return {**seed, 'order_id': str(record.id)}


def test_a_field_in_the_last_section_reaches_the_record(app, client, login,
                                                        order):
    from app.models.models import Quotation

    login('admin')
    client.post(f"/quotations/{order['order_id']}/create", data={
        'quotation_number': 'BG-SECT-1',
        'quotation_date': '2026-09-20',
        'item_name[]': ['Sofa góc L'],
        'item_quantity[]': ['1'],
        'item_price[]': ['40000000'],
        # All three live in the third section, after two section wrappers.
        'notes': 'Giao trước Tết',
        'payment_terms': 'Chuyển khoản 50/50',
        'amount_in_words': 'Bốn mươi triệu đồng',
    }, follow_redirects=True)

    with app.app_context():
        quotation = Quotation.query.filter_by(
            quotation_number='BG-SECT-1').first()
        assert quotation is not None, 'the quotation was not created at all'
        assert quotation.notes == 'Giao trước Tết', (
            'a field after the second section wrapper never reached the server')
        assert quotation.payment_terms == 'Chuyển khoản 50/50'
