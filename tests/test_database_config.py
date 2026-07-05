import pytest

from app.db.config import get_database_url


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr("app.db.config.load_env", lambda: {})

    with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is not set"):
        get_database_url()


def test_database_url_uses_explicit_environment_value(monkeypatch):
    database_url = "sqlite://"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr("app.db.config.load_env", lambda: {})

    assert get_database_url() == database_url
