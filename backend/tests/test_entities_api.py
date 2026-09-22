from datetime import datetime

import pytest


def test_entity_crud_via_api(client):
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    calendar = {
        "id": "api-cal-1",
        "name": "API Local",
        "timezone": "UTC",
        "createdAt": now,
        "updatedAt": now,
    }
    put = client.put("/api/entities/calendars/api-cal-1", json=calendar)
    assert put.status_code == 200
    assert put.json()["name"] == "API Local"

    listed = client.get("/api/entities/calendars")
    assert listed.status_code == 200
    assert any(item["id"] == "api-cal-1" for item in listed.json())

    got = client.get("/api/entities/calendars/api-cal-1")
    assert got.status_code == 200
    assert got.json()["timezone"] == "UTC"

    local = client.get("/api/calendars/local")
    assert local.status_code == 200
    # Local calendar is the earliest non-deleted calendar in DB (stable order).
    assert local.json() is not None
    assert "id" in local.json()

    deleted = client.delete("/api/entities/calendars/api-cal-1")
    assert deleted.status_code == 200
    missing = client.get("/api/entities/calendars/api-cal-1")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_unknown_collection(client):
    response = client.get("/api/entities/nope")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
