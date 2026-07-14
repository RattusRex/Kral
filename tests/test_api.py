import os
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import anyio
import pytest

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

TEST_USER_PASSWORD = "Strong-Test-Pass-47!"

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.types import Message, Scope

from app.core.auth_abuse import reset_auth_abuse_state
from app.core.request_limits import RequestBodyLimitMiddleware
from app.core.text_limits import MAX_CHAT_MESSAGE_LENGTH, MAX_INVENTORY_NOTES_LENGTH
from app.core.security import ACCESS_TOKEN_LIFETIME, ALGORITHM, SECRET_KEY
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.api.admin import apply_xp_delta
from app.api.inventory import consume_quote_for_inventory
from app.models.character import CalendarAuditLog, Character
from app.models.chat import ChatMessage
from app.models.inventory import ShopQuote, ShopTransactionLog, TransferLog
from app.models.recruitment import GameApplication, GameRecruitment, RecruitmentMessage
from app.models.user import User
from app.models.project import DEFAULT_PROJECT_NAME, Project, ProjectMembership


class ProjectAwareTestClient(TestClient):
    """Select the legacy default project for pre-project feature tests."""

    def request(self, method, url, **kwargs):
        headers = dict(kwargs.pop("headers", {}) or {})
        if url.startswith("/api/") and url not in (
            "/api/login", "/api/users", "/api/projects"
        ) and "X-Project-ID" not in headers:
            with SessionLocal() as db:
                project_id = db.query(Project.id).filter(
                    Project.name == DEFAULT_PROJECT_NAME
                ).scalar()
            if project_id is not None:
                headers["X-Project-ID"] = str(project_id)
        return super().request(method, url, headers=headers, **kwargs)


TestClient = ProjectAwareTestClient


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client: TestClient, username: str, password: str) -> str:
    verify_registered_users()
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def verify_registered_users() -> None:
    """Keep legacy feature tests focused on their domain after registration."""
    with SessionLocal() as db:
        db.query(User).update({User.email_verified: True})
        db.commit()


def create_project_fixture(name: str, owner_id: int, members: list[tuple[int, str]]) -> int:
    with SessionLocal() as db:
        project = Project(name=name, owner_id=owner_id, settings={})
        db.add(project)
        db.flush()
        db.add_all([
            ProjectMembership(project_id=project.id, user_id=user_id, role=role)
            for user_id, role in members
        ])
        db.commit()
        return project.id


def register_verified_user(client: TestClient, username: str, role: str = "player") -> int:
    password = "Cobalt!River7Lantern"
    response = client.post("/api/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
    })
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        user.email_verified = True
        user.role = role
        db.commit()
        return user.id


def test_only_owner_can_delete_user_and_related_rows_without_orphans():
    with TestClient(app) as client:
        owner_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        target_id = register_verified_user(client, "delete-target")
        admin_id = register_verified_user(client, "delete-admin", "admin")

        with SessionLocal() as db:
            project = db.query(Project).filter(Project.name == DEFAULT_PROJECT_NAME).one()
            db.query(ProjectMembership).filter_by(user_id=admin_id).update({
                ProjectMembership.role: "admin",
            })
            character = Character(
                name="Disposable Hero", class_name="Wizard",
                class_levels=[{"class_name": "Wizard", "level": 1}],
                level=1, route="Arcane", user_id=target_id, project_id=project.id,
            )
            db.add(character)
            db.flush()
            recruitment = GameRecruitment(
                author_id=admin_id, project_id=project.id,
                real_date=date.today(), game_date=date.today(),
                start_time=datetime.now().time(), duration="4h", location="Hall", quest="Test",
            )
            db.add(recruitment)
            db.flush()
            db.add_all([
                ChatMessage(user_id=target_id, project_id=project.id, username="delete-target", content="Bye"),
                GameApplication(recruitment_id=recruitment.id, user_id=target_id, character_id=character.id),
                RecruitmentMessage(recruitment_id=recruitment.id, user_id=target_id, username="delete-target", content="Bye"),
                CalendarAuditLog(
                    user_id=target_id, username="delete-target", role="player",
                    character_id=character.id, character_name=character.name,
                    action="create", entry_id=1, details="Test",
                ),
                TransferLog(
                    user_id=target_id, username="delete-target",
                    sender_character_id=character.id, sender_character_name=character.name,
                    recipient_character_id=character.id, recipient_character_name=character.name,
                    transfer_type="gold", gold=1,
                ),
            ])
            db.commit()

        admin_headers = {
            "Authorization": f"Bearer {login(client, 'delete-admin', 'Cobalt!River7Lantern')}"
        }
        assert client.delete(f"/api/admin/users/{target_id}", headers=admin_headers).status_code == 403
        assert client.delete(f"/api/admin/users/{target_id}", headers=owner_headers).status_code == 200

        with SessionLocal() as db:
            assert db.get(User, target_id) is None
            assert db.query(Character).filter_by(user_id=target_id).count() == 0
            assert db.query(ProjectMembership).filter_by(user_id=target_id).count() == 0
            assert db.query(ChatMessage).filter_by(user_id=target_id).count() == 0
            assert db.query(GameApplication).filter_by(user_id=target_id).count() == 0
            assert db.query(RecruitmentMessage).filter_by(user_id=target_id).count() == 0
            assert db.query(CalendarAuditLog).filter_by(user_id=target_id).count() == 0
            assert db.query(TransferLog).filter_by(user_id=target_id).count() == 0


def test_owner_cannot_delete_self_or_the_last_owner():
    with TestClient(app) as client:
        owner_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        with SessionLocal() as db:
            owner_id = db.query(User.id).filter(User.username == "admin").scalar()
        response = client.delete(f"/api/admin/users/{owner_id}", headers=owner_headers)
        assert response.status_code == 400
        assert response.json()["detail"] == "Нельзя удалить собственную учётную запись"


def test_project_admin_cannot_list_or_modify_another_projects_character():
    with TestClient(app) as client:
        with SessionLocal() as db:
            owner_id = db.query(User).filter(User.username == "admin").one().id
        project_admin_id = register_verified_user(client, "project-admin", "admin")
        player_id = register_verified_user(client, "other-player")
        project_a = create_project_fixture("Project A", owner_id, [(project_admin_id, "admin")])
        project_b = create_project_fixture("Project B", owner_id, [(player_id, "player")])

        with SessionLocal() as db:
            foreign_character = Character(
                name="Hidden Hero", class_name="Wizard",
                class_levels=[{"class_name": "Wizard", "level": 1}],
                level=1, route="Arcane", user_id=player_id, project_id=project_b,
            )
            own_project_character = Character(
                name="Visible Hero", class_name="Fighter",
                class_levels=[{"class_name": "Fighter", "level": 1}],
                level=1, route="Steel", user_id=project_admin_id, project_id=project_a,
            )
            db.add_all([foreign_character, own_project_character])
            db.commit()
            foreign_id = foreign_character.id

        headers = {
            "Authorization": f"Bearer {login(client, 'project-admin', 'Cobalt!River7Lantern')}",
            "X-Project-ID": str(project_a),
        }
        listed = client.get("/api/admin/characters", headers=headers)
        assert listed.status_code == 200, listed.text
        assert [row["name"] for row in listed.json()] == ["Visible Hero"]

        hidden = client.get(f"/api/admin/characters/{foreign_id}", headers=headers)
        assert hidden.status_code == 404
        grant = client.post(
            f"/api/admin/characters/{foreign_id}/xp",
            headers=headers,
            json={"amount": 1, "reason": "Cross-project attempt"},
        )
        assert grant.status_code == 404


def test_character_creation_requires_membership_in_selected_project():
    with TestClient(app) as client:
        with SessionLocal() as db:
            owner_id = db.query(User).filter(User.username == "admin").one().id
        player_id = register_verified_user(client, "project-player")
        allowed_id = create_project_fixture("Allowed", owner_id, [(player_id, "player")])
        denied_id = create_project_fixture("Denied", owner_id, [])
        headers = {
            "Authorization": f"Bearer {login(client, 'project-player', 'Cobalt!River7Lantern')}",
            "X-Project-ID": str(allowed_id),
        }
        payload = {
            "name": "Scoped Hero", "class_name": "Fighter", "level": 1,
            "route": "Steel", "project_id": denied_id,
        }
        denied = client.post("/api/characters", headers=headers, json=payload)
        assert denied.status_code == 403
        payload["project_id"] = allowed_id
        allowed = client.post("/api/characters", headers=headers, json=payload)
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["project_id"] == allowed_id


def test_character_creation_rejects_levels_outside_campaign_bounds():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}

        for level in (0, -1, 21):
            response = client.post("/api/characters", headers=headers, json={
                "name": f"Invalid Level {level}",
                "class_name": "Fighter",
                "level": level,
                "route": "Open Table",
            })
            assert response.status_code == 422, response.text

        for level in (1, 20):
            response = client.post("/api/characters", headers=headers, json={
                "name": f"Valid Level {level}",
                "class_name": "Fighter",
                "level": level,
                "route": "Open Table",
            })
            assert response.status_code == 200, response.text
            assert response.json()["level"] == level


def test_xp_grant_normalizes_legacy_invalid_level_before_progression():
    character = Character(level=-1_000_000, xp=0)

    apply_xp_delta(character, 2)

    assert character.level == 2
    assert character.xp == 0


def test_xp_grant_does_not_advance_past_campaign_maximum_level():
    character = Character(level=20, xp=0)

    apply_xp_delta(character, 21)

    assert character.level == 20
    assert character.xp == 21


def test_admin_character_level_edit_stays_within_campaign_bounds():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Bounded Admin Edit",
            "class_name": "Wizard",
            "level": 1,
            "route": "Arcane",
        })
        assert created.status_code == 200, created.text

        for requested_level, expected_level in ((0, 1), (21, 20)):
            edited = client.patch(
                f"/api/admin/characters/{created.json()['id']}",
                headers=headers,
                json={"level": requested_level},
            )
            assert edited.status_code == 200, edited.text
            assert edited.json()["level"] == expected_level


def test_admin_can_change_character_appearance_date_and_recalculate_free_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Calendar Correction", "class_name": "Wizard",
            "level": 1, "route": "Arcane", "game_created_at": "2025-06-01",
        })
        character_id = created.json()["id"]
        before = client.get(f"/api/admin/characters/{character_id}", headers=headers).json()
        changed = client.patch(
            f"/api/admin/characters/{character_id}", headers=headers,
            json={"game_created_at": "2025-06-05"},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["game_created_at"] == "2025-06-05"
        assert changed.json()["free_days"] == before["free_days"] - 4


def test_player_cannot_change_character_appearance_date():
    with TestClient(app) as client:
        client.post("/api/users", json={
            "username": "calendar-player", "email": "calendar-player@example.com",
            "password": TEST_USER_PASSWORD,
        })
        headers = {"Authorization": f"Bearer {login(client, 'calendar-player', TEST_USER_PASSWORD)}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Immutable Date", "class_name": "Fighter", "level": 1,
            "route": "Steel", "game_created_at": "2025-06-01",
        })
        changed = client.patch(
            f"/api/characters/{created.json()['id']}", headers=headers,
            json={"game_created_at": "2025-06-05"},
        )
        assert changed.status_code == 422


def test_admin_seed_and_username_login():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["is_admin"] is True


def test_access_token_lifetime_is_exactly_two_hours_for_every_role():
    from jose import jwt

    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        assert ACCESS_TOKEN_LIFETIME == timedelta(hours=2)
        assert payload["exp"] - payload["iat"] == 2 * 60 * 60


def test_backend_rejects_expired_access_token_with_explicit_reason():
    from jose import jwt

    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "admin@local",
            "iat": now - timedelta(hours=3),
            "exp": now - timedelta(hours=1),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with TestClient(app) as client:
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["detail"] == {
        "code": "token_expired",
        "message": "Сессия истекла. Войдите снова.",
    }


def test_create_user_then_login_with_username_and_email():
    with TestClient(app) as client:
        created = client.post("/api/users", json={
            "username": "player-one",
            "email": "player-one@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created.status_code == 200, created.text
        assert created.json()["username"] == "player-one"

        username_token = login(client, "player-one", TEST_USER_PASSWORD)
        username_response = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {username_token}"}
        )
        assert username_response.status_code == 200
        assert username_response.json()["email"] == "player-one@example.com"

        email_token = login(client, "player-one@example.com", TEST_USER_PASSWORD)
        email_response = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {email_token}"}
        )
        assert email_response.status_code == 200
        assert email_response.json()["username"] == "player-one"


def test_registration_never_exposes_or_persists_plaintext_password(caplog):
    password = "Safe-Campaign-Passphrase-47!"

    with caplog.at_level("DEBUG"), TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "secure-player",
            "email": "secure-player@example.com",
            "password": password,
        })

        assert response.status_code == 200, response.text
        assert "password" not in response.json()
        assert password not in response.text
        assert password not in caplog.text

        with SessionLocal() as db:
            user = db.query(User).filter(User.username == "secure-player").one()
            assert user.hashed_password != password
            assert user.hashed_password.startswith("$2b$")
            assert not hasattr(user, "password")


@pytest.mark.parametrize("password", ["simple", "alllowercase", "123456"])
def test_registration_accepts_passwords_without_composition_requirements(password):
    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": f"simple-{password}",
            "email": f"simple-{password}@example.com",
            "password": password,
        })

        assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    "password",
    [
        "short",
        "12345",
    ],
)
def test_registration_enforces_only_minimum_password_length(password):
    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "policy-user",
            "email": "policy-user@example.com",
            "password": password,
        })

        assert response.status_code == 422
        assert response.json()["detail"] == "Пароль должен содержать не менее 6 символов"


def test_registration_accepts_strong_password_at_bcrypt_byte_limit():
    password = "A1!" + "я" * 34 + "b"
    assert len(password.encode("utf-8")) == 72

    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "unicode-password",
            "email": "unicode-password@example.com",
            "password": password,
        })

        assert response.status_code == 200, response.text


def test_duplicate_username_returns_conflict():
    with TestClient(app) as client:
        assert client.post("/api/users", json={
            "username": "player-two",
            "email": "player-two@example.com",
            "password": TEST_USER_PASSWORD
        }).status_code == 200

        duplicate = client.post("/api/users", json={
            "username": "player-two",
            "email": "different@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "Имя пользователя уже занято"


def test_duplicate_email_returns_conflict():
    with TestClient(app) as client:
        assert client.post("/api/users", json={
            "username": "player-three",
            "email": "player-three@example.com",
            "password": TEST_USER_PASSWORD
        }).status_code == 200

        duplicate = client.post("/api/users", json={
            "username": "differentuser",
            "email": "player-three@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "Этот адрес электронной почты уже зарегистрирован"


def test_duplicate_email_case_insensitive_returns_conflict():
    with TestClient(app) as client:
        assert client.post("/api/users", json={
            "username": "player-four",
            "email": "player-four@example.com",
            "password": TEST_USER_PASSWORD
        }).status_code == 200

        duplicate = client.post("/api/users", json={
            "username": "player-four-v2",
            "email": "PLAYER-FOUR@EXAMPLE.COM",
            "password": TEST_USER_PASSWORD
        })
        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "Этот адрес электронной почты уже зарегистрирован"


def test_unique_user_registers_successfully():
    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "brandnewuser",
            "email": "brandnewuser@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["username"] == "brandnewuser"
        assert data["email"] == "brandnewuser@example.com"


def test_repeated_failed_login_attempts_are_temporarily_locked_before_bcrypt(monkeypatch):
    verify_calls = 0

    def always_reject(_plain_password: str, _hashed_password: str) -> bool:
        nonlocal verify_calls
        verify_calls += 1
        return False

    monkeypatch.setattr("app.api.users.verify_password", always_reject)

    with TestClient(app) as client:
        for _ in range(5):
            response = client.post(
                "/api/login",
                data={"username": "admin", "password": "wrong-password"},
            )
            assert response.status_code == 401

        blocked = client.post(
            "/api/login",
            data={"username": "admin", "password": "wrong-password"},
        )

        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        assert verify_calls == 5


def test_successful_login_still_works_after_low_volume_failures():
    with TestClient(app) as client:
        for _ in range(2):
            response = client.post(
                "/api/login",
                data={"username": "admin", "password": "wrong-password"},
            )
            assert response.status_code == 401

        token = login(client, "admin", "admin123")
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["username"] == "admin"


def test_registration_attempts_are_rate_limited_before_password_hashing(monkeypatch):
    hash_calls = 0

    def fake_hash_password(_password: str) -> str:
        nonlocal hash_calls
        hash_calls += 1
        return "test-hash"

    monkeypatch.setattr("app.api.users.hash_password", fake_hash_password)

    with TestClient(app) as client:
        for index in range(10):
            response = client.post("/api/users", json={
                "username": f"limited-user-{index}",
                "email": f"limited-user-{index}@example.com",
                "password": TEST_USER_PASSWORD,
            })
            assert response.status_code == 200, response.text

        blocked = client.post("/api/users", json={
            "username": "limited-user-10",
            "email": "limited-user-10@example.com",
            "password": TEST_USER_PASSWORD,
        })

        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"]
        assert hash_calls == 10


def test_registration_rejects_oversized_password_before_hashing(monkeypatch):
    def fail_hash_password(_password: str) -> str:
        raise AssertionError("oversized registration password reached bcrypt")

    monkeypatch.setattr("app.api.users.hash_password", fail_hash_password)

    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "oversized-password",
            "email": "oversized-password@example.com",
            # 37 Cyrillic characters fit the schema's character limit but use
            # 74 UTF-8 bytes, exercising the application's bcrypt-byte check.
            "password": "я" * 37,
        })

        assert response.status_code == 422
        assert response.json()["detail"] == (
            "Пароль должен содержать не более 72 байт в кодировке UTF-8"
        )


def test_login_rejects_oversized_password_before_bcrypt(monkeypatch):
    def fail_verify_password(_plain_password: str, _hashed_password: str) -> bool:
        raise AssertionError("oversized login password reached bcrypt")

    monkeypatch.setattr("app.api.users.verify_password", fail_verify_password)

    with TestClient(app) as client:
        response = client.post(
            "/api/login",
            data={"username": "admin", "password": "x" * 129},
        )

        assert response.status_code == 422


def test_password_hashing_uses_bcrypt_directly_without_passlib():
    """Registration must succeed with no passlib-related bcrypt version error.

    passlib 1.7.4 tried to read bcrypt.__about__.__version__, which was removed
    in bcrypt 4.1+, causing a trapped AttributeError and sometimes a cascading
    409 Conflict on valid registrations.  The fix replaces passlib with direct
    bcrypt calls so no version detection runs at all.
    """
    import logging
    import bcrypt as _bcrypt
    from app.core.security import hash_password, verify_password

    # Simulate an environment where bcrypt no longer exposes __about__
    original_about = getattr(_bcrypt, "__about__", None)
    try:
        if hasattr(_bcrypt, "__about__"):
            del _bcrypt.__about__

        hashed = hash_password("mypassword")
        assert hashed.startswith("$2b$"), "hash must be a valid bcrypt hash"
        assert verify_password("mypassword", hashed) is True
        assert verify_password("wrongpassword", hashed) is False
    finally:
        if original_about is not None:
            _bcrypt.__about__ = original_about

    # Confirm that registration itself returns 200 for a unique user
    with TestClient(app) as client:
        response = client.post("/api/users", json={
            "username": "bcrypt-compat-user",
            "email": "bcrypt-compat@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert response.status_code == 200, response.text
        assert response.json()["username"] == "bcrypt-compat-user"


def test_admin_character_xp_rolls_over_remaining_xp():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Talia",
            "class_name": "Wizard",
            "level": 3,
            "route": "Arcane"
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        response = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": 6, "reason": "Тест"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["level"] == 4
        assert response.json()["xp"] == 2


def test_player_character_patch_rejects_progression_and_death_state_changes():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "patch-player",
            "email": "patch-player@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        player_token = login(client, "patch-player", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}
        created_character = client.post("/api/characters", headers=player_headers, json={
            "name": "Grounded",
            "class_name": "Fighter",
            "level": 3,
            "route": "Steel",
            "hp": 0
        })
        assert created_character.status_code == 200, created_character.text
        character_id = created_character.json()["id"]

        seeded_state = client.patch(
            f"/api/admin/characters/{character_id}",
            headers=admin_headers,
            json={"level": 3, "xp": 1, "is_dead": True}
        )
        assert seeded_state.status_code == 200, seeded_state.text
        assert seeded_state.json()["is_dead"] is True

        forbidden = client.patch(
            f"/api/characters/{character_id}",
            headers=player_headers,
            json={"level": 20, "xp": 999, "is_dead": False}
        )
        assert forbidden.status_code == 422, forbidden.text

        unchanged = client.get(
            f"/api/admin/characters/{character_id}",
            headers=admin_headers
        )
        assert unchanged.status_code == 200, unchanged.text
        unchanged_payload = unchanged.json()
        assert unchanged_payload["level"] == 3
        assert unchanged_payload["xp"] == 1
        assert unchanged_payload["is_dead"] is True

        legitimate = client.patch(
            f"/api/characters/{character_id}",
            headers=player_headers,
            json={"name": "Renamed", "hp": 8}
        )
        assert legitimate.status_code == 200, legitimate.text
        legitimate_payload = legitimate.json()
        assert legitimate_payload["name"] == "Renamed"
        assert legitimate_payload["hp"] == 8
        assert legitimate_payload["level"] == 3
        assert legitimate_payload["xp"] == 1
        assert legitimate_payload["is_dead"] is True

        revived = client.post(
            f"/api/admin/characters/{character_id}/revive",
            headers=admin_headers
        )
        assert revived.status_code == 200, revived.text
        assert revived.json()["is_dead"] is False
        assert revived.json()["hp"] == 8


def test_karma_shop_purchases_are_atomic_persistent_and_audited():
    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created_user = client.post("/api/users", json={
            "username": "karma-shopper",
            "email": "karma-shopper@example.com",
            "password": TEST_USER_PASSWORD,
        })
        assert created_user.status_code == 200, created_user.text
        player_headers = {
            "Authorization": f"Bearer {login(client, 'karma-shopper', TEST_USER_PASSWORD)}"
        }
        character = client.post("/api/characters", headers=player_headers, json={
            "name": "Phoenix", "class_name": "Wizard", "level": 3,
            "route": "Arcane",
        })
        assert character.status_code == 200, character.text
        character_id = character.json()["id"]
        granted = client.post(
            f"/api/admin/users/{created_user.json()['id']}/karma",
            headers=admin_headers,
            json={"amount": 50, "reason": "Тест магазина"},
        )
        assert granted.status_code == 200, granted.text

        xp_purchase = client.post("/api/karma-shop/xp", headers=player_headers, json={
            "character_id": character_id, "amount": 4,
        })
        assert xp_purchase.status_code == 200, xp_purchase.text
        assert xp_purchase.json()["remaining_karma"] == 30
        assert xp_purchase.json()["character_xp"] == 0
        assert xp_purchase.json()["character_level"] == 4
        progressed = client.get("/api/characters", headers=player_headers).json()[0]
        assert progressed["level"] == 4
        assert progressed["class_levels"] == [
            {"class_name": "Wizard", "level": 4}
        ]

        item_purchase = client.post("/api/karma-shop/purchases", headers=player_headers, json={
            "purchase_type": "opener", "name": "Доступ в тайную библиотеку", "cost": 7,
        })
        assert item_purchase.status_code == 200, item_purchase.text
        assert item_purchase.json()["remaining_karma"] == 23

        purchases = client.get("/api/karma-shop/purchases", headers=player_headers)
        assert purchases.status_code == 200, purchases.text
        assert [(row["purchase_type"], row["name"]) for row in purchases.json()] == [
            ("opener", "Доступ в тайную библиотеку")
        ]

        insufficient = client.post("/api/karma-shop/purchases", headers=player_headers, json={
            "purchase_type": "item", "name": "Слишком дорогой товар", "cost": 24,
        })
        assert insufficient.status_code == 400, insufficient.text
        assert client.get("/api/me", headers=player_headers).json()["karma"] == 23
        assert len(client.get("/api/karma-shop/purchases", headers=player_headers).json()) == 1

        logs = client.get("/api/admin/karma-shop-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        assert [row["purchase_type"] for row in logs.json()] == ["opener", "xp"]
        assert logs.json()[1]["character_id"] == character_id
        assert logs.json()[1]["cost"] == 20
        assert client.get("/api/admin/karma-shop-logs", headers=player_headers).status_code == 403

        deleted = client.delete(
            f"/api/admin/characters/{character_id}", headers=admin_headers,
            params={"confirmation": "УДАЛИТЬ"},
        )
        assert deleted.status_code == 200, deleted.text
        preserved_logs = client.get("/api/admin/karma-shop-logs", headers=admin_headers)
        assert len(preserved_logs.json()) == 2


def test_karma_shop_opener_catalog_and_fixed_prices_are_server_controlled():
    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created_user = client.post("/api/users", json={
            "username": "preset-opener-shopper",
            "email": "preset-opener-shopper@example.com",
            "password": TEST_USER_PASSWORD,
        })
        assert created_user.status_code == 200, created_user.text
        player_headers = {
            "Authorization": f"Bearer {login(client, 'preset-opener-shopper', TEST_USER_PASSWORD)}"
        }
        granted = client.post(
            f"/api/admin/users/{created_user.json()['id']}/karma",
            headers=admin_headers,
            json={"amount": 50, "reason": "Тест предустановленных открывашек"},
        )
        assert granted.status_code == 200, granted.text

        catalog = client.get("/api/karma-shop/openers", headers=player_headers)
        assert catalog.status_code == 200, catalog.text
        assert [(opener["name"], opener["cost"]) for opener in catalog.json()] == [
            ("Смена расы", 10),
            ("Смена класса", 20),
            ("Смена подкласса", 15),
            ("Смена черты", 10),
            ("Смена классового умения", 5),
            ("Смена предыстории", 10),
            ("Открыть заклинание", 5),
            ("Смена опционального умения", 5),
            ("Мультикласс", 5),
            ("Открыть расу", 15),
            ("Открыть подкласс", 20),
            ("Открыть черту", 10),
            ("Открыть предысторию", 10),
        ]

        preset_purchase = client.post(
            "/api/karma-shop/purchases",
            headers=player_headers,
            json={"purchase_type": "opener", "name": "Смена класса", "cost": 1},
        )
        assert preset_purchase.status_code == 200, preset_purchase.text
        assert preset_purchase.json()["purchase"]["cost"] == 20
        assert preset_purchase.json()["remaining_karma"] == 30

        custom_purchase = client.post(
            "/api/karma-shop/purchases",
            headers=player_headers,
            json={"purchase_type": "opener", "name": "Нестандартная открывашка", "cost": 7},
        )
        assert custom_purchase.status_code == 200, custom_purchase.text
        assert custom_purchase.json()["purchase"]["cost"] == 7
        assert custom_purchase.json()["remaining_karma"] == 23

        logs = client.get("/api/admin/karma-shop-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        assert [(row["name"], row["cost"]) for row in logs.json()] == [
            ("Нестандартная открывашка", 7),
            ("Смена класса", 20),
        ]


def test_karma_resurrection_enforces_ownership_death_level_and_balance():
    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}

        def create_player(username: str):
            user = client.post("/api/users", json={
                "username": username,
                "email": f"{username}@example.com",
                "password": TEST_USER_PASSWORD,
            }).json()
            headers = {"Authorization": f"Bearer {login(client, username, TEST_USER_PASSWORD)}"}
            return user, headers

        user, headers = create_player("resurrection-owner")
        _, other_headers = create_player("resurrection-other")
        character = client.post("/api/characters", headers=headers, json={
            "name": "Fallen", "class_name": "Cleric", "level": 6, "route": "Dawn",
        }).json()
        character_id = character["id"]
        client.post(
            f"/api/admin/users/{user['id']}/karma", headers=admin_headers,
            json={"amount": 10, "reason": "Тест воскрешения"},
        )

        assert client.post(
            "/api/karma-shop/resurrect", headers=other_headers,
            json={"character_id": character_id},
        ).status_code == 404
        alive = client.post(
            "/api/karma-shop/resurrect", headers=headers,
            json={"character_id": character_id},
        )
        assert alive.status_code == 400

        client.patch(
            f"/api/admin/characters/{character_id}", headers=admin_headers,
            json={"is_dead": True, "level": 6},
        )
        client.post(
            f"/api/admin/users/{user['id']}/karma", headers=admin_headers,
            json={"amount": -1, "reason": "Проверка недостаточного баланса"},
        )
        insufficient = client.post(
            "/api/karma-shop/resurrect", headers=headers,
            json={"character_id": character_id},
        )
        assert insufficient.status_code == 400
        assert client.get("/api/me", headers=headers).json()["karma"] == 9
        assert client.get(
            f"/api/admin/characters/{character_id}", headers=admin_headers,
        ).json()["is_dead"] is True

        client.post(
            f"/api/admin/users/{user['id']}/karma", headers=admin_headers,
            json={"amount": 1, "reason": "Возврат тестового баланса"},
        )

        client.patch(
            f"/api/admin/characters/{character_id}", headers=admin_headers,
            json={"is_dead": True, "level": 11},
        )
        unavailable = client.post(
            "/api/karma-shop/resurrect", headers=headers,
            json={"character_id": character_id},
        )
        assert unavailable.status_code == 400
        assert client.get("/api/me", headers=headers).json()["karma"] == 10

        client.patch(
            f"/api/admin/characters/{character_id}", headers=admin_headers,
            json={"level": 6},
        )
        resurrected = client.post(
            "/api/karma-shop/resurrect", headers=headers,
            json={"character_id": character_id},
        )
        assert resurrected.status_code == 200, resurrected.text
        assert resurrected.json()["remaining_karma"] == 0
        assert resurrected.json()["character_is_dead"] is False
        log = client.get("/api/admin/karma-shop-logs", headers=admin_headers).json()[0]
        assert log["purchase_type"] == "resurrection"
        assert log["character_level"] == 6
        assert log["cost"] == 10


def test_players_cannot_directly_grant_inventory_currency_or_items():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "mint-blocked",
            "email": "mint-blocked@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        player_token = login(client, "mint-blocked", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}

        created_character = client.post("/api/characters", headers=player_headers, json={
            "name": "Honest Ledger",
            "class_name": "Bard",
            "level": 1,
            "route": "Market"
        })
        assert created_character.status_code == 200, created_character.text
        character_id = created_character.json()["id"]

        direct_currency = client.post(
            f"/api/characters/{character_id}/inventory/currency/add",
            headers=player_headers,
            json={"gold": 50, "silver": 5, "copper": 4, "reason": "Тест"}
        )
        assert direct_currency.status_code == 403
        direct_gold = client.post(
            f"/api/characters/{character_id}/inventory/gold/add",
            headers=player_headers,
            json={"amount": 50, "reason": "Тест"}
        )
        assert direct_gold.status_code == 403
        direct_item = client.post(
            f"/api/characters/{character_id}/inventory/items",
            headers=player_headers,
            json={"name": "Unreviewed Wand", "rarity": "Обычный", "is_consumable": False}
        )
        assert direct_item.status_code == 403

        inventory = client.get(
            f"/api/characters/{character_id}/inventory",
            headers=player_headers
        )
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["gold"] == 0
        assert inventory.json()["silver"] == 0
        assert inventory.json()["copper"] == 0
        assert inventory.json()["items"] == []

        granted_currency = client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=admin_headers,
            json={"gold": 5, "silver": 2, "copper": 1, "reason": "Тест"}
        )
        assert granted_currency.status_code == 200, granted_currency.text
        granted_item = client.post(
            f"/api/admin/characters/{character_id}/item",
            headers=admin_headers,
            json={"name": "Reviewed Wand", "rarity": "Обычный", "is_consumable": False, "reason": "Тест"}
        )
        assert granted_item.status_code == 200, granted_item.text
        assert granted_item.json()["gold"] == 5
        assert granted_item.json()["silver"] == 2
        assert granted_item.json()["copper"] == 1
        assert granted_item.json()["items"][0]["name"] == "Reviewed Wand"


def test_shop_search_charges_hireling_in_gold_before_buy_confirmation():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Borin",
            "class_name": "Fighter",
            "level": 1,
            "route": "Steel",
            "investigation": 20
        })
        character_id = created.json()["id"]
        client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"}
        )

        response = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "buy",
            "item_name": "Healing Potion",
            "rarity": "Обычный",
            "is_consumable": True,
            "searcher_type": "hireling",
            "hireling_level": "Эксперт"
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["quote_id"]
        assert payload["item_price"] > 0
        assert payload["hireling_cost"] >= 25
        assert payload["inventory"]["gold"] == 10000 - payload["hireling_cost"]
        assert payload["inventory"]["items"] == []

        confirmed = client.post(
            f"/api/characters/{character_id}/shop/buy",
            headers=headers,
            json={"quote_id": payload["quote_id"]}
        )
        assert confirmed.status_code == 200, confirmed.text
        confirmed_payload = confirmed.json()
        assert confirmed_payload["is_consumed"] is True
        assert confirmed_payload["inventory"]["gold"] == (
            10000 - payload["hireling_cost"] - payload["item_price"]
        )
        assert confirmed_payload["inventory"]["items"][0]["name"] == "Healing Potion"

        replayed = client.post(
            f"/api/characters/{character_id}/shop/buy",
            headers=headers,
            json={"quote_id": payload["quote_id"]}
        )
        assert replayed.status_code == 409
        assert replayed.json()["detail"] == "Shop result has already been used"


def test_shop_sell_search_waits_for_confirmation_and_adds_gold():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Mira",
            "class_name": "Rogue",
            "level": 1,
            "route": "Shadow",
            "investigation": 20
        })
        character_id = created.json()["id"]
        client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 1000, "silver": 0, "copper": 0, "reason": "Тест"}
        )
        granted = client.post(
            f"/api/admin/characters/{character_id}/item",
            headers=headers,
            json={"name": "Old Wand", "rarity": "Обычный", "is_consumable": False, "reason": "Тест"}
        )
        item_id = granted.json()["items"][0]["id"]

        response = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "sell",
            "item_id": item_id,
            "searcher_type": "hireling",
            "hireling_level": "Эксперт"
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["inventory"]["items"][0]["name"] == "Old Wand"
        assert payload["inventory"]["gold"] == 1000 - payload["hireling_cost"]

        confirmed = client.post(
            f"/api/characters/{character_id}/shop/sell",
            headers=headers,
            json={"quote_id": payload["quote_id"]}
        )
        assert confirmed.status_code == 200, confirmed.text
        confirmed_payload = confirmed.json()
        assert confirmed_payload["inventory"]["items"] == []
        assert confirmed_payload["inventory"]["gold"] == (
            1000 - payload["hireling_cost"] + payload["item_price"]
        )

        replayed = client.post(
            f"/api/characters/{character_id}/shop/sell",
            headers=headers,
            json={"quote_id": payload["quote_id"]}
        )
        assert replayed.status_code == 409
        assert replayed.json()["detail"] == "Shop result has already been used"


def create_shop_quote(client: TestClient, headers: dict, mode: str):
    created = client.post("/api/characters", headers=headers, json={
        "name": f"Atomic {mode}", "class_name": "Fighter",
        "level": 1, "route": "Trade", "investigation": 20,
    })
    character_id = created.json()["id"]
    client.post(
        f"/api/admin/characters/{character_id}/currency/add", headers=headers,
        json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Test"},
    )
    search_data = {
        "mode": mode, "searcher_type": "hireling", "hireling_level": "Эксперт",
    }
    if mode == "buy":
        search_data.update({
            "item_name": "Healing Potion", "rarity": "Обычный",
            "is_consumable": True,
        })
    else:
        granted = client.post(
            f"/api/admin/characters/{character_id}/item", headers=headers,
            json={
                "name": "Old Wand", "rarity": "Обычный",
                "is_consumable": False, "reason": "Test",
            },
        ).json()
        search_data["item_id"] = granted["items"][0]["id"]
    quote = client.post(
        f"/api/characters/{character_id}/shop/search",
        headers=headers,
        json=search_data,
    )
    assert quote.status_code == 200, quote.text
    return character_id, quote.json()


def assert_quote_compare_and_set_is_atomic(quote_id: int):
    with SessionLocal() as first_db, SessionLocal() as second_db:
        first_quote = first_db.get(ShopQuote, quote_id)
        second_quote = second_db.get(ShopQuote, quote_id)
        assert first_quote.is_consumed is False
        assert second_quote.is_consumed is False

        consume_quote_for_inventory(first_quote, first_db)
        first_db.commit()

        with pytest.raises(HTTPException) as replay:
            consume_quote_for_inventory(second_quote, second_db)
        assert replay.value.status_code == 409
        assert replay.value.detail == "Shop result has already been used"


def test_buy_quote_can_only_be_claimed_once_from_stale_sessions():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        _, quote = create_shop_quote(client, headers, "buy")

        assert_quote_compare_and_set_is_atomic(quote["quote_id"])


def test_sell_quote_can_only_be_claimed_once_from_stale_sessions():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        _, quote = create_shop_quote(client, headers, "sell")

        assert_quote_compare_and_set_is_atomic(quote["quote_id"])


def test_magic_item_catalog_only_lists_allowed_rarities_and_supports_search():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/api/shop/magic-items", headers=headers)

        assert response.status_code == 200, response.text
        catalog = response.json()
        assert catalog
        assert {item["rarity"] for item in catalog} <= {"Обычный", "Необычный", "Редкий"}
        assert {item["rarity_key"] for item in catalog} <= {"common", "uncommon", "rare"}
        names = {item["name"] for item in catalog}
        assert "+1 Доспех" in names
        assert "+3 Доспех" not in names
        assert "Vorpal Sword" not in names
        assert all(item["item_type"] for item in catalog)

        search = client.get(
            "/api/shop/magic-items",
            headers=headers,
            params={"search": "щит", "rarity": "Необычный"}
        )

        assert search.status_code == 200, search.text
        search_payload = search.json()
        assert search_payload
        assert all("щит" in item["name"].casefold() for item in search_payload)
        assert all(item["rarity"] == "Необычный" for item in search_payload)


def test_shop_search_uses_selected_magic_item_without_manual_name_or_rarity():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Catalog Buyer",
            "class_name": "Fighter",
            "level": 1,
            "route": "Market",
            "investigation": 20
        })
        character_id = created.json()["id"]
        client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"}
        )
        catalog = client.get(
            "/api/shop/magic-items",
            headers=headers,
            params={"search": "+1 Доспех"}
        )
        magic_item = next(item for item in catalog.json() if item["name"] == "+1 Доспех")

        response = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "buy",
            "magic_item_id": magic_item["id"],
            "searcher_type": "character"
        })

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["item_name"] == "+1 Доспех"
        assert payload["rarity"] == "Редкий"
        assert payload["is_consumable"] is False
        assert payload["item_price"] > 0


def test_shop_buy_rejects_known_banned_magic_item_even_when_manual_rarity_lowered():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Ban Checker",
            "class_name": "Wizard",
            "level": 1,
            "route": "Market",
            "investigation": 20
        })
        character_id = created.json()["id"]

        response = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "buy",
            "item_name": "Vorpal Sword",
            "rarity": "Редкий",
            "is_consumable": False,
            "searcher_type": "character"
        })

        assert response.status_code == 400
        assert response.json()["detail"] == "Magic item is not available in the shop"


def test_admin_can_change_karma_and_view_all_characters_with_owner():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "player-three",
            "email": "player-three@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        player_token = login(client, "player-three", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}
        created_character = client.post("/api/characters", headers=player_headers, json={
            "name": "Nessa",
            "class_name": "Cleric",
            "level": 2,
            "route": "Dawn",
            "race": "Human",
            "subclass": "Life"
        })
        assert created_character.status_code == 200, created_character.text

        added = client.post(
            f"/api/admin/users/{user_id}/karma/add",
            headers=admin_headers,
            json={"amount": 3, "reason": "Тест"}
        )
        assert added.status_code == 200, added.text
        assert added.json()["karma"] == 3
        subtracted = client.post(
            f"/api/admin/users/{user_id}/karma/subtract",
            headers=admin_headers,
            json={"amount": 1, "reason": "Тест"}
        )
        assert subtracted.status_code == 200, subtracted.text
        assert subtracted.json()["karma"] == 2

        characters = client.get("/api/admin/characters", headers=admin_headers)
        assert characters.status_code == 200, characters.text
        payload = characters.json()
        assert any(
            character["name"] == "Nessa" and character["owner_username"] == "player-three"
            for character in payload
        )
        nessa = next(character for character in payload if character["name"] == "Nessa")
        assert nessa["game_created_at"] == GAME_EPOCH.isoformat()
        assert isinstance(nessa["free_days"], int)
        assert "personal_hireling_free_days" in nessa
        assert "simulacrum_free_days" in nessa


def test_admin_resource_grants_require_reasons_and_create_filterable_logs():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        admin = client.get("/api/me", headers=admin_headers).json()
        created_user = client.post("/api/users", json={
            "username": "grant-target",
            "email": "grant-target@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        player_token = login(client, "grant-target", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}
        created_character = client.post("/api/characters", headers=player_headers, json={
            "name": "Logan",
            "class_name": "Wizard",
            "level": 1,
            "route": "Arcane"
        })
        assert created_character.status_code == 200, created_character.text
        character_id = created_character.json()["id"]

        missing_reason = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=admin_headers,
            json={"amount": 4}
        )
        assert missing_reason.status_code == 422
        blank_reason = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=admin_headers,
            json={"amount": 4, "reason": "   "}
        )
        assert blank_reason.status_code == 422

        grants = [
            (f"/api/admin/users/{user_id}/karma", {"amount": 2, "reason": "За игру"}),
            (f"/api/admin/characters/{character_id}/xp", {"amount": 4, "reason": "Награда за ивент"}),
            (f"/api/admin/characters/{character_id}/gold", {"amount": 7, "reason": "Компенсация"}),
            (f"/api/admin/characters/{character_id}/item", {
                "name": "Жезл",
                "rarity": "Необычный",
                "is_consumable": False,
                "reason": "Решение мастера"
            }),
        ]
        for path, payload in grants:
            response = client.post(path, headers=admin_headers, json=payload)
            assert response.status_code == 200, response.text

        logs = client.get("/api/admin/grant-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        payload = logs.json()
        assert [row["operation_type"] for row in payload] == [
            "item", "gold", "xp", "karma"
        ]
        assert all(row["admin_id"] == admin["id"] for row in payload)
        assert all(row["admin_username"] == "admin" for row in payload)
        assert all(row["user_id"] == user_id for row in payload)
        assert all(row["username"] == "grant-target" for row in payload)
        assert payload[0]["character_id"] == character_id
        assert payload[0]["character_name"] == "Logan"
        assert payload[0]["value"] == "Жезл · Необычный · постоянный"
        assert payload[0]["reason"] == "Решение мастера"
        assert payload[-1]["character_id"] is None
        assert payload[-1]["value"] == "+2"

        filtered = client.get(
            "/api/admin/grant-logs",
            headers=admin_headers,
            params={"operation_type": "xp", "user_id": user_id}
        )
        assert filtered.status_code == 200, filtered.text
        assert len(filtered.json()) == 1
        assert filtered.json()[0]["reason"] == "Награда за ивент"

        player_logs = client.get("/api/admin/grant-logs", headers=player_headers)
        assert player_logs.status_code == 403


def test_openapi_uses_russian_investigation_title():
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
        serialized_schema = str(schema)
        character_create = schema["components"]["schemas"]["CharacterCreate"]
        assert (
            character_create["properties"]["investigation"]["title"]
            == "Расследование"
        )
        assert ("Invest" + "igation") not in serialized_schema


def test_players_cannot_change_own_karma_through_me_endpoints():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "karma-self-service",
            "email": "karma-self-service@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        player_token = login(client, "karma-self-service", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}

        for path in ("/api/me/karma/add", "/api/me/karma/subtract"):
            blocked = client.post(path, headers=player_headers, json={"amount": 77, "reason": "Тест"})
            assert blocked.status_code == 404

        me = client.get("/api/me", headers=player_headers)
        assert me.status_code == 200, me.text
        assert me.json()["karma"] == 0

        added = client.post(
            f"/api/admin/users/{user_id}/karma/add",
            headers=admin_headers,
            json={"amount": 3, "reason": "Тест"}
        )
        assert added.status_code == 200, added.text
        assert added.json()["karma"] == 3


def test_admin_signed_adjustments_clamp_resources_to_zero():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}
        created_character = client.post("/api/characters", headers=headers, json={
            "name": "Vera",
            "class_name": "Wizard",
            "level": 20,
            "route": "Arcane"
        })
        assert created_character.status_code == 200, created_character.text
        character_id = created_character.json()["id"]

        added_xp = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": 10, "reason": "Тест"}
        )
        assert added_xp.status_code == 200, added_xp.text
        reduced_xp = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": -5, "reason": "Тест"}
        )
        assert reduced_xp.status_code == 200, reduced_xp.text
        assert reduced_xp.json()["xp"] == 5
        clamped_xp = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": -99, "reason": "Тест"}
        )
        assert clamped_xp.status_code == 200, clamped_xp.text
        assert clamped_xp.json()["xp"] == 0

        added_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": 100, "reason": "Тест"}
        )
        assert added_gold.status_code == 200, added_gold.text
        reduced_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": -25, "reason": "Тест"}
        )
        assert reduced_gold.status_code == 200, reduced_gold.text
        assert reduced_gold.json()["gold"] == 75
        clamped_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": -999, "reason": "Тест"}
        )
        assert clamped_gold.status_code == 200, clamped_gold.text
        assert clamped_gold.json()["gold"] == 0

        created_user = client.post("/api/users", json={
            "username": "karma-target",
            "email": "karma-target@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        added_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": 20, "reason": "Тест"}
        )
        assert added_karma.status_code == 200, added_karma.text
        reduced_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": -7, "reason": "Тест"}
        )
        assert reduced_karma.status_code == 200, reduced_karma.text
        assert reduced_karma.json()["karma"] == 13
        clamped_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": -99, "reason": "Тест"}
        )
        assert clamped_karma.status_code == 200, clamped_karma.text
        assert clamped_karma.json()["karma"] == 0


def test_admin_can_edit_any_character_directly():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "editable-player",
            "email": "editable-player@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        player_token = login(client, "editable-player", TEST_USER_PASSWORD)
        player_headers = {"Authorization": f"Bearer {player_token}"}
        created_character = client.post("/api/characters", headers=player_headers, json={
            "name": "Old Name",
            "class_name": "Rogue",
            "level": 3,
            "route": "Old Path"
        })
        assert created_character.status_code == 200, created_character.text
        character_id = created_character.json()["id"]

        edited = client.patch(
            f"/api/admin/characters/{character_id}",
            headers=admin_headers,
            json={
                "name": "New Name",
                "class_name": "Воин",
                "subclass": "Champion",
                "race": "Human",
                "background": "Soldier",
                "route": "Iron",
                "level": 7,
                "xp": 4,
                "hp": 55,
                "armor_class": 18,
                "strength": 16,
                "dexterity": 12,
                "constitution": 14,
                "intelligence": 10,
                "wisdom": 11,
                "charisma": 9,
                "investigation": 6
            }
        )
        assert edited.status_code == 200, edited.text
        payload = edited.json()
        assert payload["name"] == "New Name"
        assert payload["level"] == 7
        assert payload["xp"] == 4
        assert payload["hp"] == 55
        assert payload["armor_class"] == 18
        assert payload["strength"] == 16
        assert payload["investigation"] == 6

        listed = client.get("/api/admin/characters", headers=admin_headers)
        assert listed.status_code == 200, listed.text
        assert any(
            character["id"] == character_id and character["level"] == 7
            for character in listed.json()
        )


def test_user_cannot_create_more_than_ten_characters():
    with TestClient(app) as client:
        created_user = client.post("/api/users", json={
            "username": "collector",
            "email": "collector@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        token = login(client, "collector", TEST_USER_PASSWORD)
        headers = {"Authorization": f"Bearer {token}"}

        for index in range(10):
            response = client.post("/api/characters", headers=headers, json={
                "name": f"Hero {index}",
                "class_name": "Bard",
                "level": 1,
                "route": "Open Table"
            })
            assert response.status_code == 200, response.text

        blocked = client.post("/api/characters", headers=headers, json={
            "name": "Hero 11",
            "class_name": "Bard",
            "level": 1,
            "route": "Open Table"
        })
        assert blocked.status_code == 400
        assert blocked.json()["detail"] == "Достигнут лимит персонажей (10 из 10)."


def test_shop_buy_and_sell_confirmations_create_filterable_persistent_logs():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        me = client.get("/api/me", headers=headers)
        assert me.status_code == 200, me.text
        user_id = me.json()["id"]
        created = client.post("/api/characters", headers=headers, json={
            "name": "Ledger",
            "class_name": "Fighter",
            "level": 1,
            "route": "Trade",
            "investigation": 20
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]
        currency = client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"}
        )
        assert currency.status_code == 200, currency.text

        buy_search = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "buy",
            "item_name": "Audit Sword",
            "rarity": "Обычный",
            "is_consumable": False,
            "searcher_type": "hireling",
            "hireling_level": "Эксперт"
        })
        assert buy_search.status_code == 200, buy_search.text
        buy_payload = buy_search.json()
        buy_confirm = client.post(
            f"/api/characters/{character_id}/shop/buy",
            headers=headers,
            json={"quote_id": buy_payload["quote_id"]}
        )
        assert buy_confirm.status_code == 200, buy_confirm.text

        granted = client.post(
            f"/api/admin/characters/{character_id}/item",
            headers=headers,
            json={"name": "Audit Wand", "rarity": "Обычный", "is_consumable": False, "reason": "Тест"}
        )
        assert granted.status_code == 200, granted.text
        sell_item_id = next(
            item["id"] for item in granted.json()["items"]
            if item["name"] == "Audit Wand"
        )
        sell_search = client.post(f"/api/characters/{character_id}/shop/search", headers=headers, json={
            "mode": "sell",
            "item_id": sell_item_id,
            "searcher_type": "hireling",
            "hireling_level": "Эксперт"
        })
        assert sell_search.status_code == 200, sell_search.text
        sell_payload = sell_search.json()
        sell_confirm = client.post(
            f"/api/characters/{character_id}/shop/sell",
            headers=headers,
            json={"quote_id": sell_payload["quote_id"]}
        )
        assert sell_confirm.status_code == 200, sell_confirm.text

    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        logs = client.get("/api/admin/shop-logs", headers=headers)
        assert logs.status_code == 200, logs.text
        payload = logs.json()
        assert len(payload) == 2
        buy_log = next(log for log in payload if log["mode"] == "buy")
        assert buy_log["username"] == "admin"
        assert buy_log["character_name"] == "Ledger"
        assert buy_log["item_name"] == "Audit Sword"
        assert buy_log["rarity"] == "Обычный"
        assert buy_log["item_price"] == buy_payload["item_price"]
        assert buy_log["hireling_cost"] == buy_payload["hireling_cost"]
        assert buy_log["total_amount"] == buy_payload["item_price"] + buy_payload["hireling_cost"]

        filtered = client.get(
            "/api/admin/shop-logs",
            headers=headers,
            params={
                "character_id": character_id,
                "user_id": user_id,
                "mode": "sell",
                "date": date.today().isoformat()
            }
        )
        assert filtered.status_code == 200, filtered.text
        sell_logs = filtered.json()
        assert len(sell_logs) == 1
        assert sell_logs[0]["item_name"] == "Audit Wand"
        assert sell_logs[0]["total_amount"] == sell_payload["item_price"] - sell_payload["hireling_cost"]


def test_market_sale_credits_owned_character_and_creates_admin_audit_log():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Торговец", "class_name": "Воин", "level": 1, "route": "Рынок"
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        sold = client.post(
            f"/api/characters/{character_id}/market/sales",
            headers=headers,
            json={"item_name": "  Длинный меч  ", "gold": 7},
        )
        assert sold.status_code == 201, sold.text
        payload = sold.json()
        assert payload["sale"]["username"] == "admin"
        assert payload["sale"]["character_name"] == "Торговец"
        assert payload["sale"]["item_name"] == "Длинный меч"
        assert payload["sale"]["gold"] == 7
        assert payload["inventory"]["gold"] == 7

        logs = client.get("/api/admin/market-sales", headers=headers)
        assert logs.status_code == 200, logs.text
        assert len(logs.json()) == 1
        assert logs.json()[0] == payload["sale"]


def test_market_sale_validates_input_and_character_ownership():
    with TestClient(app) as client:
        owner_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=owner_headers, json={
            "name": "Чужой", "class_name": "Плут", "level": 1, "route": "Рынок"
        }).json()
        client.post("/api/users", json={
            "username": "market-player", "email": "market-player@example.com",
            "password": TEST_USER_PASSWORD,
        })
        player_headers = {
            "Authorization": f"Bearer {login(client, 'market-player', TEST_USER_PASSWORD)}"
        }

        forbidden = client.post(
            f"/api/characters/{created['id']}/market/sales",
            headers=player_headers,
            json={"item_name": "Щит", "gold": 5},
        )
        assert forbidden.status_code == 404

        for body in (
            {"item_name": "   ", "gold": 5},
            {"item_name": "Верёвка", "gold": 0},
            {"item_name": "Верёвка", "gold": -1},
        ):
            invalid = client.post(
                f"/api/characters/{created['id']}/market/sales",
                headers=owner_headers,
                json=body,
            )
            assert invalid.status_code == 422, invalid.text

        inventory = client.get(
            f"/api/characters/{created['id']}/inventory", headers=owner_headers
        )
        assert inventory.json()["gold"] == 0
        assert client.get("/api/admin/market-sales", headers=owner_headers).json() == []


def test_market_sales_log_is_admin_only_and_filterable():
    with TestClient(app) as client:
        owner_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=owner_headers, json={
            "name": "Фильтр", "class_name": "Бард", "level": 1, "route": "Рынок"
        }).json()
        client.post(
            f"/api/characters/{created['id']}/market/sales", headers=owner_headers,
            json={"item_name": "Кнут", "gold": 2},
        )
        client.post("/api/users", json={
            "username": "market-auditee", "email": "market-auditee@example.com",
            "password": TEST_USER_PASSWORD,
        })
        player_headers = {
            "Authorization": f"Bearer {login(client, 'market-auditee', TEST_USER_PASSWORD)}"
        }

        assert client.get("/api/admin/market-sales", headers=player_headers).status_code == 403
        filtered = client.get(
            "/api/admin/market-sales", headers=owner_headers,
            params={"character_id": created["id"], "date": date.today().isoformat()},
        )
        assert filtered.status_code == 200, filtered.text
        assert [entry["item_name"] for entry in filtered.json()] == ["Кнут"]


def test_owner_delete_character_requires_confirmation_and_cascades_inventory():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Delete Me",
            "class_name": "Fighter",
            "level": 1,
            "route": "Dust"
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]
        client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 5, "silver": 4, "copper": 3, "reason": "Тест"}
        )
        client.post(
            f"/api/admin/characters/{character_id}/item",
            headers=headers,
            json={"name": "Marked Sword", "rarity": "Обычный", "is_consumable": False, "reason": "Тест"}
        )

        blocked = client.delete(
            f"/api/admin/characters/{character_id}",
            headers=headers,
            params={"confirmation": "delete"}
        )
        assert blocked.status_code == 400

        removed = client.delete(
            f"/api/admin/characters/{character_id}",
            headers=headers,
            params={"confirmation": "УДАЛИТЬ"}
        )
        assert removed.status_code == 200, removed.text
        assert removed.json() == {"deleted": True, "id": character_id}

        listed = client.get("/api/admin/characters", headers=headers)
        assert listed.status_code == 200, listed.text
        assert all(character["id"] != character_id for character in listed.json())
        missing_inventory = client.get(
            f"/api/admin/characters/{character_id}/inventory",
            headers=headers
        )
        assert missing_inventory.status_code == 404


def test_only_owner_and_head_admin_can_delete_characters():
    with TestClient(app) as client:
        owner_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        users = {}
        for username, role in (("delete-head", "head_admin"), ("delete-admin", "admin")):
            user = client.post("/api/users", json={
                "username": username, "email": f"{username}@example.com",
                "password": TEST_USER_PASSWORD,
            }).json()
            client.post(
                f"/api/admin/users/{user['id']}/role", headers=owner_headers,
                json={"role": role},
            )
            users[role] = username
        allowed_character = client.post("/api/characters", headers=owner_headers, json={
            "name": "Head Admin Delete", "class_name": "Fighter", "level": 1,
            "route": "Steel",
        }).json()
        protected_character = client.post("/api/characters", headers=owner_headers, json={
            "name": "Protected", "class_name": "Fighter", "level": 1,
            "route": "Steel",
        }).json()
        head_headers = {"Authorization": f"Bearer {login(client, users['head_admin'], TEST_USER_PASSWORD)}"}
        allowed = client.delete(
            f"/api/admin/characters/{allowed_character['id']}", headers=head_headers,
            params={"confirmation": "УДАЛИТЬ"},
        )
        assert allowed.status_code == 200, allowed.text
        admin_headers = {"Authorization": f"Bearer {login(client, users['admin'], TEST_USER_PASSWORD)}"}
        denied = client.delete(
            f"/api/admin/characters/{protected_character['id']}", headers=admin_headers,
            params={"confirmation": "УДАЛИТЬ"},
        )
        assert denied.status_code == 403, denied.text


def test_admin_can_delete_character_with_shop_transaction_history():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {admin_token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Retired Merchant",
            "class_name": "Rogue",
            "level": 1,
            "route": "Trade",
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        funded = client.post(
            f"/api/admin/characters/{character_id}/currency/add",
            headers=headers,
            json={"gold": 1_000, "reason": "Тест покупки"},
        )
        assert funded.status_code == 200, funded.text

        for _ in range(20):
            search = client.post(
                f"/api/characters/{character_id}/shop/search",
                headers=headers,
                json={
                    "mode": "buy",
                    "item_name": "Merchant's Ring",
                    "rarity": "Обычный",
                    "is_consumable": False,
                    "searcher_type": "hireling",
                    "hireling_level": "Эксперт",
                },
            )
            assert search.status_code == 200, search.text
            quote = search.json()
            if quote["success"]:
                break
        assert quote["success"] is True
        purchased = client.post(
            f"/api/characters/{character_id}/shop/buy",
            headers=headers,
            json={"quote_id": quote["quote_id"]},
        )
        assert purchased.status_code == 200, purchased.text

        removed = client.delete(
            f"/api/admin/characters/{character_id}",
            headers=headers,
            params={"confirmation": "УДАЛИТЬ"},
        )
        assert removed.status_code == 200, removed.text
        assert removed.json() == {"deleted": True, "id": character_id}

        shop_logs = client.get("/api/admin/shop-logs", headers=headers)
        assert shop_logs.status_code == 200, shop_logs.text
        assert all(
            log["character_id"] != character_id
            for log in shop_logs.json()
        )


def test_cross_player_currency_and_item_transfers_create_persistent_logs():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "receiver",
            "email": "receiver@example.com",
            "password": TEST_USER_PASSWORD
        })
        assert created_user.status_code == 200, created_user.text
        receiver_token = login(client, "receiver", TEST_USER_PASSWORD)
        receiver_headers = {"Authorization": f"Bearer {receiver_token}"}

        sender = client.post("/api/characters", headers=admin_headers, json={
            "name": "Sender",
            "class_name": "Bard",
            "level": 1,
            "route": "Trade"
        })
        assert sender.status_code == 200, sender.text
        sender_id = sender.json()["id"]
        recipient = client.post("/api/characters", headers=receiver_headers, json={
            "name": "Recipient",
            "class_name": "Cleric",
            "level": 1,
            "route": "Trade"
        })
        assert recipient.status_code == 200, recipient.text
        recipient_id = recipient.json()["id"]

        targets = client.get("/api/characters/transfer-targets", headers=admin_headers)
        assert targets.status_code == 200, targets.text
        assert any(
            character["id"] == recipient_id and character["owner_username"] == "receiver"
            for character in targets.json()
        )

        currency = client.post(
            f"/api/admin/characters/{sender_id}/currency/add",
            headers=admin_headers,
            json={"gold": 2, "silver": 5, "copper": 4, "reason": "Тест"}
        )
        assert currency.status_code == 200, currency.text
        granted = client.post(
            f"/api/admin/characters/{sender_id}/item",
            headers=admin_headers,
            json={"name": "Courier Ring", "rarity": "Обычный", "is_consumable": False, "reason": "Тест"}
        )
        assert granted.status_code == 200, granted.text
        item_id = granted.json()["items"][0]["id"]

        insufficient = client.post(
            f"/api/characters/{sender_id}/inventory/currency/transfer",
            headers=admin_headers,
            json={"recipient_character_id": recipient_id, "gold": 9, "silver": 0, "copper": 0}
        )
        assert insufficient.status_code == 400

        transferred_currency = client.post(
            f"/api/characters/{sender_id}/inventory/currency/transfer",
            headers=admin_headers,
            json={"recipient_character_id": recipient_id, "gold": 1, "silver": 3, "copper": 4}
        )
        assert transferred_currency.status_code == 200, transferred_currency.text
        assert transferred_currency.json()["gold"] == 1
        assert transferred_currency.json()["silver"] == 2
        assert transferred_currency.json()["copper"] == 0

        invalid_item = client.post(
            f"/api/characters/{sender_id}/inventory/items/transfer",
            headers=admin_headers,
            json={"recipient_character_id": recipient_id, "item_id": item_id + 999}
        )
        assert invalid_item.status_code == 400

        transferred_item = client.post(
            f"/api/characters/{sender_id}/inventory/items/transfer",
            headers=admin_headers,
            json={"recipient_character_id": recipient_id, "item_id": item_id}
        )
        assert transferred_item.status_code == 200, transferred_item.text
        assert transferred_item.json()["items"] == []

        receiver_inventory = client.get(
            f"/api/characters/{recipient_id}/inventory",
            headers=receiver_headers
        )
        assert receiver_inventory.status_code == 200, receiver_inventory.text
        receiver_payload = receiver_inventory.json()
        assert receiver_payload["gold"] == 1
        assert receiver_payload["silver"] == 3
        assert receiver_payload["copper"] == 4
        assert receiver_payload["items"][0]["name"] == "Courier Ring"

    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        logs = client.get("/api/admin/transfer-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        payload = logs.json()
        assert len(payload) == 2
        currency_log = next(log for log in payload if log["transfer_type"] == "currency")
        assert currency_log["sender_character_name"] == "Sender"
        assert currency_log["recipient_character_name"] == "Recipient"
        assert currency_log["gold"] == 1
        assert currency_log["silver"] == 3
        assert currency_log["copper"] == 4
        item_log = next(log for log in payload if log["transfer_type"] == "item")
        assert item_log["item_name"] == "Courier Ring"
        assert item_log["item_rarity"] == "Обычный"


def test_inventory_notes_combat_fields_and_attacks_persist_with_roll_log():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Sheet Hero",
            "class_name": "Воин",
            "level": 5,
            "route": "Frontline",
            "temp_hp": 8,
            "speed": 35,
            "strength": 16
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]
        assert created.json()["temp_hp"] == 8
        assert created.json()["speed"] == 35

        patched = client.patch(
            f"/api/characters/{character_id}",
            headers=headers,
            json={"temp_hp": 3, "speed": 40}
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["temp_hp"] == 3
        assert patched.json()["speed"] == 40

        inventory = client.get(
            f"/api/characters/{character_id}/inventory",
            headers=headers
        )
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["notes"] == ""

        notes = "2 верёвки\n14 стрел\n3 факела"
        updated_notes = client.patch(
            f"/api/characters/{character_id}/inventory/notes",
            headers=headers,
            json={"notes": notes}
        )
        assert updated_notes.status_code == 200, updated_notes.text
        assert updated_notes.json()["notes"] == notes

        loaded_notes = client.get(
            f"/api/characters/{character_id}/inventory",
            headers=headers
        )
        assert loaded_notes.json()["notes"] == notes

        created_attack = client.post(
            f"/api/characters/{character_id}/attacks",
            headers=headers,
            json={
                "name": "Длинный меч",
                "attack_bonus": 5,
                "damage": "1d8+3 рубящий"
            }
        )
        assert created_attack.status_code == 200, created_attack.text
        attack_id = created_attack.json()["id"]

        attacks = client.get(
            f"/api/characters/{character_id}/attacks",
            headers=headers
        )
        assert attacks.status_code == 200, attacks.text
        assert attacks.json()[0]["name"] == "Длинный меч"
        assert attacks.json()[0]["damage"] == "1d8+3 рубящий"

        rolled = client.post(
            f"/api/characters/{character_id}/attacks/{attack_id}/roll",
            headers=headers
        )
        assert rolled.status_code == 200, rolled.text
        roll_payload = rolled.json()
        assert 1 <= roll_payload["roll"] <= 20
        assert roll_payload["bonus"] == 5
        assert roll_payload["total"] == roll_payload["roll"] + 5

        roll_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"}
        )
        assert roll_messages.status_code == 200, roll_messages.text
        assert any(
            message["formula"] == "1d20+5"
            and message["total"] == roll_payload["total"]
            and "Длинный меч" in message["content"]
            for message in roll_messages.json()
        )


def test_leaderboard_orders_users_by_karma_with_rank():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        users = []
        for username, karma in [
            ("leader-low", 3),
            ("leader-high", 11),
            ("leader-middle", 7)
        ]:
            created = client.post("/api/users", json={
                "username": username,
                "email": f"{username}@example.com",
                "password": TEST_USER_PASSWORD
            })
            assert created.status_code == 200, created.text
            users.append((created.json()["id"], username, karma))
            adjusted = client.post(
                f"/api/admin/users/{created.json()['id']}/karma",
                headers=admin_headers,
                json={"amount": karma, "reason": "Тест"}
            )
            assert adjusted.status_code == 200, adjusted.text

        leaderboard = client.get("/api/leaderboard", headers=admin_headers)
        assert leaderboard.status_code == 200, leaderboard.text
        payload = leaderboard.json()
        ranked = [
            (entry["rank"], entry["username"], entry["karma"])
            for entry in payload
            if entry["username"].startswith("leader-")
        ]
        assert ranked == [
            (1, "leader-high", 11),
            (2, "leader-middle", 7),
            (3, "leader-low", 3)
        ]


def test_chat_messages_and_dice_roll_commands_persist_to_channels():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}

        message = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"content": "Кто идёт в экспедицию?"}
        )
        assert message.status_code == 200, message.text
        assert message.json()["channel"] == "general"
        assert message.json()["content"] == "Кто идёт в экспедицию?"

        general = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "general"}
        )
        assert general.status_code == 200, general.text
        assert general.json()[0]["content"] == "Кто идёт в экспедицию?"

        roll = client.post(
            "/api/dice/roll",
            headers=headers,
            json={"formula": "/r 2d6"}
        )
        assert roll.status_code == 200, roll.text
        roll_payload = roll.json()
        assert roll_payload["formula"] == "2d6"
        assert len(roll_payload["rolls"]) == 2
        assert all(1 <= value <= 6 for value in roll_payload["rolls"])
        assert roll_payload["total"] == sum(roll_payload["rolls"])

        arbitrary = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"content": "/r 1d37"}
        )
        assert arbitrary.status_code == 200, arbitrary.text
        assert arbitrary.json()["channel"] == "rolls"
        assert arbitrary.json()["formula"] == "1d37"
        assert len(arbitrary.json()["rolls"]) == 1
        assert 1 <= arbitrary.json()["rolls"][0] <= 37

        rolls = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"}
        )
        assert rolls.status_code == 200, rolls.text
        formulas = [message["formula"] for message in rolls.json()]
        assert "2d6" in formulas
        assert "1d37" in formulas


@pytest.mark.parametrize("role", ["admin", "head_admin", "project_owner"])
def test_administrative_roles_can_delete_any_chat_message(role):
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        client.post("/api/users", json={
            "username": f"moderator-{role}",
            "email": f"moderator-{role}@example.com",
            "password": TEST_USER_PASSWORD,
        })
        user_id = next(
            user["id"] for user in client.get(
                "/api/admin/users", headers=owner_headers
            ).json() if user["username"] == f"moderator-{role}"
        )
        changed = client.post(
            f"/api/admin/users/{user_id}/role",
            headers=owner_headers,
            json={"role": role},
        )
        assert changed.status_code == 200, changed.text

        player = client.post("/api/users", json={
            "username": f"author-{role}",
            "email": f"author-{role}@example.com",
            "password": TEST_USER_PASSWORD,
        })
        assert player.status_code == 200, player.text
        player_headers = {
            "Authorization": (
                f"Bearer {login(client, f'author-{role}', TEST_USER_PASSWORD)}"
            )
        }
        message = client.post(
            "/api/chat/messages",
            headers=player_headers,
            json={"content": "Удалить это сообщение"},
        )
        moderator_headers = {
            "Authorization": (
                f"Bearer {login(client, f'moderator-{role}', TEST_USER_PASSWORD)}"
            )
        }

        deleted = client.delete(
            f"/api/chat/messages/{message.json()['id']}",
            headers=moderator_headers,
        )

        assert deleted.status_code == 204, deleted.text
        assert client.get(
            "/api/chat/messages",
            headers=player_headers,
            params={"channel": "general"},
        ).json() == []


def test_player_cannot_delete_chat_messages_and_missing_message_returns_404():
    with TestClient(app) as client:
        client.post("/api/users", json={
            "username": "chat-player",
            "email": "chat-player@example.com",
            "password": TEST_USER_PASSWORD,
        })
        player_headers = {
            "Authorization": f"Bearer {login(client, 'chat-player', TEST_USER_PASSWORD)}"
        }
        message = client.post(
            "/api/chat/messages",
            headers=player_headers,
            json={"content": "Чужое сообщение"},
        )

        forbidden = client.delete(
            f"/api/chat/messages/{message.json()['id']}",
            headers=player_headers,
        )
        assert forbidden.status_code == 403

        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        missing = client.delete(
            "/api/chat/messages/999999",
            headers=owner_headers,
        )
        assert missing.status_code == 404


def test_character_multiclass_levels_are_persisted_and_sum_to_total_level():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Боевой маг",
            "class_name": "Воин",
            "level": 8,
            "route": "Open Table",
            "class_levels": [
                {"class_name": "Воин", "level": 5},
                {"class_name": "Плут", "level": 3},
            ],
        })

        assert created.status_code == 200, created.text
        assert created.json()["level"] == 8
        assert created.json()["class_levels"] == [
            {"class_name": "Воин", "level": 5},
            {"class_name": "Плут", "level": 3},
        ]
        listed = client.get("/api/characters", headers=headers).json()[0]
        assert listed["class_levels"] == created.json()["class_levels"]


def test_character_multiclass_rejects_invalid_totals_duplicates_and_bounds():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        base = {
            "name": "Invalid Multiclass",
            "class_name": "Воин",
            "level": 8,
            "route": "Open Table",
        }
        invalid_class_levels = (
            [{"class_name": "Воин", "level": 5}, {"class_name": "Плут", "level": 2}],
            [{"class_name": "Воин", "level": 5}, {"class_name": "Воин", "level": 3}],
            [{"class_name": "Воин", "level": 0}, {"class_name": "Плут", "level": 8}],
            [{"class_name": "Воин", "level": 20}, {"class_name": "Плут", "level": 1}],
        )
        for class_levels in invalid_class_levels:
            response = client.post(
                "/api/characters",
                headers=headers,
                json={**base, "class_levels": class_levels},
            )
            assert response.status_code == 422, response.text


def test_xp_progression_keeps_multiclass_total_in_sync():
    character = Character(
        level=8,
        xp=0,
        class_name="Воин",
        class_levels=[
            {"class_name": "Воин", "level": 5},
            {"class_name": "Плут", "level": 3},
        ],
    )

    apply_xp_delta(character, 9)

    assert character.level == 9
    assert character.xp == 0
    assert character.class_levels == [
        {"class_name": "Воин", "level": 5},
        {"class_name": "Плут", "level": 4},
    ]


def test_xp_progression_keeps_single_class_level_in_sync():
    character = Character(
        level=3,
        xp=0,
        class_name="Воин",
        class_levels=[{"class_name": "Воин", "level": 3}],
    )

    apply_xp_delta(character, 4)

    assert character.level == 4
    assert character.xp == 0
    assert character.class_levels == [{"class_name": "Воин", "level": 4}]


def test_admin_direct_level_edit_keeps_single_class_level_in_sync():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Level Correction",
            "class_name": "Воин",
            "level": 3,
            "route": "Open Table",
        })

        edited = client.patch(
            f"/api/admin/characters/{created.json()['id']}",
            headers=headers,
            json={"level": 4},
        )

        assert edited.status_code == 200, edited.text
        assert edited.json()["level"] == 4
        assert edited.json()["class_levels"] == [
            {"class_name": "Воин", "level": 4}
        ]


def test_owner_and_admin_can_edit_multiclass_but_other_player_cannot():
    with TestClient(app) as client:
        client.post("/api/users", json={
            "username": "multiclass-owner",
            "email": "multiclass-owner@example.com",
            "password": TEST_USER_PASSWORD,
        })
        owner_headers = {
            "Authorization": (
                f"Bearer {login(client, 'multiclass-owner', TEST_USER_PASSWORD)}"
            )
        }
        created = client.post("/api/characters", headers=owner_headers, json={
            "name": "Герой",
            "class_name": "Воин",
            "level": 5,
            "route": "Open Table",
        })
        character_id = created.json()["id"]
        class_levels = [
            {"class_name": "Воин", "level": 3},
            {"class_name": "Плут", "level": 2},
        ]

        owner_edit = client.patch(
            f"/api/characters/{character_id}",
            headers=owner_headers,
            json={"class_levels": class_levels},
        )
        assert owner_edit.status_code == 200, owner_edit.text
        assert owner_edit.json()["class_levels"] == class_levels

        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        admin_edit = client.patch(
            f"/api/admin/characters/{character_id}",
            headers=admin_headers,
            json={"class_levels": [
                {"class_name": "Воин", "level": 4},
                {"class_name": "Плут", "level": 1},
            ]},
        )
        assert admin_edit.status_code == 200, admin_edit.text

        client.post("/api/users", json={
            "username": "multiclass-stranger",
            "email": "multiclass-stranger@example.com",
            "password": TEST_USER_PASSWORD,
        })
        stranger_headers = {
            "Authorization": (
                f"Bearer {login(client, 'multiclass-stranger', TEST_USER_PASSWORD)}"
            )
        }
        forbidden = client.patch(
            f"/api/characters/{character_id}",
            headers=stranger_headers,
            json={"class_levels": class_levels},
        )
        assert forbidden.status_code == 404


def test_player_can_only_redistribute_existing_class_levels():
    with TestClient(app) as client:
        client.post("/api/users", json={
            "username": "level-redistributor",
            "email": "level-redistributor@example.com",
            "password": TEST_USER_PASSWORD,
        })
        headers = {
            "Authorization": (
                f"Bearer {login(client, 'level-redistributor', TEST_USER_PASSWORD)}"
            )
        }
        created = client.post("/api/characters", headers=headers, json={
            "name": "Мультикласс",
            "class_name": "Бард",
            "level": 7,
            "route": "Open Table",
            "class_levels": [
                {"class_name": "Бард", "level": 3},
                {"class_name": "Паладин", "level": 4},
            ],
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        for invalid_levels in (
            [
                {"class_name": "Бард", "level": 5},
                {"class_name": "Паладин", "level": 4},
            ],
            [
                {"class_name": "Бард", "level": 2},
                {"class_name": "Паладин", "level": 3},
            ],
        ):
            rejected = client.patch(
                f"/api/characters/{character_id}",
                headers=headers,
                json={"class_levels": invalid_levels},
            )
            assert rejected.status_code == 422, rejected.text

        redistributed = client.patch(
            f"/api/characters/{character_id}",
            headers=headers,
            json={"class_levels": [
                {"class_name": "Бард", "level": 1},
                {"class_name": "Паладин", "level": 6},
            ]},
        )
        assert redistributed.status_code == 200, redistributed.text
        assert redistributed.json()["level"] == 7
        assert redistributed.json()["class_levels"] == [
            {"class_name": "Бард", "level": 1},
            {"class_name": "Паладин", "level": 6},
        ]


def test_player_cannot_change_single_class_level():
    with TestClient(app) as client:
        client.post("/api/users", json={
            "username": "single-level-owner",
            "email": "single-level-owner@example.com",
            "password": TEST_USER_PASSWORD,
        })
        headers = {
            "Authorization": (
                f"Bearer {login(client, 'single-level-owner', TEST_USER_PASSWORD)}"
            )
        }
        created = client.post("/api/characters", headers=headers, json={
            "name": "Воитель",
            "class_name": "Воин",
            "level": 7,
            "route": "Open Table",
        })
        character_id = created.json()["id"]

        for requested_level in (6, 8):
            rejected = client.patch(
                f"/api/characters/{character_id}",
                headers=headers,
                json={"class_levels": [
                    {"class_name": "Воин", "level": requested_level},
                ]},
            )
            assert rejected.status_code == 422, rejected.text


def test_persisted_text_fields_enforce_boundaries():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Bounded Text Hero",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline",
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        accepted_message = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"content": "x" * MAX_CHAT_MESSAGE_LENGTH},
        )
        assert accepted_message.status_code == 200, accepted_message.text

        rejected_message = client.post(
            "/api/chat/messages",
            headers=headers,
            json={"content": "x" * (MAX_CHAT_MESSAGE_LENGTH + 1)},
        )
        assert rejected_message.status_code == 422

        accepted_notes = client.patch(
            f"/api/characters/{character_id}/inventory/notes",
            headers=headers,
            json={"notes": "x" * MAX_INVENTORY_NOTES_LENGTH},
        )
        assert accepted_notes.status_code == 200, accepted_notes.text

        rejected_notes = client.patch(
            f"/api/characters/{character_id}/inventory/notes",
            headers=headers,
            json={"notes": "x" * (MAX_INVENTORY_NOTES_LENGTH + 1)},
        )
        assert rejected_notes.status_code == 422


def test_direct_backend_rejects_oversized_request_body():
    with TestClient(app) as client:
        response = client.post(
            "/api/login",
            content=b"x" * (1_048_576 + 1),
            headers={"content-type": "application/json"},
        )

        assert response.status_code == 413


def test_chunked_request_body_is_limited_without_content_length():
    app_called = False

    async def downstream(_scope, receive, _send):
        nonlocal app_called
        app_called = True
        while (await receive()).get("more_body", False):
            pass

    middleware = RequestBodyLimitMiddleware(downstream, max_body_bytes=5)
    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    requests: list[Message] = [
        {"type": "http.request", "body": b"123", "more_body": True},
        {"type": "http.request", "body": b"456", "more_body": False},
    ]
    responses: list[Message] = []

    async def receive() -> Message:
        return requests.pop(0)

    async def send(message: Message) -> None:
        responses.append(message)

    anyio.run(middleware, scope, receive, send)

    assert app_called is True
    assert responses[0]["status"] == 413


def test_damage_roll_returns_dice_results_and_logs_to_rolls_channel():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Damage Roller",
            "class_name": "Воин",
            "level": 5,
            "route": "Frontline"
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        attack = client.post(
            f"/api/characters/{character_id}/attacks",
            headers=headers,
            json={"name": "Длинный меч", "attack_bonus": 5, "damage": "1d8+3"}
        )
        assert attack.status_code == 200, attack.text
        attack_id = attack.json()["id"]

        rolled = client.post(
            f"/api/characters/{character_id}/attacks/{attack_id}/roll-damage",
            headers=headers
        )
        assert rolled.status_code == 200, rolled.text
        payload = rolled.json()
        assert payload["attack_id"] == attack_id
        assert payload["name"] == "Длинный меч"
        assert len(payload["rolls"]) == 1
        assert 1 <= payload["rolls"][0] <= 8
        assert payload["modifier"] == 3
        assert payload["total"] == payload["rolls"][0] + 3

        roll_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"}
        )
        assert roll_messages.status_code == 200, roll_messages.text
        assert any(
            "Длинный меч" in message["content"] and "урон" in message["content"]
            for message in roll_messages.json()
        )


def test_damage_roll_fails_for_attack_without_damage():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "No Damage Hero",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline"
        })
        character_id = created.json()["id"]
        attack = client.post(
            f"/api/characters/{character_id}/attacks",
            headers=headers,
            json={"name": "Удар", "attack_bonus": 3, "damage": ""}
        )
        attack_id = attack.json()["id"]
        response = client.post(
            f"/api/characters/{character_id}/attacks/{attack_id}/roll-damage",
            headers=headers
        )
        assert response.status_code == 400


def test_damage_roll_rejects_oversized_stored_damage_formulas():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Bounded Damage Hero",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline"
        })
        character_id = created.json()["id"]

        cases = [
            ("Too Many Dice", "5000d1", "Dice count must be between 1 and 100"),
            ("Too Many Sides", "1d10001", "Dice sides must be between 1 and 10000"),
        ]
        for name, damage, detail in cases:
            attack = client.post(
                f"/api/characters/{character_id}/attacks",
                headers=headers,
                json={"name": name, "attack_bonus": 3, "damage": damage}
            )
            assert attack.status_code == 200, attack.text
            attack_id = attack.json()["id"]

            response = client.post(
                f"/api/characters/{character_id}/attacks/{attack_id}/roll-damage",
                headers=headers
            )

            assert response.status_code == 400
            assert response.json()["detail"] == detail


def test_ability_roll_returns_d20_plus_modifier_and_logs():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Ability Roller",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline",
            "strength": 16
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        response = client.post(
            f"/api/characters/{character_id}/roll-ability/strength",
            headers=headers
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["ability"] == "strength"
        assert payload["score"] == 16
        assert payload["modifier"] == 3
        assert 1 <= payload["roll"] <= 20
        assert payload["total"] == payload["roll"] + 3

        roll_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"}
        )
        assert roll_messages.status_code == 200, roll_messages.text
        assert any(
            "Сила" in message["content"] and message["total"] == payload["total"]
            for message in roll_messages.json()
        )


def test_ability_roll_rejects_unknown_ability():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Ability Reject Hero",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline"
        })
        character_id = created.json()["id"]
        response = client.post(
            f"/api/characters/{character_id}/roll-ability/luck",
            headers=headers
        )
        assert response.status_code == 400


def test_saving_throw_roll_returns_d20_plus_modifier_and_logs():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Save Roller",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline",
            "dexterity": 14
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        response = client.post(
            f"/api/characters/{character_id}/roll-saving-throw/dexterity",
            headers=headers
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["ability"] == "dexterity"
        assert payload["bonus"] == 2
        assert 1 <= payload["roll"] <= 20
        assert payload["total"] == payload["roll"] + 2

        roll_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"}
        )
        assert roll_messages.status_code == 200, roll_messages.text
        assert any(
            "Ловкость" in message["content"]
            and "спасбросок" in message["content"]
            and message["total"] == payload["total"]
            for message in roll_messages.json()
        )


def test_saving_throw_proficiency_is_persisted_and_added_to_roll():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Resolute", "class_name": "Егерь", "level": 9,
            "route": "Wilds", "wisdom": 14,
            "saving_throw_proficiencies": ["wisdom", "strength"],
        })
        assert created.status_code == 200, created.text
        assert created.json()["saving_throw_proficiencies"] == ["strength", "wisdom"]
        with patch("app.api.characters.random.randint", return_value=10):
            rolled = client.post(
                f"/api/characters/{created.json()['id']}/roll-saving-throw/wisdom",
                headers=headers,
            )
        assert rolled.status_code == 200, rolled.text
        assert rolled.json()["bonus"] == 6
        assert rolled.json()["total"] == 16
        invalid = client.patch(
            f"/api/characters/{created.json()['id']}", headers=headers,
            json={"saving_throw_proficiencies": ["luck"]},
        )
        assert invalid.status_code == 422


def test_ranger_class_is_persisted_and_returned_by_character_endpoints():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Следопыт пустошей",
            "class_name": "Егерь",
            "level": 1,
            "route": "Путь охотника",
        })

        assert created.status_code == 200, created.text
        assert created.json()["class_name"] == "Егерь"

        character_id = created.json()["id"]
        assert any(
            character["id"] == character_id and character["class_name"] == "Егерь"
            for character in client.get("/api/characters", headers=headers).json()
        )


def test_skill_roll_uses_ability_proficiency_expertise_and_logs():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Skill Roller",
            "class_name": "Следопыт",
            "level": 9,
            "route": "Wilds",
            "strength": 16,
            "intelligence": 8,
            "wisdom": 14,
            "skill_proficiencies": ["athletics", "perception"],
            "skill_expertise": ["perception"],
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        with patch("app.api.characters.random.randint", side_effect=[8, 9, 10]):
            athletics = client.post(
                f"/api/characters/{character_id}/roll-skill/athletics",
                headers=headers,
            )
            perception = client.post(
                f"/api/characters/{character_id}/roll-skill/perception",
                headers=headers,
            )
            arcana = client.post(
                f"/api/characters/{character_id}/roll-skill/arcana",
                headers=headers,
            )

        assert athletics.status_code == 200, athletics.text
        assert athletics.json() == {
            "skill": "athletics",
            "ability": "strength",
            "modifier": 7,
            "roll": 8,
            "total": 15,
        }
        assert perception.status_code == 200, perception.text
        assert perception.json()["modifier"] == 10
        assert perception.json()["total"] == 19
        assert arcana.status_code == 200, arcana.text
        assert arcana.json()["modifier"] == -1
        assert arcana.json()["total"] == 9

        roll_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "rolls"},
        )
        assert roll_messages.status_code == 200, roll_messages.text
        contents = [message["content"] for message in roll_messages.json()]
        assert any("Атлетика" in content and "1d20+7" in content and "Итог: 15" in content for content in contents)
        assert any("Восприятие" in content and "1d20+10" in content and "Итог: 19" in content for content in contents)
        assert any("Магия" in content and "1d20-1" in content and "Итог: 9" in content for content in contents)


def test_skill_roll_rejects_unknown_skill_and_other_users_character():
    with TestClient(app) as client:
        admin_headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=admin_headers, json={
            "name": "Private Skill Roller",
            "class_name": "Воин",
            "level": 1,
            "route": "Frontline",
        })
        assert created.status_code == 200, created.text
        character_id = created.json()["id"]

        unknown = client.post(
            f"/api/characters/{character_id}/roll-skill/luck",
            headers=admin_headers,
        )
        assert unknown.status_code == 400

        user = client.post("/api/users", json={
            "username": "other-skill-user",
            "email": "other-skill-user@example.com",
            "password": TEST_USER_PASSWORD,
        })
        assert user.status_code == 200, user.text
        other_headers = {"Authorization": f"Bearer {login(client, 'other-skill-user', TEST_USER_PASSWORD)}"}
        forbidden = client.post(
            f"/api/characters/{character_id}/roll-skill/athletics",
            headers=other_headers,
        )
        assert forbidden.status_code == 404


def test_chat_messages_pagination_with_limit_and_before_id():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}

        for i in range(5):
            resp = client.post(
                "/api/chat/messages",
                headers=headers,
                json={"content": f"Сообщение {i + 1}"}
            )
            assert resp.status_code == 200, resp.text

        all_messages = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "general", "limit": 200}
        )
        assert all_messages.status_code == 200, all_messages.text
        all_data = all_messages.json()
        assert len(all_data) == 5

        first_two = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "general", "limit": 2}
        )
        assert first_two.status_code == 200, first_two.text
        page_data = first_two.json()
        assert len(page_data) == 2
        assert page_data[0]["content"] == "Сообщение 4"
        assert page_data[1]["content"] == "Сообщение 5"

        oldest_id = page_data[0]["id"]
        older = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "general", "limit": 200, "before_id": oldest_id}
        )
        assert older.status_code == 200, older.text
        older_data = older.json()
        assert len(older_data) == 3
        assert all(m["id"] < oldest_id for m in older_data)
        assert older_data[0]["content"] == "Сообщение 1"
        assert older_data[1]["content"] == "Сообщение 2"
        assert older_data[2]["content"] == "Сообщение 3"

        invalid = client.get(
            "/api/chat/messages",
            headers=headers,
            params={"channel": "general", "limit": 0}
        )
        assert invalid.status_code == 422


def _register(client: TestClient, username: str) -> int:
    created = client.post("/api/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": TEST_USER_PASSWORD
    })
    assert created.status_code == 200, created.text
    return created.json()["id"]


def test_admin_user_list_supports_bounded_pagination_and_reports_total():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        for index in range(5):
            _register(client, f"paged-user-{index}")

        response = client.get(
            "/api/admin/users",
            headers=headers,
            params={"page": 2, "page_size": 2},
        )

        assert response.status_code == 200, response.text
        assert [item["username"] for item in response.json()["items"]] == [
            "paged-user-1",
            "paged-user-2",
        ]
        assert response.json()["page"] == 2
        assert response.json()["page_size"] == 2
        assert response.json()["total"] == 6
        assert response.json()["pages"] == 3

        invalid = client.get(
            "/api/admin/users",
            headers=headers,
            params={"page_size": 101},
        )
        assert invalid.status_code == 422


def test_admin_character_list_supports_bounded_pagination_and_reports_total():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        headers = {"Authorization": f"Bearer {token}"}
        for index in range(5):
            created = client.post(
                "/api/characters",
                headers=headers,
                json={
                    "name": f"Paged Character {index}",
                    "class_name": "Fighter",
                    "level": 1,
                    "route": "Open Table",
                },
            )
            assert created.status_code == 200, created.text

        response = client.get(
            "/api/admin/characters",
            headers=headers,
            params={"page": 3, "page_size": 2},
        )

        assert response.status_code == 200, response.text
        assert [item["name"] for item in response.json()["items"]] == [
            "Paged Character 4"
        ]
        assert response.json()["page"] == 3
        assert response.json()["page_size"] == 2
        assert response.json()["total"] == 5
        assert response.json()["pages"] == 3

        beyond_last_page = client.get(
            "/api/admin/characters",
            headers=headers,
            params={"page": 4, "page_size": 2},
        )
        assert beyond_last_page.status_code == 200, beyond_last_page.text
        assert beyond_last_page.json()["items"] == []
        assert beyond_last_page.json()["total"] == 5


def test_seeded_admin_account_has_owner_role():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["role"] == "owner"
        assert body["is_owner"] is True
        assert body["is_admin"] is True


def test_new_users_default_to_player_role():
    with TestClient(app) as client:
        _register(client, "fresh-player")
        token = login(client, "fresh-player", TEST_USER_PASSWORD)
        me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text
        body = me.json()
        assert body["role"] == "player"
        assert body["is_admin"] is False
        assert body["is_owner"] is False


def test_owner_can_assign_roles_and_promotion_grants_admin_tools():
    with TestClient(app) as client:
        owner_token = login(client, "admin", "admin123")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        user_id = _register(client, "promote-me")
        player_headers = {
            "Authorization": f"Bearer {login(client, 'promote-me', TEST_USER_PASSWORD)}"
        }

        # Player cannot reach admin-only endpoints before promotion.
        denied = client.get("/api/admin/users", headers=player_headers)
        assert denied.status_code == 403

        promoted = client.post(
            f"/api/admin/users/{user_id}/role",
            headers=owner_headers,
            json={"role": "admin"}
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "admin"
        assert promoted.json()["is_admin"] is True
        assert promoted.json()["is_owner"] is False

        # After promotion the user can use the admin tools.
        allowed = client.get("/api/admin/users", headers=player_headers)
        assert allowed.status_code == 200, allowed.text
        roles = {row["username"]: row["role"] for row in allowed.json()}
        assert roles["promote-me"] == "admin"
        assert roles["admin"] == "owner"


def test_owner_can_assign_technician_with_limited_admin_tools():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        technician_id = _register(client, "global-technician")
        target_id = _register(client, "technician-target")

        promoted = client.post(
            f"/api/admin/users/{technician_id}/role",
            headers=owner_headers,
            json={"role": "technician"},
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "technician"
        assert promoted.json()["is_admin"] is True

        with SessionLocal() as db:
            default_project = db.query(Project).filter(
                Project.name == DEFAULT_PROJECT_NAME
            ).one()
            membership = db.query(ProjectMembership).filter_by(
                project_id=default_project.id,
                user_id=technician_id,
            ).one()
            assert membership.role == "technician"

        technician_headers = {
            "Authorization": f"Bearer {login(client, 'global-technician', TEST_USER_PASSWORD)}"
        }
        assert client.post(
            f"/api/admin/users/{target_id}/karma/add",
            headers=technician_headers,
            json={"amount": 2, "reason": "Technician grant"},
        ).status_code == 200
        assert client.post(
            f"/api/admin/users/{target_id}/role",
            headers=technician_headers,
            json={"role": "player"},
        ).status_code == 403


def test_admin_role_cannot_manage_roles_only_owner_can():
    with TestClient(app) as client:
        owner_token = login(client, "admin", "admin123")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}

        admin_id = _register(client, "an-admin")
        target_id = _register(client, "a-target")

        client.post(
            f"/api/admin/users/{admin_id}/role",
            headers=owner_headers,
            json={"role": "admin"}
        )
        admin_headers = {
            "Authorization": f"Bearer {login(client, 'an-admin', TEST_USER_PASSWORD)}"
        }

        # Admins keep their game-master powers (karma) ...
        karma = client.post(
            f"/api/admin/users/{target_id}/karma/add",
            headers=admin_headers,
            json={"amount": 2, "reason": "Тест"}
        )
        assert karma.status_code == 200, karma.text

        # ... but cannot change roles (owner only).
        forbidden = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=admin_headers,
            json={"role": "admin"}
        )
        assert forbidden.status_code == 403


def test_role_endpoint_validates_role_and_blocks_self_demotion():
    with TestClient(app) as client:
        owner_token = login(client, "admin", "admin123")
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        owner_id = client.get("/api/me", headers=owner_headers).json()["id"]

        user_id = _register(client, "role-validate")

        unknown = client.post(
            f"/api/admin/users/{user_id}/role",
            headers=owner_headers,
            json={"role": "superuser"}
        )
        assert unknown.status_code == 400

        self_demote = client.post(
            f"/api/admin/users/{owner_id}/role",
            headers=owner_headers,
            json={"role": "player"}
        )
        assert self_demote.status_code == 400

        missing = client.post(
            "/api/admin/users/999999/role",
            headers=owner_headers,
            json={"role": "admin"}
        )
        assert missing.status_code == 404


def _promote(client, owner_headers, user_id, role):
    response = client.post(
        f"/api/admin/users/{user_id}/role",
        headers=owner_headers,
        json={"role": role}
    )
    assert response.status_code == 200, response.text
    return response


def test_owner_can_appoint_head_admin_with_full_admin_tools():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }

        user_id = _register(client, "deputy")
        promoted = _promote(client, owner_headers, user_id, "head_admin")
        body = promoted.json()
        assert body["role"] == "head_admin"
        assert body["is_head_admin"] is True
        assert body["is_admin"] is True
        assert body["is_owner"] is False

        head_headers = {
            "Authorization": f"Bearer {login(client, 'deputy', TEST_USER_PASSWORD)}"
        }
        me = client.get("/api/me", headers=head_headers).json()
        assert me["role"] == "head_admin"
        assert me["is_head_admin"] is True
        assert me["is_admin"] is True
        assert me["is_owner"] is False

        # Head admins have access to the game-master endpoints.
        users = client.get("/api/admin/users", headers=head_headers)
        assert users.status_code == 200, users.text


def test_head_admin_can_manage_admins_and_players():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }

        head_id = _register(client, "deputy")
        target_id = _register(client, "regular")
        _promote(client, owner_headers, head_id, "head_admin")

        head_headers = {
            "Authorization": f"Bearer {login(client, 'deputy', TEST_USER_PASSWORD)}"
        }

        promoted = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=head_headers,
            json={"role": "admin"}
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "admin"

        demoted = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=head_headers,
            json={"role": "player"}
        )
        assert demoted.status_code == 200, demoted.text
        assert demoted.json()["role"] == "player"


def test_head_admin_can_assign_technician():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        head_id = _register(client, "technician-manager")
        target_id = _register(client, "new-technician")
        _promote(client, owner_headers, head_id, "head_admin")
        head_headers = {
            "Authorization": f"Bearer {login(client, 'technician-manager', TEST_USER_PASSWORD)}"
        }

        promoted = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=head_headers,
            json={"role": "technician"},
        )
        assert promoted.status_code == 200, promoted.text
        assert promoted.json()["role"] == "technician"
        assert promoted.json()["is_admin"] is True


def test_head_admin_cannot_touch_owner_or_grant_privileged_roles():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        owner_id = client.get("/api/me", headers=owner_headers).json()["id"]

        head_id = _register(client, "deputy")
        other_head_id = _register(client, "deputy-two")
        target_id = _register(client, "regular")
        _promote(client, owner_headers, head_id, "head_admin")
        _promote(client, owner_headers, other_head_id, "head_admin")

        head_headers = {
            "Authorization": f"Bearer {login(client, 'deputy', TEST_USER_PASSWORD)}"
        }

        # Cannot change the owner's role in any way.
        demote_owner = client.post(
            f"/api/admin/users/{owner_id}/role",
            headers=head_headers,
            json={"role": "player"}
        )
        assert demote_owner.status_code == 403, demote_owner.text

        # Cannot appoint a new owner.
        appoint_owner = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=head_headers,
            json={"role": "owner"}
        )
        assert appoint_owner.status_code == 403, appoint_owner.text

        # Cannot grant the head-admin role (owner-only privilege).
        grant_head = client.post(
            f"/api/admin/users/{target_id}/role",
            headers=head_headers,
            json={"role": "head_admin"}
        )
        assert grant_head.status_code == 403, grant_head.text

        # Cannot change another head admin's role.
        touch_head = client.post(
            f"/api/admin/users/{other_head_id}/role",
            headers=head_headers,
            json={"role": "admin"}
        )
        assert touch_head.status_code == 403, touch_head.text

        # The owner is untouched and the targets keep their roles.
        owner_me = client.get("/api/me", headers=owner_headers).json()
        assert owner_me["role"] == "owner"


def test_owner_can_revoke_head_admin_role():
    with TestClient(app) as client:
        owner_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }

        head_id = _register(client, "deputy")
        _promote(client, owner_headers, head_id, "head_admin")

        revoked = _promote(client, owner_headers, head_id, "player")
        assert revoked.json()["role"] == "player"
        assert revoked.json()["is_head_admin"] is False
        assert revoked.json()["is_admin"] is False


def test_migrate_user_roles_uses_boolean_true_comparison():
    """migrate_user_roles must compare is_admin with TRUE, not 1.

    PostgreSQL rejects ``is_admin = 1`` on a boolean column, so the
    comparison must use ``is_admin = TRUE`` to be compatible with both
    PostgreSQL and SQLite.
    """
    from sqlalchemy import text
    from app.db.database import engine
    from app.main import migrate_user_roles
    from app.core.roles import Role

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS users"))
        conn.execute(text(
            "CREATE TABLE users ("
            "  id INTEGER PRIMARY KEY,"
            "  username TEXT NOT NULL,"
            "  email TEXT NOT NULL,"
            "  hashed_password TEXT NOT NULL,"
            "  karma INTEGER NOT NULL DEFAULT 0,"
            "  is_admin BOOLEAN NOT NULL DEFAULT 0"
            ")"
        ))
        conn.execute(text(
            "INSERT INTO users (id, username, email, hashed_password, is_admin) VALUES "
            "(1, 'legacy-admin', 'la@example.com', 'x', TRUE),"
            "(2, 'legacy-player', 'lp@example.com', 'x', FALSE)"
        ))

    migrate_user_roles()

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT username, role FROM users ORDER BY id")
        ).fetchall()

    assert rows[0] == ("legacy-admin", Role.ADMIN), (
        "Legacy admin with is_admin=TRUE should be migrated to 'admin' role"
    )
    assert rows[1] == ("legacy-player", Role.PLAYER), (
        "Legacy player with is_admin=FALSE should be migrated to 'player' role"
    )


# ---------------------------------------------------------------------------
# Game calendar / free-day tracking
# ---------------------------------------------------------------------------

from datetime import timedelta

from app.core.calendar import GAME_EPOCH


def _make_character(client, headers, **overrides):
    payload = {
        "name": "Calendar Hero",
        "class_name": "Wizard",
        "level": 1,
        "route": "Market",
        "investigation": 20,
    }
    payload.update(overrides)
    created = client.post("/api/characters", headers=headers, json=payload)
    assert created.status_code == 200, created.text
    return created.json()


def test_character_defaults_to_game_epoch_creation_date():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        character = _make_character(client, headers)
        assert character["game_created_at"] == GAME_EPOCH.isoformat()


def test_character_accepts_custom_creation_date():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        character = _make_character(client, headers, game_created_at="2025-09-15")
        assert character["game_created_at"] == "2025-09-15"


def test_character_rejects_creation_date_before_epoch():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        created = client.post("/api/characters", headers=headers, json={
            "name": "Too Early",
            "class_name": "Wizard",
            "level": 1,
            "route": "Market",
            "game_created_at": "2025-05-31",
        })
        assert created.status_code == 400, created.text


def test_calendar_summary_reports_total_busy_and_free_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        character = _make_character(client, headers)
        cid = character["id"]

        summary = client.get(
            f"/api/characters/{cid}/calendar", headers=headers
        ).json()
        assert summary["created_at"] == GAME_EPOCH.isoformat()
        assert summary["busy_days"] == 0
        assert summary["free_days"] == summary["total_days"]
        assert summary["total_days"] > 0


def test_manual_downtime_entry_reduces_free_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]

        response = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 5, "reason": "Крафт"},
        )
        assert response.status_code == 200, response.text
        summary = response.json()
        assert summary["busy_days"] == 5
        assert summary["free_days"] == summary["total_days"] - 5
        assert len(summary["entries"]) == 1
        assert summary["entries"][0]["source"] == "manual"
        assert summary["entries"][0]["reason"] == "Крафт"


def test_downtime_entry_reports_inclusive_end_date(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2026, 10, 9),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]

        response = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2026-07-01", "days": 100, "reason": "Крафт"},
        )

        assert response.status_code == 200, response.text
        entry = response.json()["entries"][0]
        assert entry["start_date"] == "2026-07-01"
        assert entry["end_date"] == "2026-10-08"
        assert entry["days"] == 100


def test_manual_downtime_cannot_start_before_creation_date():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers, game_created_at="2025-09-15")["id"]

        rejected = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-09-10", "days": 1, "reason": "Слишком рано"},
        )
        assert rejected.status_code == 400, rejected.text

        accepted = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-09-20", "days": 1, "reason": "Норм"},
        )
        assert accepted.status_code == 200, accepted.text


def test_manual_downtime_rejects_non_positive_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        rejected = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 0, "reason": "Ничего"},
        )
        assert rejected.status_code == 400, rejected.text


def test_manual_downtime_rejects_duplicate_and_overlapping_entries():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        created = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-10", "days": 5, "reason": "Крафт"},
        )
        assert created.status_code == 200, created.text

        for start_date, days in (
            ("2025-06-10", 5),  # exact duplicate
            ("2025-06-09", 2),  # overlaps the beginning
            ("2025-06-12", 1),  # contained by the existing entry
            ("2025-06-14", 2),  # overlaps the end
        ):
            rejected = client.post(
                f"/api/characters/{cid}/calendar/downtime",
                headers=headers,
                json={"start_date": start_date, "days": days, "reason": "Дубль"},
            )
            assert rejected.status_code == 409, rejected.text
            assert "пересекается" in rejected.json()["detail"]

        before = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-09", "days": 1, "reason": "До"},
        )
        assert before.status_code == 200, before.text
        after = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-15", "days": 1, "reason": "После"},
        )
        assert after.status_code == 200, after.text
        assert len(after.json()["entries"]) == 3


def test_admin_downtime_update_rejects_overlap_but_ignores_edited_entry():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        first = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 3, "reason": "Первое"},
        )
        assert first.status_code == 200, first.text
        second = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-10", "days": 3, "reason": "Второе"},
        )
        assert second.status_code == 200, second.text
        second_id = next(
            entry["id"]
            for entry in second.json()["entries"]
            if entry["start_date"] == "2025-06-10"
            and entry["reason"] == "Второе"
        )

        unchanged_window = client.patch(
            f"/api/characters/{cid}/calendar/downtime/{second_id}",
            headers=headers,
            json={"reason": "Новое описание"},
        )
        assert unchanged_window.status_code == 200, unchanged_window.text

        rejected = client.patch(
            f"/api/characters/{cid}/calendar/downtime/{second_id}",
            headers=headers,
            json={"start_date": "2025-06-03", "days": 2},
        )
        assert rejected.status_code == 409, rejected.text

        summary = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        edited = next(row for row in summary.json()["entries"] if row["id"] == second_id)
        assert edited["start_date"] == "2025-06-10"
        assert edited["days"] == 3


def test_downtime_overlap_is_scoped_to_calendar_actor(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        updated = client.patch(
            f"/api/admin/characters/{cid}",
            headers=headers,
            json={
                "personal_hireling_enabled": True,
                "personal_hireling_acquired_at": "2025-06-01",
            },
        )
        assert updated.status_code == 200, updated.text

        character_entry = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 2, "reason": "Персонаж"},
        )
        assert character_entry.status_code == 200, character_entry.text
        hireling_entry = client.post(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 2, "reason": "Наёмник"},
        )
        assert hireling_entry.status_code == 200, hireling_entry.text

        overlapping_hireling_entry = client.post(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime",
            headers=headers,
            json={"start_date": "2025-06-02", "days": 1, "reason": "Дубль"},
        )
        assert overlapping_hireling_entry.status_code == 409


def test_manual_downtime_rejects_span_past_current_game_date(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(
            client, headers, game_created_at="2025-06-01"
        )["id"]

        accepted = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={
                "start_date": "2025-06-01",
                "days": 9,
                "reason": "В пределах календаря",
            },
        )
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["busy_days"] == 9

        rejected = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={
                "start_date": "2025-06-01",
                "days": 10000,
                "reason": "Слишком длинная запись",
            },
        )
        assert rejected.status_code == 400, rejected.text

        summary = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert summary.status_code == 200, summary.text
        assert len(summary.json()["entries"]) == 1


def test_calendar_entries_are_paginated_newest_first():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        for day in range(1, 4):
            response = client.post(
                f"/api/characters/{cid}/calendar/downtime",
                headers=headers,
                json={
                    "start_date": f"2025-06-0{day}",
                    "days": 1,
                    "reason": f"Entry {day}",
                },
            )
            assert response.status_code == 200, response.text

        first = client.get(
            f"/api/characters/{cid}/calendar?page=1&page_size=2",
            headers=headers,
        )
        assert first.status_code == 200, first.text
        assert first.json()["total_entries"] == 3
        assert first.json()["page"] == 1
        assert first.json()["page_size"] == 2
        assert [entry["reason"] for entry in first.json()["entries"]] == [
            "Entry 3",
            "Entry 2",
        ]

        second = client.get(
            f"/api/characters/{cid}/calendar?page=2&page_size=2",
            headers=headers,
        )
        assert second.status_code == 200, second.text
        assert [entry["reason"] for entry in second.json()["entries"]] == [
            "Entry 1",
        ]


def test_character_skill_proficiency_and_expertise_are_persisted_and_validated():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        character = _make_character(client, headers)
        cid = character["id"]

        updated = client.patch(
            f"/api/characters/{cid}",
            headers=headers,
            json={
                "skill_proficiencies": ["athletics", "perception"],
                "skill_expertise": ["perception"],
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["skill_proficiencies"] == ["athletics", "perception"]
        assert updated.json()["skill_expertise"] == ["perception"]

        invalid = client.patch(
            f"/api/characters/{cid}",
            headers=headers,
            json={"skill_proficiencies": [], "skill_expertise": ["perception"]},
        )
        assert invalid.status_code == 422, invalid.text


def test_agent_calendar_entries_are_paginated():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        enabled = client.patch(
            f"/api/admin/characters/{cid}",
            headers=headers,
            json={
                "personal_hireling_enabled": True,
                "personal_hireling_acquired_at": "2025-06-01",
            },
        )
        assert enabled.status_code == 200, enabled.text
        for day in range(1, 4):
            added = client.post(
                f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime",
                headers=headers,
                json={
                    "start_date": f"2025-06-0{day}",
                    "days": 1,
                    "reason": f"Hireling {day}",
                },
            )
            assert added.status_code == 200, added.text

        response = client.get(
            f"/api/characters/{cid}/calendar/agents/personal_hireling?page=2&page_size=2",
            headers=headers,
        )
        assert response.status_code == 200, response.text
        assert response.json()["total_entries"] == 3
        assert [entry["reason"] for entry in response.json()["entries"]] == [
            "Hireling 1",
        ]


def test_admin_downtime_update_rejects_span_past_current_game_date(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(
            client, headers, game_created_at="2025-06-01"
        )["id"]
        created = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 1, "reason": "Крафт"},
        )
        assert created.status_code == 200, created.text
        summary = created.json()
        entry_id = summary["entries"][0]["id"]

        rejected = client.patch(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=headers,
            json={"days": 10000},
        )
        assert rejected.status_code == 400, rejected.text

        summary = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert summary.status_code == 200, summary.text
        assert summary.json()["entries"][0]["days"] == 1


def test_downtime_entry_can_be_deleted():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        summary = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-01", "days": 3, "reason": "Крафт"},
        ).json()
        entry_id = summary["entries"][0]["id"]

        deleted = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=headers,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["busy_days"] == 0
        assert deleted.json()["entries"] == []


def test_shop_search_spends_oldest_free_days_first():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(client, headers)["id"]
        client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"},
        )

        search = client.post(
            f"/api/characters/{cid}/shop/search",
            headers=headers,
            json={
                "mode": "buy",
                "item_name": "Healing Potion",
                "rarity": "Обычный",
                "is_consumable": True,
                "searcher_type": "character",
            },
        )
        assert search.status_code == 200, search.text
        spent_days = search.json()["days"]
        assert spent_days > 0

        summary = client.get(
            f"/api/characters/{cid}/calendar", headers=headers
        ).json()
        assert summary["busy_days"] == spent_days
        # Oldest days are spent first, so the run begins at the game epoch.
        shop_entries = [e for e in summary["entries"] if e["source"] == "shop"]
        assert shop_entries
        assert shop_entries[0]["start_date"] == GAME_EPOCH.isoformat()


def test_shop_search_blocked_when_not_enough_free_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cid = _make_character(
            client, headers, game_created_at=yesterday
        )["id"]
        client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"},
        )
        # Occupy the single available free day so none remain.
        client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": yesterday, "days": 1, "reason": "Занят"},
        )

        search = client.post(
            f"/api/characters/{cid}/shop/search",
            headers=headers,
            json={
                "mode": "buy",
                "item_name": "Healing Potion",
                "rarity": "Обычный",
                "is_consumable": True,
                "searcher_type": "character",
            },
        )
        assert search.status_code == 400, search.text
        assert "свободных дней" in search.json()["detail"]

        # The blocked search must not have charged gold.
        inventory = client.get(
            f"/api/characters/{cid}/inventory", headers=headers
        ).json()
        assert inventory["gold"] == 10000


def test_paid_hireling_search_spends_gold_but_not_character_free_days():
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        cid = _make_character(
            client,
            headers,
            game_created_at=yesterday,
        )["id"]
        client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"},
        )
        occupied = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": yesterday, "days": 1, "reason": "Занят"},
        )
        assert occupied.status_code == 200, occupied.text
        assert occupied.json()["free_days"] == 0

        search = client.post(
            f"/api/characters/{cid}/shop/search",
            headers=headers,
            json={
                "mode": "buy",
                "item_name": "Healing Potion",
                "rarity": "Обычный",
                "is_consumable": True,
                "searcher_type": "paid_hireling",
                "hireling_level": "Эксперт",
            },
        )

        assert search.status_code == 200, search.text
        payload = search.json()
        assert payload["searcher_type"] == "paid_hireling"
        assert payload["hireling_cost"] >= 25
        assert payload["inventory"]["gold"] == 10000 - payload["hireling_cost"]

        summary = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert summary.status_code == 200, summary.text
        assert summary.json()["busy_days"] == 1
        assert summary.json()["free_days"] == 0
        assert len(summary.json()["entries"]) == 1


def test_personal_hireling_search_uses_own_day_pool(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(
            client,
            headers,
            game_created_at="2025-06-09",
        )["id"]
        client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"},
        )
        updated = client.patch(
            f"/api/admin/characters/{cid}",
            headers=headers,
            json={
                "personal_hireling_enabled": True,
                "personal_hireling_acquired_at": "2025-06-01",
                "personal_hireling_investigation": 20,
            },
        )
        assert updated.status_code == 200, updated.text
        occupied = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-09", "days": 1, "reason": "Занят"},
        )
        assert occupied.status_code == 200, occupied.text
        assert occupied.json()["free_days"] == 0

        search = client.post(
            f"/api/characters/{cid}/shop/search",
            headers=headers,
            json={
                "mode": "buy",
                "item_name": "Healing Potion",
                "rarity": "Обычный",
                "is_consumable": True,
                "searcher_type": "personal_hireling",
            },
        )

        assert search.status_code == 200, search.text
        payload = search.json()
        assert payload["searcher_type"] == "personal_hireling"
        assert payload["hireling_cost"] == 0
        assert payload["days"] > 0

        character_calendar = client.get(
            f"/api/characters/{cid}/calendar",
            headers=headers,
        )
        assert character_calendar.status_code == 200, character_calendar.text
        assert character_calendar.json()["busy_days"] == 1
        assert len(character_calendar.json()["entries"]) == 1

        admin_character = client.get(
            f"/api/admin/characters/{cid}",
            headers=headers,
        )
        assert admin_character.status_code == 200, admin_character.text
        admin_payload = admin_character.json()
        assert admin_payload["personal_hireling_busy_days"] == payload["days"]
        assert admin_payload["personal_hireling_free_days"] == 9 - payload["days"]


def test_player_cannot_self_grant_hireling_or_simulacrum():
    with TestClient(app) as client:
        created_user = client.post("/api/users", json={
            "username": "unit-granter",
            "email": "unit-granter@example.com",
            "password": TEST_USER_PASSWORD,
        })
        assert created_user.status_code == 200, created_user.text
        player_headers = {
            "Authorization": f"Bearer {login(client, 'unit-granter', TEST_USER_PASSWORD)}"
        }

        rejected_create = client.post("/api/characters", headers=player_headers, json={
            "name": "Unauthorized Hireling",
            "class_name": "Wizard",
            "level": 1,
            "route": "Market",
            "personal_hireling_enabled": True,
            "personal_hireling_acquired_at": "2025-06-01",
            "personal_hireling_investigation": 12,
            "simulacrum_enabled": True,
            "simulacrum_created_at": "2025-06-01",
            "simulacrum_investigation": 12,
        })
        assert rejected_create.status_code == 422, rejected_create.text

        character = client.post("/api/characters", headers=player_headers, json={
            "name": "Legitimate Hero",
            "class_name": "Wizard",
            "level": 1,
            "route": "Market",
        })
        assert character.status_code == 200, character.text
        cid = character.json()["id"]

        rejected_update = client.patch(
            f"/api/characters/{cid}",
            headers=player_headers,
            json={
                "personal_hireling_enabled": True,
                "simulacrum_enabled": True,
            },
        )
        assert rejected_update.status_code == 422, rejected_update.text

        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        admin_character = client.get(
            f"/api/admin/characters/{cid}",
            headers=admin_headers,
        )
        assert admin_character.status_code == 200, admin_character.text
        assert admin_character.json()["personal_hireling_enabled"] is False
        assert admin_character.json()["simulacrum_enabled"] is False


def test_admin_can_manage_personal_hireling_calendar_independently(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        cid = _make_character(
            client,
            admin_headers,
            game_created_at="2025-06-09",
        )["id"]
        updated = client.patch(
            f"/api/admin/characters/{cid}",
            headers=admin_headers,
            json={
                "personal_hireling_enabled": True,
                "personal_hireling_acquired_at": "2025-06-01",
                "personal_hireling_investigation": 8,
            },
        )
        assert updated.status_code == 200, updated.text

        added = client.post(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime",
            headers=admin_headers,
            json={
                "start_date": "2025-06-01",
                "days": 3,
                "reason": "Занят поручением",
            },
        )
        assert added.status_code == 200, added.text
        summary = added.json()
        assert summary["created_at"] == "2025-06-01"
        assert summary["busy_days"] == 3
        assert summary["free_days"] == 6
        assert summary["entries"][0]["agent_type"] == "personal_hireling"
        entry_id = summary["entries"][0]["id"]

        character_calendar = client.get(
            f"/api/characters/{cid}/calendar",
            headers=admin_headers,
        )
        assert character_calendar.status_code == 200, character_calendar.text
        assert character_calendar.json()["busy_days"] == 0
        assert character_calendar.json()["free_days"] == 1

        edited = client.patch(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime/{entry_id}",
            headers=admin_headers,
            json={"days": 2, "reason": "Скорректировано"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["entries"][0]["days"] == 2
        assert edited.json()["entries"][0]["reason"] == "Скорректировано"

        deleted = client.delete(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime/{entry_id}",
            headers=admin_headers,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["entries"] == []


def test_player_cannot_manually_manage_personal_hireling_calendar():
    with TestClient(app) as client:
        player_headers, cid = _make_player_with_character(
            client,
            "unit-calendar-player",
        )
        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        updated = client.patch(
            f"/api/admin/characters/{cid}",
            headers=admin_headers,
            json={
                "personal_hireling_enabled": True,
                "personal_hireling_acquired_at": "2025-06-01",
            },
        )
        assert updated.status_code == 200, updated.text

        visible = client.get(
            f"/api/characters/{cid}/calendar/agents/personal_hireling",
            headers=player_headers,
        )
        assert visible.status_code == 200, visible.text
        assert visible.json()["created_at"] == "2025-06-01"
        assert visible.json()["busy_days"] == 0
        assert visible.json()["can_manage"] is False

        forbidden = client.post(
            f"/api/characters/{cid}/calendar/agents/personal_hireling/downtime",
            headers=player_headers,
            json={
                "start_date": "2025-06-01",
                "days": 1,
                "reason": "Игрок пытается занять дни",
            },
        )
        assert forbidden.status_code == 403, forbidden.text


def test_simulacrum_search_uses_own_day_pool(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(
        game_calendar,
        "current_game_date",
        lambda: date(2025, 6, 10),
    )

    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {login(client, 'admin', 'admin123')}"}
        cid = _make_character(
            client,
            headers,
            game_created_at="2025-06-09",
        )["id"]
        client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=headers,
            json={"gold": 10000, "silver": 0, "copper": 0, "reason": "Тест"},
        )
        updated = client.patch(
            f"/api/admin/characters/{cid}",
            headers=headers,
            json={
                "simulacrum_enabled": True,
                "simulacrum_created_at": "2025-06-01",
                "simulacrum_investigation": 20,
            },
        )
        assert updated.status_code == 200, updated.text
        occupied = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=headers,
            json={"start_date": "2025-06-09", "days": 1, "reason": "Занят"},
        )
        assert occupied.status_code == 200, occupied.text
        assert occupied.json()["free_days"] == 0

        search = client.post(
            f"/api/characters/{cid}/shop/search",
            headers=headers,
            json={
                "mode": "buy",
                "item_name": "Scroll",
                "rarity": "Обычный",
                "is_consumable": True,
                "searcher_type": "simulacrum",
            },
        )

        assert search.status_code == 200, search.text
        payload = search.json()
        assert payload["searcher_type"] == "simulacrum"
        assert payload["hireling_cost"] == 0

        character_calendar = client.get(
            f"/api/characters/{cid}/calendar",
            headers=headers,
        )
        assert character_calendar.status_code == 200, character_calendar.text
        assert character_calendar.json()["busy_days"] == 1

        admin_character = client.get(
            f"/api/admin/characters/{cid}",
            headers=headers,
        )
        assert admin_character.status_code == 200, admin_character.text
        assert admin_character.json()["simulacrum_busy_days"] == payload["days"]


# ---------------------------------------------------------------------------
# Calendar permissions and audit log (issue #51)
# ---------------------------------------------------------------------------

def _make_player_with_character(client, username, character_name="Calendar Hero"):
    """Create a player account + one character, returning (headers, character_id)."""
    created = client.post("/api/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": TEST_USER_PASSWORD,
    })
    assert created.status_code == 200, created.text
    token = login(client, username, TEST_USER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    character = client.post("/api/characters", headers=headers, json={
        "name": character_name,
        "class_name": "Wizard",
        "level": 3,
        "route": "Arcane",
    })
    assert character.status_code == 200, character.text
    return headers, character.json()["id"]


def _add_downtime(client, headers, character_id, start="2025-06-01", days=3, reason="Крафт"):
    response = client.post(
        f"/api/characters/{character_id}/calendar/downtime",
        headers=headers,
        json={"start_date": start, "days": days, "reason": reason},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_player_work_reserves_days_credits_wallet_and_records_finance_log(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(game_calendar, "current_game_date", lambda: date(2025, 6, 10))

    with TestClient(app) as client:
        headers, cid = _make_player_with_character(client, "working-player", "Smith")

        worked = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=headers,
            json={
                "start_date": "2025-06-02",
                "days": 3,
                "tools": "Инструменты кузнеца",
                "proficiency_modifier": 3,
            },
        )

        assert worked.status_code == 200, worked.text
        result = worked.json()
        assert result["income_copper"] == 150
        assert result["income"] == {"gold": 1, "silver": 5, "copper": 0}
        assert result["inventory"]["gold"] == 1
        assert result["inventory"]["silver"] == 5
        entry = result["entry"]
        assert entry["source"] == "work"
        assert entry["reason"] == "Работа: Инструменты кузнеца"
        assert entry["tools"] == "Инструменты кузнеца"
        assert entry["proficiency_modifier"] == 3
        assert entry["income_copper"] == 150

        calendar = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert calendar.status_code == 200
        assert calendar.json()["busy_days"] == 3
        assert calendar.json()["entries"][0]["income_copper"] == 150

        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        removable = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry['id']}",
            headers=admin_headers,
        )
        assert removable.status_code == 200, removable.text
        assert removable.json()["busy_days"] == 0
        assert removable.json()["entries"] == []

        inventory = client.get(
            f"/api/characters/{cid}/inventory", headers=headers
        )
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["gold"] == 0
        assert inventory.json()["silver"] == 0
        assert inventory.json()["copper"] == 0

        audit_logs = client.get(
            "/api/admin/calendar-logs",
            headers=admin_headers,
            params={"action": "delete", "character_id": cid},
        )
        assert audit_logs.status_code == 200, audit_logs.text
        assert len(audit_logs.json()) == 1
        assert audit_logs.json()[0]["username"] == "admin"
        assert "150" in audit_logs.json()[0]["details"]

        logs = client.get(
            "/api/admin/shop-logs",
            headers=admin_headers,
            params={"mode": "work", "character_id": cid},
        )
        assert logs.status_code == 200, logs.text
        assert len(logs.json()) == 1
        assert logs.json()[0]["mode"] == "work"
        assert logs.json()[0]["item_name"] == "Инструменты кузнеца"
        assert logs.json()[0]["item_price"] == 1
        assert logs.json()[0]["total_amount"] == 1
        assert logs.json()[0]["total_copper"] == 150


def test_player_cannot_delete_work_and_admin_reverses_exact_income(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(game_calendar, "current_game_date", lambda: date(2025, 6, 10))

    with TestClient(app) as client:
        player_headers, cid = _make_player_with_character(
            client, "work-delete-player", "Working Hero"
        )
        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        funded = client.post(
            f"/api/admin/characters/{cid}/currency/add",
            headers=admin_headers,
            json={"gold": 1, "silver": 2, "copper": 3, "reason": "Starting wallet"},
        )
        assert funded.status_code == 200, funded.text

        worked = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=player_headers,
            json={
                "start_date": "2025-06-02",
                "days": 3,
                "tools": "Инструменты кузнеца",
                "proficiency_modifier": 3,
            },
        )
        assert worked.status_code == 200, worked.text
        entry_id = worked.json()["entry"]["id"]
        assert worked.json()["inventory"]["gold"] == 2
        assert worked.json()["inventory"]["silver"] == 7
        assert worked.json()["inventory"]["copper"] == 3

        forbidden = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=player_headers,
        )
        assert forbidden.status_code == 403, forbidden.text

        deleted = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["busy_days"] == 0

        inventory = client.get(
            f"/api/characters/{cid}/inventory", headers=player_headers
        )
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["gold"] == 1
        assert inventory.json()["silver"] == 2
        assert inventory.json()["copper"] == 3


def test_work_deletion_is_atomic_when_earned_gold_was_spent(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(game_calendar, "current_game_date", lambda: date(2025, 6, 10))

    with TestClient(app) as client:
        player_headers, cid = _make_player_with_character(
            client, "spent-work-player", "Spent Earnings"
        )
        admin_headers = {
            "Authorization": f"Bearer {login(client, 'admin', 'admin123')}"
        }
        worked = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=player_headers,
            json={
                "start_date": "2025-06-02",
                "days": 3,
                "tools": "Инструменты кузнеца",
                "proficiency_modifier": 3,
            },
        )
        assert worked.status_code == 200, worked.text
        entry_id = worked.json()["entry"]["id"]

        spent = client.post(
            f"/api/admin/characters/{cid}/gold",
            headers=admin_headers,
            json={"amount": -1, "reason": "Spent earnings"},
        )
        assert spent.status_code == 200, spent.text

        rejected = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
        )
        assert rejected.status_code == 409, rejected.text
        assert "заработок уже потрачен" in rejected.json()["detail"]

        calendar = client.get(
            f"/api/characters/{cid}/calendar", headers=player_headers
        )
        assert calendar.status_code == 200, calendar.text
        assert calendar.json()["busy_days"] == 3
        assert calendar.json()["entries"][0]["id"] == entry_id

        inventory = client.get(
            f"/api/characters/{cid}/inventory", headers=player_headers
        )
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()["gold"] == 0
        assert inventory.json()["silver"] == 5
        assert inventory.json()["copper"] == 0


def test_work_rejects_overlap_cross_user_access_and_invalid_fields(monkeypatch):
    from app.core import calendar as game_calendar

    monkeypatch.setattr(game_calendar, "current_game_date", lambda: date(2025, 6, 10))

    with TestClient(app) as client:
        owner_headers, cid = _make_player_with_character(client, "work-owner")
        stranger_headers, _ = _make_player_with_character(client, "work-stranger")
        first = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=owner_headers,
            json={
                "start_date": "2025-06-02", "days": 2,
                "tools": "Инструменты плотника", "proficiency_modifier": 4,
            },
        )
        assert first.status_code == 200, first.text

        overlap = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=owner_headers,
            json={
                "start_date": "2025-06-03", "days": 1,
                "tools": "Инструменты алхимика", "proficiency_modifier": 8,
            },
        )
        assert overlap.status_code == 409, overlap.text

        forbidden = client.post(
            f"/api/characters/{cid}/calendar/work",
            headers=stranger_headers,
            json={
                "start_date": "2025-06-05", "days": 1,
                "tools": "Инструменты вора", "proficiency_modifier": 5,
            },
        )
        assert forbidden.status_code == 404, forbidden.text

        for field, value in (("tools", "  "), ("days", 0)):
            payload = {
                "start_date": "2025-06-05", "days": 1,
                "tools": "Инструменты ювелира", "proficiency_modifier": 5,
            }
            payload[field] = value
            invalid = client.post(
                f"/api/characters/{cid}/calendar/work",
                headers=owner_headers,
                json=payload,
            )
            assert invalid.status_code == 422, invalid.text


def test_player_can_add_and_view_but_cannot_edit_or_delete_downtime():
    with TestClient(app) as client:
        headers, cid = _make_player_with_character(client, "calendar-player")

        summary = _add_downtime(client, headers, cid)
        assert summary["busy_days"] == 3
        assert summary["can_manage"] is False
        assert len(summary["entries"]) == 1
        entry_id = summary["entries"][0]["id"]

        # Viewing is allowed and reports the player cannot manage entries.
        view = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert view.status_code == 200, view.text
        assert view.json()["can_manage"] is False

        # Editing is forbidden for players.
        edited = client.patch(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=headers,
            json={"days": 1},
        )
        assert edited.status_code == 403, edited.text

        # Deleting is forbidden for players.
        deleted = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=headers,
        )
        assert deleted.status_code == 403, deleted.text

        # The entry must still be intact after the rejected attempts.
        view = client.get(f"/api/characters/{cid}/calendar", headers=headers)
        assert len(view.json()["entries"]) == 1
        assert view.json()["entries"][0]["days"] == 3


def test_admin_can_add_edit_and_delete_any_character_downtime():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        player_headers, cid = _make_player_with_character(client, "managed-player")

        # Admin adds downtime to another player's character.
        added = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=admin_headers,
            json={"start_date": "2025-06-01", "days": 2, "reason": "Исправление"},
        )
        assert added.status_code == 200, added.text
        assert added.json()["can_manage"] is True
        entry_id = added.json()["entries"][0]["id"]

        # Admin edits the entry.
        edited = client.patch(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
            json={"days": 5, "reason": "Скорректировано"},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["entries"][0]["days"] == 5
        assert edited.json()["entries"][0]["reason"] == "Скорректировано"

        # Admin deletes the entry.
        deleted = client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["entries"] == []

        # The player can still see their (now empty) calendar.
        view = client.get(f"/api/characters/{cid}/calendar", headers=player_headers)
        assert view.status_code == 200, view.text
        assert view.json()["entries"] == []


def test_calendar_admin_actions_are_recorded_in_audit_log():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        player_headers, cid = _make_player_with_character(
            client, "audited-player", character_name="Audited Hero"
        )

        # A player's own add must NOT be audited (only admin corrections are).
        _add_downtime(client, player_headers, cid, days=2)

        logs = client.get("/api/admin/calendar-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        assert logs.json() == []

        # Admin create / update / delete are all audited.
        created = client.post(
            f"/api/characters/{cid}/calendar/downtime",
            headers=admin_headers,
            json={"start_date": "2025-07-01", "days": 1, "reason": "Аудит"},
        )
        entry_id = created.json()["entries"][-1]["id"]
        client.patch(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
            json={"days": 2},
        )
        client.delete(
            f"/api/characters/{cid}/calendar/downtime/{entry_id}",
            headers=admin_headers,
        )

        logs = client.get("/api/admin/calendar-logs", headers=admin_headers)
        assert logs.status_code == 200, logs.text
        actions = [row["action"] for row in logs.json()]
        assert sorted(actions) == ["create", "delete", "update"]
        for row in logs.json():
            assert row["username"] == "admin"
            assert row["character_id"] == cid
            assert row["character_name"] == "Audited Hero"
            assert row["details"]

        # The audit log can be filtered by action and character.
        deletes = client.get(
            "/api/admin/calendar-logs",
            headers=admin_headers,
            params={"action": "delete", "character_id": cid},
        )
        assert deletes.status_code == 200, deletes.text
        assert len(deletes.json()) == 1
        assert deletes.json()[0]["action"] == "delete"


def test_calendar_logs_require_admin():
    with TestClient(app) as client:
        player_headers, _ = _make_player_with_character(client, "nosy-player")
        forbidden = client.get("/api/admin/calendar-logs", headers=player_headers)
        assert forbidden.status_code == 403, forbidden.text
