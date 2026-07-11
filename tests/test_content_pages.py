import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

TEST_USER_PASSWORD = "Strong-Test-Pass-47!"

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_player(client: TestClient) -> dict[str, str]:
    response = client.post("/api/users", json={
        "username": "reader",
        "email": "reader@example.com",
        "password": TEST_USER_PASSWORD,
    })
    assert response.status_code == 200, response.text
    return login(client, "reader", TEST_USER_PASSWORD)


def test_content_pages_require_login_and_allow_players_to_read():
    with TestClient(app) as client:
        assert client.get("/api/content-pages/server-rules").status_code == 401
        player = create_player(client)
        response = client.get("/api/content-pages/server-rules", headers=player)
        assert response.status_code == 200
        assert response.json() == []


def test_admin_can_create_edit_reorder_and_delete_content_blocks():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        first = client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "Правила создания персонажа",
            "content": "Создавайте персонажей первого уровня.",
        })
        second = client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "Правила проведения игр",
            "content": "Уважайте других участников.",
        })
        assert first.status_code == second.status_code == 201

        reordered = client.put(
            "/api/content-pages/server-rules/order",
            headers=admin,
            json={"block_ids": [second.json()["id"], first.json()["id"]]},
        )
        assert reordered.status_code == 200, reordered.text
        assert [block["title"] for block in reordered.json()] == [
            "Правила проведения игр", "Правила создания персонажа"
        ]

        edited = client.patch(
            f"/api/content-pages/server-rules/{first.json()['id']}",
            headers=admin,
            json={"title": "Создание персонажа", "content": "Новая редакция."},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["title"] == "Создание персонажа"

        deleted = client.delete(
            f"/api/content-pages/server-rules/{second.json()['id']}", headers=admin
        )
        assert deleted.status_code == 204
        listed = client.get("/api/content-pages/server-rules", headers=admin)
        assert [block["title"] for block in listed.json()] == ["Создание персонажа"]


def test_player_cannot_manage_content_and_pages_are_isolated():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        player = create_player(client)
        created = client.post("/api/content-pages/approved-homebrew", headers=admin, json={
            "title": "Новые подклассы", "content": "Одобренный список."
        })
        assert created.status_code == 201
        assert client.get("/api/content-pages/server-rules", headers=player).json() == []
        assert client.get("/api/content-pages/approved-homebrew", headers=player).json()[0]["title"] == "Новые подклассы"

        assert client.post("/api/content-pages/server-rules", headers=player, json={
            "title": "Нет", "content": "Нет"
        }).status_code == 403
        assert client.patch(
            f"/api/content-pages/approved-homebrew/{created.json()['id']}",
            headers=player,
            json={"title": "Взлом"},
        ).status_code == 403
        assert client.delete(
            f"/api/content-pages/approved-homebrew/{created.json()['id']}", headers=player
        ).status_code == 403


def test_content_blocks_validate_page_slug_and_text_limits():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        assert client.get("/api/content-pages/unknown", headers=admin).status_code == 404
        assert client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "", "content": "text"
        }).status_code == 422
        assert client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "x" * 201, "content": "text"
        }).status_code == 422
        assert client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "title", "content": "x" * 20_001
        }).status_code == 422


def test_reorder_requires_each_page_block_exactly_once():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        blocks = [
            client.post("/api/content-pages/server-rules", headers=admin, json={
                "title": title, "content": "text"
            }).json()
            for title in ("One", "Two")
        ]
        duplicate = client.put("/api/content-pages/server-rules/order", headers=admin, json={
            "block_ids": [blocks[0]["id"], blocks[0]["id"]]
        })
        missing = client.put("/api/content-pages/server-rules/order", headers=admin, json={
            "block_ids": [blocks[0]["id"]]
        })
        assert duplicate.status_code == 400
        assert missing.status_code == 400
