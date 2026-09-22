from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_and_me(client: TestClient, settings):
    if not settings.auth_username:
        # Auth disabled in this environment — skip behavioral asserts.
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        return

    denied = client.get("/api/calendars/local")
    # Session client may already be logged in via fixture; use a fresh client for deny check.
    from app.main import create_app

    with TestClient(create_app()) as anon:
        denied = anon.get("/api/calendars/local")
        assert denied.status_code == 401
        bad = anon.post("/api/auth/login", json={"username": "nope", "password": "wrong"})
        assert bad.status_code == 401
        ok = anon.post(
            "/api/auth/login",
            json={"username": settings.auth_username, "password": settings.auth_password},
        )
        assert ok.status_code == 200
        me = anon.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["authenticated"] is True
        assert me.json()["username"] == settings.auth_username
        calendars = anon.get("/api/calendars/local")
        assert calendars.status_code in {200, 404}


def test_health_stays_public(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
