import os
from datetime import date

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
            json={"amount": 10}
        )
        assert added_xp.status_code == 200, added_xp.text
        reduced_xp = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": -5}
        )
        assert reduced_xp.status_code == 200, reduced_xp.text
        assert reduced_xp.json()["xp"] == 5
        clamped_xp = client.post(
            f"/api/admin/characters/{character_id}/xp",
            headers=headers,
            json={"amount": -99}
        )
        assert clamped_xp.status_code == 200, clamped_xp.text
        assert clamped_xp.json()["xp"] == 0

        added_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": 100}
        )
        assert added_gold.status_code == 200, added_gold.text
        reduced_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": -25}
        )
        assert reduced_gold.status_code == 200, reduced_gold.text
        assert reduced_gold.json()["gold"] == 75
        clamped_gold = client.post(
            f"/api/admin/characters/{character_id}/gold",
            headers=headers,
            json={"amount": -999}
        )
        assert clamped_gold.status_code == 200, clamped_gold.text
        assert clamped_gold.json()["gold"] == 0

        created_user = client.post("/api/users", json={
            "username": "karma-target",
            "email": "karma-target@example.com",
            "password": "secret123"
        })
        assert created_user.status_code == 200, created_user.text
        user_id = created_user.json()["id"]
        added_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": 20}
        )
        assert added_karma.status_code == 200, added_karma.text
        reduced_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": -7}
        )
        assert reduced_karma.status_code == 200, reduced_karma.text
        assert reduced_karma.json()["karma"] == 13
        clamped_karma = client.post(
            f"/api/admin/users/{user_id}/karma",
            headers=headers,
            json={"amount": -99}
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
            "password": "secret123"
        })
        assert created_user.status_code == 200, created_user.text
        player_token = login(client, "editable-player", "secret123")
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
            "password": "secret123"
        })
        assert created_user.status_code == 200, created_user.text
        token = login(client, "collector", "secret123")
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
            json={"gold": 10000, "silver": 0, "copper": 0}
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
            json={"name": "Audit Wand", "rarity": "Обычный", "is_consumable": False}
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
