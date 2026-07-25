"""CSRF protection is enforced when enabled (W1, S1).

The rest of the suite runs with WTF_CSRF_ENABLED=False (TestingConfig) so it does
not need tokens. This test flips CSRF on and proves a tokenless POST is rejected.
"""


def test_post_without_csrf_token_is_rejected(monkeypatch, tmp_path):
    from app.config.config import TestingConfig
    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True, raising=False)
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI",
                        f"sqlite:///{tmp_path/'csrf.db'}", raising=False)

    from app import create_app
    from app.config import db

    app = create_app("testing")
    with app.app_context():
        db.create_all()

    client = app.test_client()
    resp = client.post("/auth/login", data={
        "company_code": "X", "username": "y", "password": "z",
    })
    assert resp.status_code == 400, "tokenless POST should be rejected by CSRF"


def test_check_code_api_is_csrf_exempt(monkeypatch, tmp_path):
    """The read-only code checker must stay usable (exempt) even with CSRF on."""
    from app.config.config import TestingConfig
    monkeypatch.setattr(TestingConfig, "WTF_CSRF_ENABLED", True, raising=False)
    monkeypatch.setattr(TestingConfig, "SQLALCHEMY_DATABASE_URI",
                        f"sqlite:///{tmp_path/'csrf2.db'}", raising=False)

    from app import create_app
    from app.config import db

    app = create_app("testing")
    with app.app_context():
        db.create_all()

    client = app.test_client()
    # Not logged in -> login_required should redirect (302), NOT a 400 CSRF error.
    resp = client.post("/api/check-code/order", json={"code": "X"})
    assert resp.status_code != 400, "check_code should be CSRF-exempt"
