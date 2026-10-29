import base64
import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

from app.infrastructure.db.session import Base, engine
from app.infrastructure.db import models  # noqa: F401


SECRET = "bridge-test-secret"


def _b64(value: dict) -> str:
    raw = json.dumps(value, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def bridge_token(*scopes: str) -> str:
    now = int(time.time())
    header = _b64({"alg": "HS256", "typ": "JWT"})
    payload = _b64(
        {
            "iss": "folio",
            "aud": "personal-calendar",
            "purpose": "calendar_bridge",
            "sub": "11111111-1111-1111-1111-111111111111",
            "connection_id": "22222222-2222-2222-2222-222222222222",
            "scopes": list(scopes),
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "jti": "jti-test",
        }
    )
    signature = hmac.new(SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{header}.{payload}.{encoded}"


def test_bridge_connect_status_and_agenda(client):
    Base.metadata.create_all(engine)
    headers = {"Authorization": f"Bearer {bridge_token('calendar:connect')}"}
    connected = client.post(
        "/api/integration/v1/connect",
        json={"timezone": "Asia/Vladivostok", "idempotency_key": "33333333-3333-3333-3333-333333333333"},
        headers=headers,
    )
    assert connected.status_code == 200, connected.text
    calendar = connected.json()
    assert calendar["timezone"] == "Asia/Vladivostok"
    assert calendar["revision"] == 1

    again = client.post(
        "/api/integration/v1/connect",
        json={"timezone": "UTC"},
        headers=headers,
    )
    assert again.json()["id"] == calendar["id"]
    assert again.json()["timezone"] == "Asia/Vladivostok"

    read_headers = {"Authorization": f"Bearer {bridge_token('calendar:read')}"}
    status = client.get("/api/integration/v1/status", headers=read_headers)
    assert status.status_code == 200, status.text
    body = status.json()
    assert body["contract_version"] == 2
    assert body["calendar"]["id"] == calendar["id"]
    assert body["capabilities"]["read"] is True
    assert body["capabilities"]["write"] is False

    now = datetime(2026, 10, 30, 1, 0, tzinfo=UTC)
    event = client.put(
        "/api/entities/events/event-1",
        json={
            "calendarId": calendar["id"],
            "title": "Встреча",
            "description": "",
            "startAt": now.isoformat().replace("+00:00", "Z"),
            "endAt": now.replace(hour=2).isoformat().replace("+00:00", "Z"),
            "timezone": "Asia/Vladivostok",
            "allDay": False,
            "color": "#336699",
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "updatedAt": now.isoformat().replace("+00:00", "Z"),
        },
    )
    assert event.status_code == 200, event.text
    task = client.put(
        "/api/entities/tasks/task-1",
        json={
            "calendarId": calendar["id"],
            "title": "Просрочено",
            "dueDate": "2026-10-01",
            "completed": False,
            "createdAt": now.isoformat().replace("+00:00", "Z"),
            "updatedAt": now.isoformat().replace("+00:00", "Z"),
        },
    )
    assert task.status_code == 200, task.text

    agenda = client.get(
        "/api/integration/v1/agenda",
        params={"from": "2026-10-30", "to": "2026-10-30", "timezone": "Asia/Vladivostok"},
        headers=read_headers,
    )
    assert agenda.status_code == 200, agenda.text
    page = agenda.json()
    assert page["complete"] is True
    assert page["items"][0]["title"] == "Встреча"
    assert page["items"][0]["start_at"].endswith("Z")
    assert page["overdue_tasks"][0]["title"] == "Просрочено"
    assert page["overdue_tasks"][0]["start_at"] is None

    denied = client.get("/api/integration/v1/status")
    assert denied.status_code == 401
