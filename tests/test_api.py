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
            json={"gold": 10000, "silver": 0, "copper": 0}
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
            json={"gold": 1000, "silver": 0, "copper": 0}
        )
        granted = client.post(
            f"/api/admin/characters/{character_id}/item",
            headers=headers,
            json={"name": "Old Wand", "rarity": "Обычный", "is_consumable": False}
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


def test_admin_can_change_karma_and_view_all_characters_with_owner():
    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        created_user = client.post("/api/users", json={
            "username": "player-three",
            "email": "player-three@example.com",
            "password": "secret123"
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        player_token = login(client, "player-three", "secret123")
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
            json={"amount": 3}
        )
        assert added.status_code == 200, added.text
        assert added.json()["karma"] == 3
        subtracted = client.post(
            f"/api/admin/users/{user_id}/karma/subtract",
            headers=admin_headers,
            json={"amount": 1}
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
