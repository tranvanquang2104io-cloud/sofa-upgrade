"""Email + password login (replaces company_code + username + password)."""
import pytest


def test_login_with_email_reaches_dashboard(client, seed):
    client.post("/auth/login", data={"email": "admin@acme.test", "password": "secret123"},
                follow_redirects=True)
    assert client.get("/").status_code == 200


def test_login_email_is_case_insensitive(client, seed):
    client.post("/auth/login", data={"email": "ADMIN@Acme.Test", "password": "secret123"},
                follow_redirects=True)
    assert client.get("/").status_code == 200


def test_login_wrong_password_rejected(client, seed):
    client.post("/auth/login", data={"email": "admin@acme.test", "password": "nope"},
                follow_redirects=True)
    resp = client.get("/")
    assert resp.status_code == 302 and "/auth/login" in resp.headers["Location"]


def test_login_unknown_email_rejected(client, seed):
    client.post("/auth/login", data={"email": "nobody@acme.test", "password": "secret123"},
                follow_redirects=True)
    assert client.get("/").status_code == 302


def test_email_globally_unique(app, seed):
    from app.config import db
    from app.models.models import User
    with app.app_context():
        dup = User(company_id=seed["company_id"], username="dup",
                   email="admin@acme.test", full_name="Dup", role="user")
        dup.set_password("x")
        db.session.add(dup)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()
