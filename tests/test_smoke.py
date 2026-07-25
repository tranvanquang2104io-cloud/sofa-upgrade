"""Smoke tests — prove the harness (app boot, auth guard, real login) works."""


def test_app_boots(app):
    assert app is not None


def test_login_page_renders(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200


def test_dashboard_requires_auth(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_success_reaches_dashboard(login, client):
    resp = login()
    assert resp.status_code == 200
    # Session established → dashboard now reachable without redirect.
    resp2 = client.get("/")
    assert resp2.status_code == 200


def test_login_wrong_password_rejected(login, client):
    login(password="wrong-password")
    # Still unauthenticated → protected page redirects to login.
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
