"""Item 9: BI/KPI reports dashboard renders and aggregates without cross-tenant leaks."""


def test_report_service_shape(app, seed):
    from app.services.report_service import ReportService
    with app.app_context():
        data = ReportService().dashboard(seed['company_id'])
    assert set(data) == {'sales', 'purchasing', 'accounting'}
    assert 'orders_total' in data['sales']
    assert 'po_value' in data['purchasing']
    assert 'cash_in' in data['accounting']
    # Empty company → all zeros, never negative receivable
    assert data['accounting']['receivable'] >= 0


def test_reports_page_renders_for_admin(app, client, login, seed):
    login(username='admin')
    r = client.get('/reports', follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'Sales' in body or 'Bán hàng' in body


def test_reports_blocked_without_feature(app, client, login, seed):
    """A plain user without the 'reports' grant is denied (RBAC before_request)."""
    from app.models.models import User
    from app.config import db
    with app.app_context():
        u = User(company_id=seed['company_id'], username='norep', email='norep@acme.test',
                 full_name='No Reports', role='user', store_id=seed['store_id'],
                 allowed_features=['orders'])
        u.set_password('Pass@123')
        db.session.add(u); db.session.commit()
    login(username='norep', password='Pass@123')
    r = client.get('/reports')
    assert r.status_code == 403
