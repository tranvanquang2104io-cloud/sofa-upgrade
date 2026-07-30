"""Extension fields work on master data (customer) create flow."""


def _enable(app, company_id, entity, field_key='extend01', label='Nguồn KH', dt='text', required=False):
    from app.config import db
    from app.models.models import ExtensionFieldConfig
    with app.app_context():
        db.session.add(ExtensionFieldConfig(
            company_id=company_id, entity_type=entity, field_key=field_key,
            is_enabled=True, label=label, data_type=dt, is_required=required))
        db.session.commit()


def test_customer_extension_field_saved_on_create(app, client, login, seed):
    from app.models.models import Customer
    _enable(app, seed['company_id'], 'customer', label='Nguồn khách')
    login(username='admin')
    # the create form should render the enabled field label
    r = client.get('/customers/create')
    assert r.status_code == 200
    assert 'Nguồn khách'.encode() in r.data
    client.post('/customers/create', data={
        'store_id': seed['store_id'], 'customer_code': 'KH-EXT', 'name': 'KH mở rộng',
        'extend01': 'Facebook Ads',
    }, follow_redirects=True)
    with app.app_context():
        c = Customer.query.filter_by(company_id=seed['company_id'], customer_code='KH-EXT').first()
        assert c is not None
        assert c.extend01 == 'Facebook Ads'


def test_required_extension_field_blocks_create(app, client, login, seed):
    from app.models.models import Customer
    _enable(app, seed['company_id'], 'customer', field_key='extend02', label='Bắt buộc', required=True)
    login(username='admin')
    client.post('/customers/create', data={
        'store_id': seed['store_id'], 'customer_code': 'KH-REQ', 'name': 'X',
        # extend02 intentionally omitted
    }, follow_redirects=True)
    with app.app_context():
        assert Customer.query.filter_by(company_id=seed['company_id'], customer_code='KH-REQ').first() is None
