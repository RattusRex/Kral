import os
from datetime import datetime, timedelta, timezone

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("EMAIL_BACKEND", "console")

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.user import User


OLD_PASSWORD = "old-password"
NEW_PASSWORD = "new-password"
GENERIC_MESSAGE = (
    "Если аккаунт с указанным адресом существует, письмо для восстановления "
    "пароля было отправлено."
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def create_verified_user(client: TestClient) -> None:
    from app.core.security import hash_password

    with SessionLocal() as db:
        db.add(User(
            username="reset-player",
            email="reset@example.com",
            hashed_password=hash_password(OLD_PASSWORD),
            email_verified=True,
            email_verified_at=datetime.now(timezone.utc),
        ))
        db.commit()


def request_token(client: TestClient, monkeypatch) -> str:
    tokens: list[str] = []
    monkeypatch.setattr(
        "app.api.users.send_password_reset_email",
        lambda _email, _username, token: tokens.append(token),
    )
    response = client.post("/api/password/forgot", json={"email": "RESET@example.com"})
    assert response.status_code == 200, response.text
    assert response.json() == {"message": GENERIC_MESSAGE}
    assert len(tokens) == 1
    return tokens[0]


def login(client: TestClient, password: str):
    reset_auth_abuse_state()
    return client.post(
        "/api/login",
        data={"username": "reset@example.com", "password": password},
    )


def test_forgot_password_is_neutral_for_known_and_unknown_addresses(monkeypatch):
    delivered: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.api.users.send_password_reset_email",
        lambda email, username, token: delivered.append((email, username, token)),
    )

    with TestClient(app) as client:
        create_verified_user(client)
        known = client.post("/api/password/forgot", json={"email": "RESET@example.com"})
        unknown = client.post("/api/password/forgot", json={"email": "missing@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"message": GENERIC_MESSAGE}
    assert len(delivered) == 1
    assert delivered[0][0:2] == ("reset@example.com", "reset-player")
    assert len(delivered[0][2]) >= 32


def test_forgot_password_is_rate_limited_by_email(monkeypatch):
    monkeypatch.setattr("app.core.auth_abuse.PASSWORD_RESET_LIMIT", 2)
    monkeypatch.setattr("app.core.auth_abuse.PASSWORD_RESET_IP_LIMIT", 100)
    monkeypatch.setattr("app.api.users.send_password_reset_email", lambda *_args: None)

    with TestClient(app) as client:
        create_verified_user(client)
        assert client.post(
            "/api/password/forgot", json={"email": "reset@example.com"}
        ).status_code == 200
        assert client.post(
            "/api/password/forgot", json={"email": "reset@example.com"}
        ).status_code == 200
        limited = client.post(
            "/api/password/forgot", json={"email": "reset@example.com"}
        )

    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


def test_reset_token_is_hashed_rotated_expiring_and_single_use(monkeypatch):
    with TestClient(app) as client:
        create_verified_user(client)
        first_token = request_token(client, monkeypatch)
        with SessionLocal() as db:
            user = db.query(User).filter_by(email="reset@example.com").one()
            assert user.password_reset_token_hash
            assert user.password_reset_token_hash != first_token
            first_hash = user.password_reset_token_hash

        second_token = request_token(client, monkeypatch)
        assert second_token != first_token
        assert client.post("/api/password/reset", json={
            "token": first_token,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        }).status_code == 400

        reset = client.post("/api/password/reset", json={
            "token": second_token,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        })
        assert reset.status_code == 200, reset.text

        replay = client.post("/api/password/reset", json={
            "token": second_token,
            "password": "another-password",
            "password_confirmation": "another-password",
        })
        assert replay.status_code == 400
        with SessionLocal() as db:
            user = db.query(User).filter_by(email="reset@example.com").one()
            assert user.password_reset_token_hash is None
            assert user.password_reset_expires_at is None
            assert user.hashed_password not in (OLD_PASSWORD, NEW_PASSWORD)
            assert first_hash != user.hashed_password

        assert login(client, OLD_PASSWORD).status_code == 401
        assert login(client, NEW_PASSWORD).status_code == 200


def test_expired_reset_token_is_rejected(monkeypatch):
    with TestClient(app) as client:
        create_verified_user(client)
        token = request_token(client, monkeypatch)
        with SessionLocal() as db:
            user = db.query(User).filter_by(email="reset@example.com").one()
            user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()

        response = client.post("/api/password/reset", json={
            "token": token,
            "password": NEW_PASSWORD,
            "password_confirmation": NEW_PASSWORD,
        })
        assert response.status_code == 400


def test_reset_enforces_current_password_policy_and_confirmation(monkeypatch):
    with TestClient(app) as client:
        create_verified_user(client)
        token = request_token(client, monkeypatch)

        too_short = client.post("/api/password/reset", json={
            "token": token,
            "password": "12345",
            "password_confirmation": "12345",
        })
        assert too_short.status_code == 422
        assert too_short.json()["detail"] == "Пароль должен содержать не менее 6 символов"

        mismatch = client.post("/api/password/reset", json={
            "token": token,
            "password": NEW_PASSWORD,
            "password_confirmation": "different-password",
        })
        assert mismatch.status_code == 422


def test_password_reset_email_contains_public_single_use_link(monkeypatch):
    from app.core.email_verification import send_password_reset_email

    monkeypatch.setenv("EMAIL_BACKEND", "console")
    monkeypatch.setenv("FRONTEND_URL", "https://kral.example.com")
    messages: list[str] = []
    monkeypatch.setattr(
        "app.core.email_verification.logger.info",
        lambda message, *_args: messages.append(message % _args),
    )

    send_password_reset_email("reset@example.com", "reset-player", "secret-token")

    assert any(
        "https://kral.example.com/reset-password?token=secret-token" in message
        for message in messages
    )


def test_password_reset_email_uses_configured_smtp_without_exposing_token(monkeypatch, caplog):
    from app.core.email_verification import send_password_reset_email

    sent = []

    class FakeSmtp:
        def __init__(self, host, port, *, timeout):
            assert (host, port, timeout) == ("smtp.example.com", 587, 10)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self, *, context):
            assert context is not None

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setenv("EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("FRONTEND_URL", "https://kral.example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_SECURITY", "starttls")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setattr("app.core.email_verification.smtplib.SMTP", FakeSmtp)

    token = "secret-reset-token-which-is-long-enough"
    with caplog.at_level("INFO", logger="app.core.email_verification"):
        send_password_reset_email("reset@example.com", "reset-player", token)

    assert len(sent) == 1
    assert sent[0]["Subject"] == "Восстановление пароля"
    assert f"/reset-password?token={token}" in sent[0].get_content()
    assert token not in caplog.text


def test_password_reset_columns_are_added_to_legacy_user_table():
    from sqlalchemy import inspect, text
    from app.main import migrate_password_reset

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE users"))
        connection.execute(text(
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE, "
            "email VARCHAR(255) UNIQUE, hashed_password VARCHAR NOT NULL)"
        ))

    migrate_password_reset()

    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    assert {"password_reset_token_hash", "password_reset_expires_at"} <= columns
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
