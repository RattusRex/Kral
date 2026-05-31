import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient

from app.db.database import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_seed_and_username_login():
    with TestClient(app) as client:
        token = login(client, "admin", "admin123")
        response = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        assert response.json()["is_admin"] is True


def test_create_user_then_login_with_username_and_email():
    with TestClient(app) as client:
        created = client.post("/api/users", json={
            "username": "player-one",
            "email": "player-one@example.com",
            "password": "secret123"
        })
        assert created.status_code == 200, created.text
        assert created.json()["username"] == "player-one"

        username_token = login(client, "player-one", "secret123")
        username_response = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {username_token}"}
        )
        assert username_response.status_code == 200
        assert username_response.json()["email"] == "player-one@example.com"

        email_token = login(client, "player-one@example.com", "secret123")
        email_response = client.get(
            "/api/me",
            headers={"Authorization": f"Bearer {email_token}"}
        )
        assert email_response.status_code == 200
        assert email_response.json()["username"] == "player-one"


def test_duplicate_user_returns_conflict():
    with TestClient(app) as client:
        payload = {
            "username": "player-two",
            "email": "player-two@example.com",
            "password": "secret123"
        }
        assert client.post("/api/users", json=payload).status_code == 200

        duplicate = client.post("/api/users", json=payload)

        assert duplicate.status_code == 409
        assert duplicate.json()["detail"] == "Username or email already exists"


def test_character_xp_rolls_over_remaining_xp():
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

        response = client.patch(f"/api/characters/{character_id}", headers=headers, json={"xp": 6})
        assert response.status_code == 200, response.text
        assert response.json()["level"] == 4
        assert response.json()["xp"] == 2


def test_shop_buy_uses_api_prefix_and_updates_inventory():
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
            json={"gold": 1000, "silver": 0, "copper": 0}
        )

        response = client.post(f"/api/characters/{character_id}/shop/buy", headers=headers, json={
            "item_name": "Healing Potion",
            "rarity": "Обычный",
            "is_consumable": True,
            "searcher_type": "character"
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["inventory"]["items"][0]["name"] == "Healing Potion"
