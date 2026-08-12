"""Per-user feature permissions (RBAC)."""


def _grant(app, user_id, features):
    from app.config import db
    from app.models.models import User
    with app.app_context():
        u = User.query.get(user_id)
        u.allowed_features = features
        db.session.commit()


def test_staff_limited_to_granted_features(app, client, login, seed):
    _grant(app, seed['staff_id'], ['customers'])   # staff can only do customers
    login(username='staff')
    assert client.get('/customers').status_code == 200
    assert client.get('/orders').status_code == 403          # not granted
    assert client.get('/materials/').status_code == 403      # inventory not granted


def test_staff_with_orders_feature(app, client, login, seed):
    _grant(app, seed['staff_id'], ['customers', 'orders'])
    login(username='staff')
    assert client.get('/customers').status_code == 200
    assert client.get('/orders').status_code == 200
    assert client.get('/purchase-orders').status_code == 403


def test_admin_has_all_features(app, client, login, seed):
    login(username='admin')   # company_admin
    for url in ('/customers', '/orders', '/materials/', '/purchase-orders', '/requisitions'):
        assert client.get(url).status_code == 200, url
