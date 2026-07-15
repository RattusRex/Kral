import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.project import ProjectMembership
from app.models.user import User


PASSWORD = "Strong-About-Page-Pass-47!"


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user(username: str, *, owner: bool = False) -> User:
    with SessionLocal() as db:
        user = User(
            username=username,
            email=f"{username}@example.com",
            hashed_password=hash_password(PASSWORD),
            email_verified=True,
            role="owner" if owner else "player",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/login", data={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def selected(headers: dict[str, str], project_id: int) -> dict[str, str]:
    return {**headers, "X-Project-ID": str(project_id)}


def assign_role(project_id: int, user_id: int, role: str) -> None:
    with SessionLocal() as db:
        db.add(ProjectMembership(project_id=project_id, user_id=user_id, role=role))
        db.commit()


def test_about_page_is_project_scoped_and_preserves_markdown():
    owner = create_user("about-owner", owner=True)
    with TestClient(app) as client:
        owner_headers = login(client, owner.username)
        first = client.post(
            "/api/projects", headers=owner_headers, json={"name": "First World"}
        ).json()
        second = client.post(
            "/api/projects", headers=owner_headers, json={"name": "Second World"}
        ).json()

        first_headers = selected(owner_headers, first["id"])
        second_headers = selected(owner_headers, second["id"])
        first_default = client.get("/api/projects/about", headers=first_headers)
        assert first_default.status_code == 200, first_default.text
        assert first_default.json() == {
            "title": "Добро пожаловать в First World",
            "description": "",
        }

        markdown = "**Жирный текст**\n\n- Первый пункт\n- [Ссылка](https://example.com)"
        updated = client.put(
            "/api/projects/about",
            headers=first_headers,
            json={"title": "Первый мир", "description": markdown},
        )
        assert updated.status_code == 200, updated.text
        assert updated.json() == {"title": "Первый мир", "description": markdown}

        assert client.get("/api/projects/about", headers=first_headers).json() == updated.json()
        assert client.get("/api/projects/about", headers=second_headers).json() == {
            "title": "Добро пожаловать в Second World",
            "description": "",
        }


def test_only_technician_and_higher_roles_can_edit_about_page():
    owner = create_user("role-owner", owner=True)
    users = {role: create_user(f"about-{role}") for role in (
        "player", "technician", "admin", "head_admin", "project_owner"
    )}
    with TestClient(app) as client:
        owner_headers = login(client, owner.username)
        project = client.post(
            "/api/projects", headers=owner_headers, json={"name": "Role World"}
        ).json()
        for role, user in users.items():
            assign_role(project["id"], user.id, role)

        for role, user in users.items():
            headers = selected(login(client, user.username), project["id"])
            assert client.get("/api/projects/about", headers=headers).status_code == 200
            response = client.put(
                "/api/projects/about",
                headers=headers,
                json={"title": f"Title by {role}", "description": "Description"},
            )
            assert response.status_code == (403 if role == "player" else 200), response.text

        response = client.put(
            "/api/projects/about",
            headers=selected(owner_headers, project["id"]),
            json={"title": "Title by owner", "description": "Description"},
        )
        assert response.status_code == 200, response.text


def test_about_page_validates_title_and_requires_selected_project():
    owner = create_user("validation-owner", owner=True)
    with TestClient(app) as client:
        owner_headers = login(client, owner.username)
        project = client.post(
            "/api/projects", headers=owner_headers, json={"name": "Validation World"}
        ).json()
        headers = selected(owner_headers, project["id"])

        assert client.get("/api/projects/about", headers=owner_headers).status_code == 400
        assert client.put(
            "/api/projects/about",
            headers=headers,
            json={"title": "   ", "description": "Description"},
        ).status_code == 422
