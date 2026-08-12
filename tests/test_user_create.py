"""Creating a user via the admin form works and stores feature grants."""


def test_admin_creates_staff_with_features(app, client, login, seed):
    from app.models.models import User
    login(username='admin')
    r = client.post('/users/create', data={
        'username': 'nvmoi', 'email': 'nvmoi@acme.test', 'password': 'Pass@123',
        'full_name': 'Nhân viên mới', 'role': 'user', 'store_id': seed['store_id'],
        'features': ['customers', 'orders'],
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        u = User.query.filter_by(username='nvmoi', company_id=seed['company_id']).first()
        assert u is not None
        assert u.check_password('Pass@123')
        assert set(u.allowed_features) == {'customers', 'orders'}
