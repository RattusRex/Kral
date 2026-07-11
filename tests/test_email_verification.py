import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("EMAIL_BACKEND", "console")

TEST_USER_PASSWORD = "Strong-Test-Pass-47!"

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.project import ProjectMembership
from app.models.user import User


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def register(client: TestClient, email: str = "new@example.com"):
    return client.post("/api/users", json={
        "username": "new-player",
        "email": email,
        "password": TEST_USER_PASSWORD,
    })


def admin_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_registration_creates_inactive_user_and_sends_confirmation(monkeypatch):
    delivered = []
    monkeypatch.setattr(
        "app.api.users.send_verification_email",
        lambda email, username, token: delivered.append((email, username, token)),
    )

    with TestClient(app) as client:
        response = register(client)
        assert response.status_code == 200, response.text
        assert response.json()["email_verified"] is False
        assert response.json()["message"] == "Verification email sent"
        assert len(delivered) == 1

        login = client.post(
            "/api/login",
            data={"username": "new-player", "password": TEST_USER_PASSWORD},
        )
        assert login.status_code == 403
        assert login.json()["detail"]["code"] == "email_not_verified"


def test_smtp_delivery_is_attempted_with_configured_sender(monkeypatch):
    sent_messages = []

    class FakeSmtp:
        def __init__(self, host, port):
            assert (host, port) == ("smtp.example.com", 2525)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def starttls(self):
            pass

        def login(self, username, password):
            assert (username, password) == ("smtp-user", "smtp-password")

        def send_message(self, message):
            sent_messages.append(message)

    monkeypatch.setenv("EMAIL_BACKEND", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "2525")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "Kral <no-reply@example.com>")
    monkeypatch.setenv("FRONTEND_URL", "https://kral.example.com")
    monkeypatch.setattr("app.core.email_verification.smtplib.SMTP", FakeSmtp)

    with TestClient(app) as client:
        response = register(client)

    assert response.status_code == 200, response.text
    assert len(sent_messages) == 1
    message = sent_messages[0]
    assert message["From"] == "Kral <no-reply@example.com>"
    assert message["To"] == "new@example.com"
    assert "https://kral.example.com/verify-email?token=" in message.get_content()


def test_smtp_configuration_is_validated_before_registration():
    from app.core.email_verification import validate_email_configuration

    with patch.dict(os.environ, {"EMAIL_BACKEND": "smtp"}, clear=True):
        try:
            validate_email_configuration()
        except RuntimeError as error:
            assert "SMTP_HOST" in str(error)
            assert "SMTP_FROM_EMAIL" in str(error)
        else:
            raise AssertionError("Incomplete SMTP settings must fail validation")


def test_confirmation_token_is_single_use(monkeypatch):
    tokens = []
    monkeypatch.setattr(
        "app.api.users.send_verification_email",
        lambda _email, _username, token: tokens.append(token),
    )

    with TestClient(app) as client:
        register(client)
        confirmed = client.post("/api/email/verify", json={"token": tokens[0]})
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["email_verified"] is True

        replay = client.post("/api/email/verify", json={"token": tokens[0]})
        assert replay.status_code == 400
        assert replay.json()["detail"] == "Invalid or expired verification token"

        login = client.post(
            "/api/login",
            data={"username": "new-player", "password": TEST_USER_PASSWORD},
        )
        assert login.status_code == 200, login.text
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        me = client.get("/api/me", headers=headers)
        projects = client.get("/api/projects", headers=headers)
        current_project = client.get("/api/projects/current", headers=headers)
        assert me.status_code == 200, me.text
        assert me.json()["email_verified"] is True
        assert projects.status_code == 200, projects.text
        assert len(projects.json()) == 1
        assert current_project.status_code == 200, current_project.text

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "new@example.com").one()
            assert db.query(ProjectMembership).filter_by(user_id=user.id).count() == 1


def test_resend_rotates_token_and_expired_token_is_rejected(monkeypatch):
    tokens = []
    monkeypatch.setattr(
        "app.api.users.send_verification_email",
        lambda _email, _username, token: tokens.append(token),
    )

    with TestClient(app) as client:
        register(client)
        resent = client.post("/api/email/resend", json={"email": "new@example.com"})
        assert resent.status_code == 200, resent.text
        assert len(tokens) == 2
        assert tokens[0] != tokens[1]
        assert client.post("/api/email/verify", json={"token": tokens[0]}).status_code == 400

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "new@example.com").one()
            user.email_verification_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        assert client.post("/api/email/verify", json={"token": tokens[1]}).status_code == 400


def test_admin_can_see_and_manually_verify_email(monkeypatch):
    monkeypatch.setattr("app.api.users.send_verification_email", lambda *_args: None)

    with TestClient(app) as client:
        register(client)
        headers = admin_headers(client)
        users = client.get("/api/admin/users", headers=headers)
        row = next(item for item in users.json() if item["email"] == "new@example.com")
        assert row["email_verified"] is False
        assert row["email_verified_at"] is None

        verified = client.post(
            f"/api/admin/users/{row['id']}/verify-email",
            headers=headers,
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["email_verified"] is True
        assert verified.json()["email_verified_at"] is not None


def test_schema_migration_marks_legacy_users_verified():
    from sqlalchemy import text

    with engine.begin() as connection:
        connection.execute(text("DROP TABLE users"))
        connection.execute(text(
            "CREATE TABLE users ("
            "id INTEGER PRIMARY KEY, username VARCHAR(50) UNIQUE, "
            "email VARCHAR(255) UNIQUE, hashed_password VARCHAR NOT NULL, "
            "karma INTEGER DEFAULT 0, role VARCHAR(20) DEFAULT 'player'"
            ")"
        ))
        connection.execute(text(
            "INSERT INTO users (id, username, email, hashed_password) "
            "VALUES (1, 'legacy', 'legacy@example.com', 'unused')"
        ))

    from app.main import migrate_email_verification
    migrate_email_verification()

    with engine.begin() as connection:
        row = connection.execute(text(
            "SELECT email_verified FROM users WHERE id = 1"
        )).one()
    assert bool(row.email_verified) is True
