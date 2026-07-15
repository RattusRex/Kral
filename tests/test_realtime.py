import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-realtime-tests")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")

from fastapi.testclient import TestClient

from app.core.auth_abuse import reset_auth_abuse_state
from app.core.realtime import infer_realtime_events
from app.db.database import Base, SessionLocal, engine
from app.main import app
from app.models.user import User


PASSWORD = "Strong-Realtime-Pass-47!"


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    reset_auth_abuse_state()


def register_and_login(client: TestClient, username: str) -> tuple[str, dict[str, str]]:
    response = client.post("/api/users", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": PASSWORD,
    })
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username).one()
        user.email_verified = True
        db.commit()
    login = client.post("/api/login", data={"username": username, "password": PASSWORD})
    token = login.json()["access_token"]
    projects = client.get(
        "/api/projects", headers={"Authorization": f"Bearer {token}"}
    ).json()
    project_id = projects[0]["id"]
    return token, {"Authorization": f"Bearer {token}", "X-Project-ID": str(project_id)}


def test_websocket_rejects_missing_and_invalid_authentication():
    with TestClient(app) as client:
        with client.websocket_connect("/api/ws?project_id=1") as websocket:
            assert websocket.receive_json() == {
                "type": "connection.error",
                "detail": "Authentication required",
            }

        with client.websocket_connect("/api/ws?token=invalid&project_id=1") as websocket:
            assert websocket.receive_json() == {
                "type": "connection.error",
                "detail": "Invalid token",
            }


def test_successful_mutation_paths_map_to_centralized_event_topics():
    assert infer_realtime_events("POST", "/api/chat/messages") >= {"chat.changed", "logs.changed"}
    assert infer_realtime_events("POST", "/api/game-recruitments/1/applications") >= {"recruitment.changed"}
    assert infer_realtime_events("PATCH", "/api/admin/characters/4") >= {"character.changed"}
    assert infer_realtime_events("POST", "/api/characters/4/inventory/items") >= {"market.changed"}
    assert infer_realtime_events("GET", "/api/chat/messages") == set()
    assert infer_realtime_events("POST", "/api/login") == set()


def test_chat_events_reach_all_project_connections_and_not_other_projects():
    with TestClient(app) as client:
        token, headers = register_and_login(client, "realtime-player")
        project_id = int(headers["X-Project-ID"])
        owner_login = client.post(
            "/api/login", data={"username": "admin", "password": "admin123"}
        ).json()
        other_project = client.post(
            "/api/projects",
            headers={"Authorization": f"Bearer {owner_login['access_token']}"},
            json={"name": "Other realtime project"},
        ).json()

        with (
            client.websocket_connect(f"/api/ws?token={token}&project_id={project_id}") as first_tab,
            client.websocket_connect(f"/api/ws?token={token}&project_id={project_id}") as second_tab,
            client.websocket_connect(
                f"/api/ws?token={owner_login['access_token']}&project_id={other_project['id']}"
            ) as other_project_socket,
        ):
            assert first_tab.receive_json()["type"] == "connection.ready"
            assert second_tab.receive_json()["type"] == "connection.ready"
            assert other_project_socket.receive_json()["type"] == "connection.ready"

            response = client.post(
                "/api/chat/messages",
                headers=headers,
                json={"channel": "general", "content": "Realtime hello"},
            )
            assert response.status_code == 200, response.text

            for socket in (first_tab, second_tab):
                events = [socket.receive_json(), socket.receive_json()]
                assert {event["type"] for event in events} == {"chat.changed", "logs.changed"}
                assert all(event["project_id"] == project_id for event in events)

            other_project_socket.send_json({"type": "ping"})
            assert other_project_socket.receive_json()["type"] == "pong"
