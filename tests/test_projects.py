import os
from datetime import date, time

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
from app.models.project import DEFAULT_PROJECT_NAME, Project, ProjectAuditLog, ProjectMembership
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
        assert client.get(
            "/api/admin/users",
            headers=project_headers(owner_headers, projects.json()[0]["id"]),
        ).status_code == 200


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


def test_owner_can_create_project_from_name_only_and_list_its_ecosystem():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")

        created = client.post(
            "/api/projects",
            headers=owner,
            json={"name": "Новая кампания: Север!"},
        )

        assert created.status_code == 200, created.text
        project = created.json()
        assert project["name"] == "Новая кампания: Север!"
        assert project["slug"]
        assert all(character.isascii() and (character.isalnum() or character == "-") for character in project["slug"])
        assert project["features"]
        assert project["role"] == "owner"
        assert project["id"] in {item["id"] for item in client.get("/api/projects", headers=owner).json()}

        with SessionLocal() as db:
            owner_id = db.query(User).filter_by(username="admin").one().id
            membership = db.query(ProjectMembership).filter_by(
                project_id=project["id"], user_id=owner_id
            ).one()
            assert membership.role == "project_owner"


def test_duplicate_project_name_returns_conflict_instead_of_database_error():
    with TestClient(app, raise_server_exceptions=False) as client:
        owner = login(client, "admin", "admin123")
        first = client.post(
            "/api/projects", headers=owner, json={"name": "Duplicate project"}
        )
        duplicate = client.post(
            "/api/projects", headers=owner, json={"name": "Duplicate project"}
        )

        assert first.status_code == 200, first.text
        assert duplicate.status_code == 409, duplicate.text
        assert duplicate.json()["detail"] == "Project name already exists"


def test_automatic_project_slugs_do_not_limit_project_count():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")

        first = client.post(
            "/api/projects", headers=owner, json={"name": "Campaign!"}
        )
        second = client.post(
            "/api/projects", headers=owner, json={"name": "Campaign?"}
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.json()["slug"] == "campaign"
        assert second.json()["slug"] == "campaign-2"


def test_global_admin_role_does_not_leak_into_player_project_membership():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        user_id = register(client, "global-admin-project-player")
        with SessionLocal() as db:
            db.get(User, user_id).role = "admin"
            db.commit()
        project = client.post(
            "/api/projects", headers=owner,
            json={"name": "Role Isolation", "slug": "role-isolation"},
        ).json()
        assert client.put(
            f"/api/projects/{project['id']}/members/{user_id}",
            headers=owner, json={"role": "player"},
        ).status_code == 200

        headers = project_headers(login(client, "global-admin-project-player", PASSWORD), project["id"])
        assert client.get("/api/admin/characters", headers=headers).status_code == 403


def test_gameplay_requires_explicit_project_selection():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")

        assert client.get("/api/projects", headers=owner).status_code == 200
        assert client.get("/api/me", headers=owner).status_code == 200
        for path in (
            "/api/projects/current",
            "/api/characters",
            "/api/chat/messages",
            "/api/leaderboard",
            "/api/content-pages/server-rules",
            "/api/karma-shop/purchases",
        ):
            response = client.get(path, headers=owner)
            assert response.status_code == 400, (path, response.text)
            assert response.json()["detail"] == "X-Project-ID header is required"


def test_chat_and_karma_are_isolated_between_selected_projects():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        player_id = register(client, "isolated-player")
        first = client.post(
            "/api/projects", headers=owner, json={"name": "Isolated First", "slug": "isolated-first"}
        ).json()
        second = client.post(
            "/api/projects", headers=owner, json={"name": "Isolated Second", "slug": "isolated-second"}
        ).json()
        for project in (first, second):
            assert client.put(
                f"/api/projects/{project['id']}/members/{player_id}",
                headers=owner,
                json={"role": "player"},
            ).status_code == 200

        player = login(client, "isolated-player", PASSWORD)
        first_headers = project_headers(player, first["id"])
        second_headers = project_headers(player, second["id"])
        first_character = client.post("/api/characters", headers=first_headers, json={
            "name": "First Character", "class_name": "Fighter", "level": 1, "route": "First"
        })
        assert first_character.status_code == 200, first_character.text
        assert [row["name"] for row in client.get("/api/characters", headers=first_headers).json()] == [
            "First Character"
        ]
        assert client.get("/api/characters", headers=second_headers).json() == []
        assert client.patch(
            f"/api/characters/{first_character.json()['id']}",
            headers=second_headers,
            json={"name": "Cross-project update"},
        ).status_code == 404

        assert client.post(
            "/api/chat/messages", headers=first_headers, json={"content": "First only"}
        ).status_code == 200
        assert [row["content"] for row in client.get(
            "/api/chat/messages", headers=first_headers
        ).json()] == ["First only"]
        assert client.get("/api/chat/messages", headers=second_headers).json() == []

        granted = client.post(
            f"/api/admin/users/{player_id}/karma/add",
            headers=project_headers(owner, first["id"]),
            json={"amount": 7, "reason": "project-local grant"},
        )
        assert granted.status_code == 200, granted.text
        assert granted.json()["karma"] == 7
        assert client.get("/api/projects/current", headers=first_headers).json()["karma"] == 7
        assert client.get("/api/projects/current", headers=second_headers).json()["karma"] == 0
        purchase = client.post(
            "/api/karma-shop/purchases",
            headers=first_headers,
            json={"purchase_type": "opener", "name": "First opener", "cost": 3},
        )
        assert purchase.status_code == 200, purchase.text
        assert purchase.json()["remaining_karma"] == 4
        assert [row["name"] for row in client.get(
            "/api/karma-shop/purchases", headers=first_headers
        ).json()] == ["First opener"]
        assert client.get("/api/karma-shop/purchases", headers=second_headers).json() == []
        assert client.get("/api/projects/current", headers=second_headers).json()["karma"] == 0


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


def test_project_owner_and_head_admin_can_assign_technician():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        project_owner_id = register(client, "technician-project-owner")
        head_admin_id = register(client, "technician-head-admin")
        first_target_id = register(client, "first-technician-target")
        second_target_id = register(client, "second-technician-target")
        project = client.post(
            "/api/projects", headers=owner, json={"name": "Technicians", "slug": "technicians"}
        ).json()
        for user_id, role in (
            (project_owner_id, "project_owner"),
            (head_admin_id, "head_admin"),
        ):
            assert client.put(
                f"/api/projects/{project['id']}/members/{user_id}",
                headers=owner,
                json={"role": role},
            ).status_code == 200

        project_owner = project_headers(
            login(client, "technician-project-owner", PASSWORD), project["id"]
        )
        head_admin = project_headers(
            login(client, "technician-head-admin", PASSWORD), project["id"]
        )
        for actor, target_id in (
            (project_owner, first_target_id),
            (head_admin, second_target_id),
        ):
            assigned = client.put(
                f"/api/projects/{project['id']}/members/{target_id}",
                headers=actor,
                json={"role": "technician"},
            )
            assert assigned.status_code == 200, assigned.text
            assert assigned.json()["role"] == "technician"


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


def test_additional_project_features_are_independent_and_backend_enforced():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        player_id = register(client, "optional-feature-player")
        first = client.post(
            "/api/projects", headers=owner,
            json={"name": "Optional Features", "slug": "optional-features"},
        ).json()
        second = client.post(
            "/api/projects", headers=owner,
            json={"name": "Enabled Features", "slug": "enabled-features"},
        ).json()
        for project in (first, second):
            assert client.put(
                f"/api/projects/{project['id']}/members/{player_id}",
                headers=owner,
                json={"role": "player"},
            ).status_code == 200

        disabled = {
            "leaderboard": False,
            "karma": False,
            "karma_logs": False,
            "character_transfers": False,
            "market_logs": False,
            "logs": False,
        }
        updated = client.patch(
            f"/api/projects/{first['id']}/settings",
            headers=owner,
            json={"features": disabled},
        )
        assert updated.status_code == 200, updated.text
        assert all(updated.json()["features"][feature] is False for feature in disabled)

        player = login(client, "optional-feature-player", PASSWORD)
        first_headers = project_headers(player, first["id"])
        second_headers = project_headers(player, second["id"])
        assert client.get("/api/leaderboard", headers=first_headers).status_code == 403
        assert client.get("/api/leaderboard", headers=second_headers).status_code == 200
        assert client.get("/api/characters/transfer-targets", headers=first_headers).status_code == 403
        assert client.get("/api/characters/transfer-targets", headers=second_headers).status_code == 200
        assert client.get("/api/karma-shop/purchases", headers=first_headers).status_code == 403

        assert client.put(
            f"/api/projects/{first['id']}/members/{player_id}",
            headers=owner,
            json={"role": "technician"},
        ).status_code == 200
        admin_headers = project_headers(player, first["id"])
        assert client.get("/api/admin/shop-logs", headers=admin_headers).status_code == 403
        assert client.get("/api/admin/market-sales", headers=admin_headers).status_code == 403
        assert client.get("/api/admin/karma-shop-logs", headers=admin_headers).status_code == 403
        karma_change = client.post(
            f"/api/admin/users/{player_id}/karma",
            headers=admin_headers,
            json={"amount": 1, "reason": "must remain disabled"},
        )
        assert karma_change.status_code == 403

        first_context = client.get("/api/projects/current", headers=first_headers).json()
        second_context = client.get("/api/projects/current", headers=second_headers).json()
        assert all(first_context["features"][feature] is False for feature in disabled)
        assert all(second_context["features"][feature] is True for feature in disabled)


def test_only_owner_project_owner_and_head_admin_can_change_feature_settings():
    with TestClient(app) as client:
        owner = login(client, "admin", "admin123")
        project = client.post(
            "/api/projects", headers=owner,
            json={"name": "Feature Roles", "slug": "feature-roles"},
        ).json()
        roles = ("project_owner", "head_admin", "admin", "technician", "player")
        headers_by_role = {}
        for role in roles:
            username = f"feature-{role.replace('_', '-')}"
            user_id = register(client, username)
            assert client.put(
                f"/api/projects/{project['id']}/members/{user_id}",
                headers=owner,
                json={"role": role},
            ).status_code == 200
            headers_by_role[role] = project_headers(login(client, username, PASSWORD), project["id"])

        for role in ("project_owner", "head_admin"):
            response = client.patch(
                f"/api/projects/{project['id']}/settings",
                headers=headers_by_role[role],
                json={"features": {"leaderboard": False}},
            )
            assert response.status_code == 200, (role, response.text)
        for role in ("admin", "technician", "player"):
            response = client.patch(
                f"/api/projects/{project['id']}/settings",
                headers=headers_by_role[role],
                json={"features": {"leaderboard": True}},
            )
            assert response.status_code == 403, (role, response.text)


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
                author_id=manager_id, project_id=first["id"], real_date=date(2026, 8, 1),
                game_date=date(1492, 1, 1), start_time=time(18, 0), duration="4 hours",
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
