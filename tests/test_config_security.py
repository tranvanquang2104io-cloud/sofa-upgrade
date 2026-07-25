"""Config hardening tests (W3, W4)."""
import os

import pytest


def test_production_refuses_default_secret_key(monkeypatch):
    """create_app('production') must fail fast when SECRET_KEY is not overridden."""
    from app import create_app
    from app.config.config import ProductionConfig

    # Ensure the config carries the insecure default (no real secret in env).
    monkeypatch.setattr(ProductionConfig, "SECRET_KEY",
                        "dev-secret-key-change-in-production", raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")


def test_production_starts_with_real_secret_key(monkeypatch, tmp_path):
    """With a real SECRET_KEY set, production app builds fine."""
    from app import create_app
    from app.config.config import ProductionConfig

    monkeypatch.setattr(ProductionConfig, "SECRET_KEY", "a-real-strong-secret", raising=False)
    # Point the prod DB at a temp sqlite file so no external DB is needed to build.
    monkeypatch.setattr(ProductionConfig, "SQLALCHEMY_DATABASE_URI",
                        f"sqlite:///{tmp_path/'p.db'}", raising=False)
    app = create_app("production")
    assert app is not None
