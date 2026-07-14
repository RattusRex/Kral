import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

TEST_USER_PASSWORD = "Strong-Test-Pass-47!"

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.project import DEFAULT_PROJECT_NAME, Project
from app.models.user import User


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client: TestClient, username: str, password: str) -> dict[str, str]:
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    with SessionLocal() as db:
        project_id = db.query(Project.id).filter(Project.name == DEFAULT_PROJECT_NAME).scalar()
    return {**headers, "X-Project-ID": str(project_id)}


def create_player(client: TestClient) -> dict[str, str]:
    response = client.post("/api/users", json={
        "username": "reader",
        "email": "reader@example.com",
        "password": TEST_USER_PASSWORD,
    })
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == "reader").one()
        user.email_verified = True
        db.commit()
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
            "title": "Новые подклассы", "content_type": "Подкласс",
            "karma_cost": 5, "is_banned": False,
            "source_url": "https://example.com/subclasses", "notes": "Одобренный список."
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


def test_admin_can_manage_structured_homebrew_entries_and_players_can_read_them():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        player = create_player(client)
        payload = {
            "title": "Клятва Мора",
            "content_type": "Подкласс",
            "karma_cost": 20,
            "is_banned": False,
            "source_url": "https://example.com/homebrew/oath-of-pestilence",
            "notes": "Разрешено после обсуждения с мастером.",
        }

        created = client.post(
            "/api/content-pages/approved-homebrew", headers=admin, json=payload
        )
        assert created.status_code == 201, created.text
        assert created.json() | payload == created.json()

        listed = client.get(
            "/api/content-pages/approved-homebrew", headers=player
        )
        assert listed.status_code == 200
        assert listed.json()[0]["content_type"] == "Подкласс"
        assert listed.json()[0]["source_url"] == payload["source_url"]

        edited = client.patch(
            f"/api/content-pages/approved-homebrew/{created.json()['id']}",
            headers=admin,
            json={"karma_cost": None, "is_banned": True, "notes": "Запрещено."},
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["karma_cost"] is None
        assert edited.json()["is_banned"] is True
        assert edited.json()["notes"] == "Запрещено."

        unbanned = client.patch(
            f"/api/content-pages/approved-homebrew/{created.json()['id']}",
            headers=admin,
            json={"karma_cost": 35},
        )
        assert unbanned.status_code == 200, unbanned.text
        assert unbanned.json()["karma_cost"] == 35
        assert unbanned.json()["is_banned"] is False

        assert client.patch(
            f"/api/content-pages/approved-homebrew/{created.json()['id']}",
            headers=player,
            json={"notes": "Взлом"},
        ).status_code == 403


def test_structured_homebrew_fields_are_required_and_validated():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        base = {
            "title": "Связующая нить",
            "content_type": "Заклинание",
            "karma_cost": 5,
            "is_banned": False,
            "source_url": "https://example.com/thread",
            "notes": "",
        }

        missing_type = client.post(
            "/api/content-pages/approved-homebrew",
            headers=admin,
            json={key: value for key, value in base.items() if key != "content_type"},
        )
        invalid_url = client.post(
            "/api/content-pages/approved-homebrew",
            headers=admin,
            json={**base, "source_url": "javascript:alert(1)"},
        )
        ambiguous_status = client.post(
            "/api/content-pages/approved-homebrew",
            headers=admin,
            json={**base, "is_banned": True},
        )
        missing_status = client.post(
            "/api/content-pages/approved-homebrew",
            headers=admin,
            json={**base, "karma_cost": None},
        )
        blank_title = client.post(
            "/api/content-pages/approved-homebrew",
            headers=admin,
            json={**base, "title": "   "},
        )

        assert missing_type.status_code == 422
        assert invalid_url.status_code == 422
        assert ambiguous_status.status_code == 422
        assert missing_status.status_code == 422
        assert blank_title.status_code == 422


def test_server_rules_reject_homebrew_only_fields():
    with TestClient(app) as client:
        admin = login(client, "admin", "admin123")
        response = client.post("/api/content-pages/server-rules", headers=admin, json={
            "title": "Правило",
            "content": "Текст правила",
            "content_type": "Класс",
            "karma_cost": 5,
            "is_banned": False,
            "source_url": "https://example.com",
            "notes": "",
        })
        assert response.status_code == 422
