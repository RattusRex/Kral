import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

TEST_USER_PASSWORD = "Strong-Test-Pass-47!"

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.character import Character
from app.models.project import ProjectMembership
from app.models.recruitment import GameApplication, GameRecruitment, RecruitmentMessage
from app.models.user import User


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client, username, password=TEST_USER_PASSWORD):
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register(client, username):
    response = client.post("/api/users", json={
        "username": username, "email": f"{username}@example.com", "password": TEST_USER_PASSWORD
    })
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        user.email_verified = True
        db.commit()
    return login(client, username)


def create_character(client, headers, name):
    response = client.post("/api/characters", headers=headers, json={
        "name": name, "class_name": "Волшебник", "level": 5, "route": "Путь"
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def recruitment_payload():
    return {
        "real_date": "2026-07-20", "game_date": "2026-06-15",
        "start_time": "18:00", "duration": "4 часа", "location": "Эсмелтаран",
        "quest": "Исследовать крипту", "notes": "Уровни 3–6",
    }


def test_only_admins_create_recruitments_and_all_authenticated_users_can_list_them():
    with TestClient(app) as client:
        player = register(client, "player")
        assert client.post("/api/game-recruitments", headers=player, json=recruitment_payload()).status_code == 403

        admin = login(client, "admin", "admin123")
        created = client.post("/api/game-recruitments", headers=admin, json=recruitment_payload())
        assert created.status_code == 201, created.text
        assert created.json()["author_username"] == "admin"
        assert created.json()["can_manage"] is True

        listed = client.get("/api/game-recruitments", headers=player)
        assert listed.status_code == 200
        assert listed.json()[0]["can_manage"] is False
        assert listed.json()[0]["application_status"] == "not_applied"


def test_application_enforces_ownership_prevents_duplicates_and_persists_chat_message():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        recruitment_id = client.post("/api/game-recruitments", headers=admin, json=recruitment_payload()).json()["id"]
        alice = register(client, "alice")
        bob = register(client, "bob")
        alice_character = create_character(client, alice, "Алиса")
        bob_character = create_character(client, bob, "Боб")

        forbidden = client.post(f"/api/game-recruitments/{recruitment_id}/applications", headers=alice, json={"character_id": bob_character})
        assert forbidden.status_code == 403

        applied = client.post(f"/api/game-recruitments/{recruitment_id}/applications", headers=alice, json={"character_id": alice_character})
        assert applied.status_code == 201, applied.text
        payload = applied.json()
        assert payload["application_status"] == "applied"
        assert payload["applications"][0]["username"] == "alice"
        messages = client.get(
            f"/api/game-recruitments/{recruitment_id}/messages", headers=alice
        ).json()
        assert messages[0]["content"] == 'Игрок #alice записался на персонаже "Алиса".\n\nКласс: Волшебник\nУровень: 5'

        duplicate = client.post(f"/api/game-recruitments/{recruitment_id}/applications", headers=alice, json={"character_id": alice_character})
        assert duplicate.status_code == 409
        messages = client.get(
            f"/api/game-recruitments/{recruitment_id}/messages", headers=alice
        ).json()
        assert len(messages) == 1


def test_every_project_role_can_apply_with_an_owned_character():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        project_id = client.get("/api/projects/current", headers=owner).json()["id"]
        recruitment_id = client.post(
            "/api/game-recruitments", headers=owner, json=recruitment_payload()
        ).json()["id"]
        headers_by_role = {"owner": owner}
        for role in ("project_owner", "head_admin", "admin", "technician", "player"):
            username = f"apply-{role}"
            headers_by_role[role] = register(client, username)
            with SessionLocal() as db:
                user = db.query(User).filter(User.username == username).one()
                membership = db.query(ProjectMembership).filter_by(
                    project_id=project_id, user_id=user.id
                ).one()
                membership.role = role
                db.commit()

        for role, headers in headers_by_role.items():
            character_id = create_character(client, headers, f"Персонаж {role}")
            response = client.post(
                f"/api/game-recruitments/{recruitment_id}/applications",
                headers=headers,
                json={"character_id": character_id},
            )
            assert response.status_code == 201, f"{role}: {response.text}"


def test_character_picker_and_application_are_isolated_to_selected_project():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        default_project = client.get("/api/projects/current", headers=owner).json()
        other_project = client.post(
            "/api/projects",
            headers=owner,
            json={"name": "Другой проект", "slug": "other-project"},
        ).json()
        default_headers = {**owner, "X-Project-ID": str(default_project["id"])}
        other_headers = {**owner, "X-Project-ID": str(other_project["id"])}
        default_character = create_character(client, default_headers, "Текущий")
        other_character = create_character(client, other_headers, "Чужой проект")
        recruitment_id = client.post(
            "/api/game-recruitments", headers=default_headers, json=recruitment_payload()
        ).json()["id"]

        listed = client.get("/api/characters", headers=default_headers)
        assert listed.status_code == 200, listed.text
        assert [character["id"] for character in listed.json()] == [default_character]
        forbidden = client.post(
            f"/api/game-recruitments/{recruitment_id}/applications",
            headers=default_headers,
            json={"character_id": other_character},
        )
        assert forbidden.status_code == 403


def test_only_author_selects_applicants_and_selection_is_announced():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        recruitment_id = client.post("/api/game-recruitments", headers=admin, json=recruitment_payload()).json()["id"]
        alice = register(client, "alice")
        character_id = create_character(client, alice, "Лира")
        application = client.post(f"/api/game-recruitments/{recruitment_id}/applications", headers=alice, json={"character_id": character_id}).json()["applications"][0]

        assert client.post(f"/api/game-recruitments/{recruitment_id}/participants", headers=alice, json={"application_ids": [application["id"]]}).status_code == 403
        selected = client.post(f"/api/game-recruitments/{recruitment_id}/participants", headers=admin, json={"application_ids": [application["id"]]})
        assert selected.status_code == 200, selected.text
        payload = selected.json()
        assert payload["applications"][0]["status"] == "selected"
        messages = client.get(
            f"/api/game-recruitments/{recruitment_id}/messages", headers=admin
        ).json()
        assert messages[-1]["content"] == 'Игроки выбраны:\n\n- #alice — "Лира", класс: Волшебник, уровень: 5'

        mine = client.get("/api/game-recruitments", headers=alice).json()[0]
        assert mine["application_status"] == "selected"


def test_deleting_character_removes_its_historical_application():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        recruitment_id = client.post("/api/game-recruitments", headers=admin, json=recruitment_payload()).json()["id"]
        character_id = create_character(client, admin, "Удаляемый")
        applied = client.post(
            f"/api/game-recruitments/{recruitment_id}/applications",
            headers=admin,
            json={"character_id": character_id},
        )
        assert applied.status_code == 201

        db = SessionLocal()
        try:
            db.delete(db.get(Character, character_id))
            db.commit()
            assert db.query(GameApplication).count() == 0
        finally:
            db.close()


def promote(client, owner_headers, username, role):
    users = client.get("/api/admin/users", headers=owner_headers).json()
    user_id = next(user["id"] for user in users if user["username"] == username)
    response = client.post(
        f"/api/admin/users/{user_id}/role",
        headers=owner_headers,
        json={"role": role},
    )
    assert response.status_code == 200, response.text


def test_author_and_every_administrative_role_can_delete_recruitments():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        headers_by_role = {"owner": owner}
        for role in ("admin", "head_admin"):
            headers_by_role[role] = register(client, f"delete-{role}")
            promote(client, owner, f"delete-{role}", role)

        for deleting_role, deleting_headers in headers_by_role.items():
            author = register(client, f"author-{deleting_role}")
            promote(client, owner, f"author-{deleting_role}", "admin")
            recruitment_id = client.post(
                "/api/game-recruitments", headers=author, json=recruitment_payload()
            ).json()["id"]

            deleted = client.delete(
                f"/api/game-recruitments/{recruitment_id}", headers=deleting_headers
            )
            assert deleted.status_code == 204, deleted.text

        author_recruitment = client.post(
            "/api/game-recruitments", headers=headers_by_role["admin"], json=recruitment_payload()
        ).json()["id"]
        assert client.delete(
            f"/api/game-recruitments/{author_recruitment}", headers=headers_by_role["admin"]
        ).status_code == 204


def test_delete_is_forbidden_to_players_and_cascades_applications_and_messages():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        recruitment_id = client.post(
            "/api/game-recruitments", headers=owner, json=recruitment_payload()
        ).json()["id"]
        player = register(client, "delete-player")
        character_id = create_character(client, player, "Участник")
        assert client.post(
            f"/api/game-recruitments/{recruitment_id}/applications",
            headers=player,
            json={"character_id": character_id},
        ).status_code == 201

        forbidden = client.delete(
            f"/api/game-recruitments/{recruitment_id}", headers=player
        )
        assert forbidden.status_code == 403
        assert client.delete(
            f"/api/game-recruitments/{recruitment_id}", headers=owner
        ).status_code == 204

        db = SessionLocal()
        try:
            assert db.query(GameRecruitment).count() == 0
            assert db.query(GameApplication).count() == 0
            assert db.query(RecruitmentMessage).count() == 0
        finally:
            db.close()


def test_status_defaults_to_upcoming_and_only_author_or_admin_can_complete_it():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        author = register(client, "status-author")
        promote(client, owner, "status-author", "admin")
        recruitment_id = client.post(
            "/api/game-recruitments", headers=author, json=recruitment_payload()
        ).json()["id"]
        player = register(client, "status-player")

        listed = client.get("/api/game-recruitments", headers=player).json()[0]
        assert listed["status"] == "upcoming"
        assert listed["can_manage"] is False
        assert client.patch(
            f"/api/game-recruitments/{recruitment_id}/status",
            headers=player,
            json={"status": "completed"},
        ).status_code == 403

        completed = client.patch(
            f"/api/game-recruitments/{recruitment_id}/status",
            headers=author,
            json={"status": "completed"},
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["status"] == "completed"
        character_id = create_character(client, player, "Опоздавший")
        closed_application = client.post(
            f"/api/game-recruitments/{recruitment_id}/applications",
            headers=player,
            json={"character_id": character_id},
        )
        assert closed_application.status_code == 409
        assert client.patch(
            f"/api/game-recruitments/{recruitment_id}/status",
            headers=owner,
            json={"status": "upcoming"},
        ).status_code == 200


def test_paginated_list_sorts_upcoming_before_completed_and_reports_totals():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        ids = []
        for index, real_date in enumerate(("2026-07-22", "2026-07-20", "2026-07-21")):
            payload = {**recruitment_payload(), "real_date": real_date, "quest": f"Игра {index}"}
            ids.append(client.post(
                "/api/game-recruitments", headers=owner, json=payload
            ).json()["id"])
        assert client.patch(
            f"/api/game-recruitments/{ids[1]}/status",
            headers=owner,
            json={"status": "completed"},
        ).status_code == 200

        first = client.get(
            "/api/game-recruitments", headers=owner, params={"page": 1, "page_size": 2}
        )
        assert first.status_code == 200, first.text
        assert [row["quest"] for row in first.json()["items"]] == ["Игра 2", "Игра 0"]
        assert first.json() | {"items": []} == {
            "items": [], "page": 1, "page_size": 2, "total": 3, "pages": 2
        }

        second = client.get(
            "/api/game-recruitments", headers=owner, params={"page": 2, "page_size": 2}
        )
        assert [row["quest"] for row in second.json()["items"]] == ["Игра 1"]
        assert second.json()["items"][0]["status"] == "completed"
        assert client.get(
            "/api/game-recruitments", headers=owner, params={"page_size": 101}
        ).status_code == 422


def test_recruitment_chat_supports_cursor_history_and_message_permissions():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        recruitment_id = client.post(
            "/api/game-recruitments", headers=owner, json=recruitment_payload()
        ).json()["id"]
        alice = register(client, "chat-alice")
        bob = register(client, "chat-bob")

        created_ids = []
        for index in range(4):
            response = client.post(
                f"/api/game-recruitments/{recruitment_id}/messages",
                headers=alice,
                json={"content": f"Сообщение {index}"},
            )
            assert response.status_code == 201, response.text
            assert response.json()["username"] == "chat-alice"
            assert response.json()["is_system"] is False
            created_ids.append(response.json()["id"])

        latest = client.get(
            f"/api/game-recruitments/{recruitment_id}/messages",
            headers=bob,
            params={"limit": 2},
        )
        assert latest.status_code == 200, latest.text
        assert [row["id"] for row in latest.json()] == created_ids[-2:]
        older = client.get(
            f"/api/game-recruitments/{recruitment_id}/messages",
            headers=bob,
            params={"before_id": created_ids[-2], "limit": 2},
        )
        assert [row["id"] for row in older.json()] == created_ids[:2]

        assert client.delete(
            f"/api/game-recruitments/{recruitment_id}/messages/{created_ids[0]}",
            headers=bob,
        ).status_code == 403
        assert client.delete(
            f"/api/game-recruitments/{recruitment_id}/messages/{created_ids[0]}",
            headers=alice,
        ).status_code == 204
        assert client.delete(
            f"/api/game-recruitments/{recruitment_id}/messages/{created_ids[1]}",
            headers=owner,
        ).status_code == 204
