"""Clearing an optional field on update must persist as empty (regression)."""


def test_customer_update_can_clear_email(app, client, login, seed):
    from app.config import db
    from app.models.models import Customer
    cid, sid = seed['company_id'], seed['store_id']
    with app.app_context():
        c = Customer(company_id=cid, store_id=sid, customer_code='KH-CLR', name='KH',
                     email='typo@wrong.com', phone='0900')
        db.session.add(c); db.session.commit()
        cust_id = str(c.id)
    login(username='admin')
    # submit edit with email + phone cleared (blank), name kept
    client.post(f'/customers/{cust_id}/edit', data={
        'name': 'KH', 'email': '', 'phone': '', 'tax_code': '', 'representative_name': '',
        'representative_title': '', 'address': '', 'city': '', 'postal_code': '', 'country': '', 'notes': '',
    }, follow_redirects=True)
    with app.app_context():
        c = Customer.query.get(cust_id)
        assert not c.email, f'email should be cleared, got {c.email!r}'
        assert not c.phone, f'phone should be cleared, got {c.phone!r}'
        assert c.name == 'KH'   # required field kept
