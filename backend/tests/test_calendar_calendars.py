"""Wave 2 (D36): several calendars per account, colour/visibility, create into a chosen calendar."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

PASSWORD = "correct-horse-1"


def account_client():
    from app.application.accounts import create_account
    from app.core import login_rate_limit
    from app.infrastructure.db.session import SessionLocal
    from app.main import create_app
    login_rate_limit.reset()
    login = f"cal-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        create_account(db, login, PASSWORD, None, "Europe/Moscow")
        db.commit()
    client = TestClient(create_app())
    client.__enter__()
    assert client.post("/api/auth/login", json={"username": login, "password": PASSWORD}).status_code == 200
    return client


@pytest.fixture()
def alice():
    c = account_client()
    yield c
    c.__exit__(None, None, None)


@pytest.fixture()
def bob():
    c = account_client()
    yield c
    c.__exit__(None, None, None)


def create_event(client, title, calendar_id=None):
    command_id = str(uuid4())
    body = {"command_id": command_id, "kind": "event", "operation": "create",
            "payload": {"title": title, "timezone": "Europe/Moscow", "start_at": "2026-11-10T09:00:00Z",
                        "end_at": "2026-11-10T10:00:00Z"}}
    if calendar_id:
        body["calendar_id"] = calendar_id
    return client.post("/api/commands", json=body, headers={"Idempotency-Key": command_id})


def occurrence_titles(client, calendar_id):
    r = client.get("/api/occurrences", params={"calendar_id": calendar_id, "from": "2026-11-10", "to": "2026-11-10"})
    assert r.status_code == 200, r.text
    return [item["title"] for item in r.json()["items"]]


def test_new_account_lists_only_personal(alice):
    rows = alice.get("/api/v2/calendars").json()
    assert [(r["name"], r["kind"], r["visible"]) for r in rows] == [("Личное", "personal", True)]
    assert rows[0]["timezone"] == "Europe/Moscow"


def test_create_patch_and_order(alice):
    sport = alice.post("/api/v2/calendars", json={"name": "Спорт", "color": "#FF0000"})
    assert sport.status_code == 201, sport.text
    assert sport.json()["kind"] == "user" and sport.json()["color"] == "#ff0000"
    assert sport.json()["timezone"] == "Europe/Moscow"
    work = alice.post("/api/v2/calendars", json={"name": "Работа"}).json()
    names = [r["name"] for r in alice.get("/api/v2/calendars").json()]
    assert names == ["Личное", "Спорт", "Работа"]
    patched = alice.patch(f"/api/v2/calendars/{work['id']}", json={"name": "Офис", "visible": False, "color": "#00aa00"})
    assert patched.status_code == 200
    assert (patched.json()["name"], patched.json()["visible"], patched.json()["color"]) == ("Офис", False, "#00aa00")
    assert patched.json()["revision"] == work["revision"] + 1


@pytest.mark.parametrize("body", [{"name": ""}, {"name": "   "}, {"name": "X", "color": "red"},
                                  {"name": "X", "timezone": "Mars/Base"}, {"name": "X", "kind": "app"}])
def test_create_validation(alice, body):
    assert alice.post("/api/v2/calendars", json=body).status_code == 422


def test_personal_cannot_be_deleted_but_others_can(alice):
    personal = alice.get("/api/v2/calendars").json()[0]
    assert alice.delete(f"/api/v2/calendars/{personal['id']}").status_code == 409
    extra = alice.post("/api/v2/calendars", json={"name": "Временный"}).json()
    assert create_event(alice, "В удаляемом", extra["id"]).status_code == 200
    assert alice.delete(f"/api/v2/calendars/{extra['id']}").json() == {"id": extra["id"], "deleted": True}
    assert [r["id"] for r in alice.get("/api/v2/calendars").json()] == [personal["id"]]
    # Entries of a deleted calendar are no longer readable or writable.
    assert alice.get("/api/occurrences", params={"calendar_id": extra["id"], "from": "2026-11-10", "to": "2026-11-10"}).status_code == 404
    assert create_event(alice, "Поздно", extra["id"]).status_code == 404


def test_create_event_into_chosen_calendar(alice):
    personal = alice.get("/api/v2/calendars").json()[0]
    sport = alice.post("/api/v2/calendars", json={"name": "Спорт"}).json()
    assert create_event(alice, "Зал", sport["id"]).json()["entity"]["calendar_id"] == sport["id"]
    assert create_event(alice, "Дела").json()["entity"]["calendar_id"] == personal["id"]
    assert occurrence_titles(alice, sport["id"]) == ["Зал"]
    assert occurrence_titles(alice, personal["id"]) == ["Дела"]


def test_calendar_id_only_on_create(alice):
    sport = alice.post("/api/v2/calendars", json={"name": "Спорт"}).json()
    created = create_event(alice, "Зал").json()["entity"]
    command_id = str(uuid4())
    r = alice.post("/api/commands", headers={"Idempotency-Key": command_id}, json={
        "command_id": command_id, "kind": "event", "operation": "patch", "entity_id": created["id"],
        "expected_revision": created["revision"], "calendar_id": sport["id"], "payload": {"title": "Move"}})
    assert r.status_code == 422


def test_foreign_calendars_are_invisible(alice, bob):
    secret = bob.post("/api/v2/calendars", json={"name": "Секрет"}).json()
    bob_personal = bob.get("/api/v2/calendars").json()[0]
    for calendar_id in (secret["id"], bob_personal["id"]):
        assert alice.patch(f"/api/v2/calendars/{calendar_id}", json={"name": "hack"}).status_code == 404
        assert alice.delete(f"/api/v2/calendars/{calendar_id}").status_code == 404
        assert create_event(alice, "Подброс", calendar_id).status_code == 404
    assert all(r["id"] not in {secret["id"], bob_personal["id"]} for r in alice.get("/api/v2/calendars").json())


def test_legacy_entity_put_keeps_kind_and_colour(alice):
    personal = alice.get("/api/v2/calendars").json()[0]
    alice.patch(f"/api/v2/calendars/{personal['id']}", json={"color": "#123456"})
    entity = alice.get(f"/api/entities/calendars/{personal['id']}").json()
    assert alice.put(f"/api/entities/calendars/{personal['id']}", json={**entity, "name": "Мой"}).status_code == 200
    after = alice.get("/api/v2/calendars").json()[0]
    assert (after["name"], after["kind"], after["color"]) == ("Мой", "personal", "#123456")
