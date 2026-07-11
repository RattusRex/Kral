import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-project-tests")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from fastapi.testclient import TestClient
from sqlalchemy import Boolean, Column, Integer, MetaData, String, Table

from app.core.auth_abuse import reset_auth_abuse_state
from app.db.database import Base, SessionLocal, engine
from app.core.security import hash_password
from app.main import app, ensure_schema_columns
from app.models.character import Character
from app.models.project import DEFAULT_PROJECT_NAME, Project, ProjectAuditLog
from app.models.recruitment import GameRecruitment, RecruitmentMessage
from app.models.user import User


PASSWORD = "Strong-Project-Pass-47!"


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def login(client, username, password):
    with SessionLocal() as db:
        db.query(User).update({User.email_verified: True})
        db.commit()
    response = client.post("/api/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register(client, username):
    response = client.post("/api/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD,
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def project_headers(headers, project_id):
    return {**headers, "X-Project-ID": str(project_id)}


def test_legacy_admin_is_promoted_before_project_schema_migration():
    Base.metadata.drop_all(bind=engine)
    legacy_metadata = MetaData()
    legacy_users = Table(
        "users",
        legacy_metadata,
        Column("id", Integer, primary_key=True),
        Column("username", String(50), unique=True, nullable=False),
        Column("email", String(255), unique=True, nullable=False),
        Column("hashed_password", String, nullable=False),
        Column("karma", Integer, nullable=False, default=0),
        Column("is_admin", Boolean, nullable=False, default=False),
    )
    legacy_metadata.create_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(legacy_users.insert().values(
            username="admin",
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
            karma=0,
            is_admin=True,
        ))

    Base.metadata.create_all(bind=engine)
    ensure_schema_columns()
    with SessionLocal() as db:
        owner = db.query(User).filter(User.username == "admin").one()
        default_project = db.query(Project).filter(
            Project.name == DEFAULT_PROJECT_NAME
        ).one()

        assert owner.is_owner is True
        assert default_project.owner_id == owner.id

    with TestClient(app) as client:
        owner_headers = login(client, "admin", "admin123")
        me = client.get("/api/me", headers=owner_headers)
        projects = client.get("/api/projects", headers=owner_headers)

        assert me.status_code == 200
        assert me.json()["is_owner"] is True
        assert projects.status_code == 200
        assert [project["name"] for project in projects.json()] == [DEFAULT_PROJECT_NAME]
        assert client.get("/api/admin/users", headers=owner_headers).status_code == 200


def test_project_roles_are_isolated_and_cannot_be_escalated_by_switching_project_id():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        user_id = register(client, "project-manager")
        user = login(client, "project-manager", PASSWORD)

        first = client.post("/api/projects", headers=owner, json={"name": "First", "slug": "first"}).json()
        second = client.post("/api/projects", headers=owner, json={"name": "Second", "slug": "second"}).json()
        promoted = client.put(
            f"/api/projects/{first['id']}/members/{user_id}",
            headers=owner,
            json={"role": "head_admin"},
        )
        assert promoted.status_code == 200, promoted.text

        assert client.get("/api/admin/users", headers=project_headers(user, first["id"])).status_code == 200
        assert client.get("/api/admin/users", headers=project_headers(user, second["id"])).status_code == 403
        assert client.get(f"/api/projects/{second['id']}/settings", headers=user).status_code == 403


def test_role_hierarchy_and_project_owner_peer_protection_are_enforced_server_side():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        first_owner_id = register(client, "first-project-owner")
        second_owner_id = register(client, "second-project-owner")
        target_id = register(client, "target-player")
        project = client.post("/api/projects", headers=owner, json={"name": "Protected", "slug": "protected"}).json()

        for user_id, role in ((first_owner_id, "project_owner"), (second_owner_id, "project_owner")):
            assert client.put(
                f"/api/projects/{project['id']}/members/{user_id}", headers=owner, json={"role": role}
            ).status_code == 200

        first_owner = login(client, "first-project-owner", PASSWORD)
        forbidden_peer_change = client.put(
            f"/api/projects/{project['id']}/members/{second_owner_id}",
            headers=first_owner,
            json={"role": "player"},
        )
        assert forbidden_peer_change.status_code == 403

        forbidden_equal_grant = client.put(
            f"/api/projects/{project['id']}/members/{target_id}",
            headers=first_owner,
            json={"role": "project_owner"},
        )
        assert forbidden_equal_grant.status_code == 403
        assert client.put(
            f"/api/projects/{project['id']}/members/{target_id}",
            headers=first_owner,
            json={"role": "head_admin"},
        ).status_code == 200


def test_technician_can_grant_resources_but_cannot_delete_or_manage_roles_or_settings():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        technician_id = register(client, "technician")
        player_id = register(client, "tech-target")
        project = client.post("/api/projects", headers=owner, json={"name": "Tech", "slug": "tech"}).json()
        for user_id, role in ((technician_id, "technician"), (player_id, "player")):
            assert client.put(
                f"/api/projects/{project['id']}/members/{user_id}", headers=owner, json={"role": role}
            ).status_code == 200
        technician = project_headers(login(client, "technician", PASSWORD), project["id"])
        player = project_headers(login(client, "tech-target", PASSWORD), project["id"])
        character = client.post("/api/characters", headers=player, json={
            "name": "Technician Target", "class_name": "Fighter", "level": 1, "route": "Open Table"
        }).json()

        assert client.post(
            f"/api/admin/characters/{character['id']}/gold",
            headers=technician,
            json={"amount": 3, "reason": "test grant"},
        ).status_code == 200
        assert client.delete(
            f"/api/admin/characters/{character['id']}",
            headers=technician,
            params={"confirmation": "УДАЛИТЬ"},
        ).status_code == 403
        assert client.put(
            f"/api/projects/{project['id']}/members/{player_id}",
            headers=technician,
            json={"role": "admin"},
        ).status_code == 403
        assert client.patch(
            f"/api/projects/{project['id']}/settings",
            headers=technician,
            json={"features": {"shop": False}},
        ).status_code == 403


def test_disabled_project_feature_is_hidden_in_context_and_rejected_by_backend():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        player_id = register(client, "feature-player")
        project = client.post("/api/projects", headers=owner, json={"name": "Features", "slug": "features"}).json()
        client.put(f"/api/projects/{project['id']}/members/{player_id}", headers=owner, json={"role": "player"})
        client.patch(
            f"/api/projects/{project['id']}/settings",
            headers=owner,
            json={"features": {"shop": False}},
        )
        player = project_headers(login(client, "feature-player", PASSWORD), project["id"])
        context = client.get("/api/projects/current", headers=player)
        assert context.status_code == 200
        assert context.json()["features"]["shop"] is False
        assert client.get("/api/shop/magic-items", headers=player).status_code == 403


def test_only_global_owner_can_delete_project_and_other_projects_are_untouched():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        manager_id = register(client, "delete-project-manager")
        first = client.post(
            "/api/projects", headers=owner,
            json={"name": "Disposable", "slug": "disposable"},
        ).json()
        second = client.post(
            "/api/projects", headers=owner,
            json={"name": "Preserved", "slug": "preserved"},
        ).json()
        client.put(
            f"/api/projects/{first['id']}/members/{manager_id}", headers=owner,
            json={"role": "project_owner"},
        )
        manager = login(client, "delete-project-manager", PASSWORD)
        assert client.delete(f"/api/projects/{first['id']}", headers=manager).status_code == 403

        with SessionLocal() as db:
            first_character = Character(
                name="Delete me", class_name="Fighter", route="Test", level=1,
                user_id=manager_id, project_id=first["id"],
            )
            second_character = Character(
                name="Keep me", class_name="Wizard", route="Test", level=1,
                user_id=manager_id, project_id=second["id"],
            )
            db.add_all([first_character, second_character])
            db.flush()
            recruitment = GameRecruitment(
                author_id=manager_id, project_id=first["id"], real_date="2026-08-01",
                game_date="1492-01-01", start_time="18:00", duration="4 hours",
                location="Test", quest="Delete me",
            )
            db.add(recruitment)
            db.flush()
            db.add(RecruitmentMessage(
                recruitment_id=recruitment.id, user_id=manager_id,
                username="delete-project-manager", content="Delete me",
            ))
            db.commit()
            kept_character_id = second_character.id

        deleted = client.delete(f"/api/projects/{first['id']}", headers=owner)
        assert deleted.status_code == 204, deleted.text

        with SessionLocal() as db:
            assert db.get(Project, first["id"]) is None
            assert db.get(Project, second["id"]) is not None
            assert db.get(Character, kept_character_id) is not None
            assert db.query(GameRecruitment).filter_by(project_id=first["id"]).count() == 0
            audit = db.query(ProjectAuditLog).one()
            assert audit.action == "delete"
            assert audit.project_id == first["id"]
            assert audit.project_name == "Disposable"
            assert audit.admin_username == "admin"
