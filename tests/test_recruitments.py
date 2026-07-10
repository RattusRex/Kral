import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.character import Character
from app.models.recruitment import GameApplication


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client, username, password="password123"):
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register(client, username):
    response = client.post("/api/users", json={
        "username": username, "email": f"{username}@example.com", "password": "password123"
    })
    assert response.status_code == 200, response.text
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
        assert payload["messages"][0]["content"] == 'Игрок #alice записался на персонаже "Алиса".\n\nКласс: Волшебник\nУровень: 5'

        duplicate = client.post(f"/api/game-recruitments/{recruitment_id}/applications", headers=alice, json={"character_id": alice_character})
        assert duplicate.status_code == 409
        assert len(client.get("/api/game-recruitments", headers=alice).json()[0]["messages"]) == 1


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
        assert payload["messages"][-1]["content"] == 'Игроки выбраны:\n\n- #alice — "Лира", класс: Волшебник, уровень: 5'

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
