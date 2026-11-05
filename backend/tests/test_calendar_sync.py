"""Wave 4 (D37): external ids, the per-connection changes feed with actor, signed webhooks."""
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from uuid import uuid4

import pytest

from test_calendar_oauth import bearer, connect, new_event, personal_id, server, user  # noqa: F401 — fixtures


def app_calendar(user):
    return next(c for c in user.get("/api/v2/calendars").json() if c["kind"] == "app")


def lesson(external_id, title="Урок"):
    return {**new_event(title), "external_id": external_id}


def ui_command(user, body):
    command_id = str(uuid4())
    return user.post("/api/commands", json={"command_id": command_id, "kind": "event", **body},
                     headers={"Idempotency-Key": command_id})


def ui_patch(user, event, title):
    return ui_command(user, {"operation": "patch", "entity_id": event["id"], "expected_revision": event["revision"],
                             "payload": {"title": title}})


def ui_create(user, calendar_id, title="Личное дело"):
    return ui_command(user, {"operation": "create", "calendar_id": calendar_id, "payload": new_event(title)})


# --- external_id -------------------------------------------------------------

def test_resending_external_id_updates_instead_of_duplicating(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    first = server.post("/api/v2/events", json=lesson("lesson-123"), headers=auth)
    assert first.status_code == 201 and first.json()["external_id"] == "lesson-123"
    again = server.post("/api/v2/events", json=lesson("lesson-123", "Урок (перенесён)"), headers=auth)
    assert again.status_code == 200, again.text
    assert again.json()["id"] == first.json()["id"] and again.json()["title"] == "Урок (перенесён)"
    listed = server.get("/api/v2/events", params={"calendar_id": app_calendar(user)["id"], "from": "2026-11-12", "to": "2026-11-12"}, headers=auth).json()
    assert [(i["title"], i["external_id"]) for i in listed["items"]] == [("Урок (перенесён)", "lesson-123")]
    assert server.get(f"/api/v2/events/{first.json()['id']}", headers=auth).json()["external_id"] == "lesson-123"


def test_retry_with_same_idempotency_key_replays(user, server):
    _, _, tokens = connect(user, server)
    headers = {**bearer(tokens["access_token"]), "Idempotency-Key": str(uuid4())}
    first = server.post("/api/v2/events", json=lesson("lesson-7"), headers=headers)
    retry = server.post("/api/v2/events", json=lesson("lesson-7"), headers=headers)
    assert first.status_code == 201 and retry.status_code == 201
    assert retry.json()["id"] == first.json()["id"]
    listed = server.get("/api/v2/events", params={"calendar_id": app_calendar(user)["id"], "from": "2026-11-12", "to": "2026-11-12"}, headers=bearer(tokens["access_token"]))
    assert len(listed.json()["items"]) == 1


def test_external_ids_differing_only_in_case_are_different_events(user, server):
    """External ids are opaque and case-sensitive on every database (MariaDB's default collation is not)."""
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    upper = server.post("/api/v2/events", json=lesson("Lesson-7", "Первый"), headers=auth)
    lower = server.post("/api/v2/events", json=lesson("lesson-7", "Второй"), headers=auth)
    assert (upper.status_code, lower.status_code) == (201, 201), lower.text
    assert upper.json()["id"] != lower.json()["id"]
    assert server.get(f"/api/v2/events/{upper.json()['id']}", headers=auth).json()["title"] == "Первый"


def test_external_id_upsert_respects_revision(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    event = server.post("/api/v2/events", json=lesson("lesson-9"), headers=auth).json()
    assert ui_patch(user, event, "Пользователь поправил").status_code == 200
    stale = server.post("/api/v2/events", json=lesson("lesson-9", "Старая версия"), headers={**auth, "If-Match": str(event["revision"])})
    assert stale.status_code == 409
    assert server.get(f"/api/v2/events/{event['id']}", headers=auth).json()["title"] == "Пользователь поправил"


def test_deleted_event_is_not_recreated_by_resend(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    event = server.post("/api/v2/events", json=lesson("lesson-5"), headers=auth).json()
    assert server.delete(f"/api/v2/events/{event['id']}", headers={**auth, "If-Match": str(event["revision"])}).status_code == 200
    again = server.post("/api/v2/events", json=lesson("lesson-5"), headers=auth)
    assert again.status_code == 409 and again.json()["error"]["details"] == {"entity_id": event["id"], "deleted": True}


def test_external_id_is_for_apps_and_validated(user, server):
    assert user.post("/api/v2/events", json=lesson("x")).status_code == 422
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    assert server.post("/api/v2/events", json=lesson(""), headers=auth).status_code == 422
    assert server.post("/api/v2/events", json=lesson("x" * 256), headers=auth).status_code == 422
    assert server.post("/api/v2/events", json=lesson(123), headers=auth).status_code == 422


# --- changes feed --------------------------------------------------------------

def test_feed_shows_actor_and_only_readable_calendars(user, server):
    client_id, _, tokens = connect(user, server)  # nothing ticked: the app reads only its own calendar
    auth = bearer(tokens["access_token"])
    event = server.post("/api/v2/events", json=lesson("lesson-1"), headers=auth).json()
    assert ui_patch(user, event, "Правка в интерфейсе").status_code == 200
    assert ui_create(user, personal_id(user)).status_code == 200

    feed = server.get("/api/v2/changes", headers=auth)
    assert feed.status_code == 200, feed.text
    items = feed.json()["items"]
    assert [(i["entity_id"], i["operation"], i["actor"]) for i in items] == [
        (event["id"], "create", f"app:{client_id}"), (event["id"], "patch", "user")]
    assert {i["calendar_id"] for i in items} == {app_calendar(user)["id"]}

    # The calendar UI reads the whole account, including the personal calendar.
    ui = user.get("/api/v2/changes").json()["items"]
    assert personal_id(user) in {i["calendar_id"] for i in ui}


def test_feed_cursor_pages_and_is_bound_to_its_reader(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    for n in range(3):
        server.post("/api/v2/events", json=lesson(f"l-{n}"), headers=auth)
    page = server.get("/api/v2/changes", params={"limit": 2}, headers=auth).json()
    assert len(page["items"]) == 2 and page["complete"] is False
    rest = server.get("/api/v2/changes", params={"cursor": page["next_cursor"]}, headers=auth).json()
    assert len(rest["items"]) == 1 and rest["complete"] is True
    idle = server.get("/api/v2/changes", params={"cursor": rest["next_cursor"]}, headers=auth).json()
    assert idle["items"] == [] and idle["next_cursor"] == rest["next_cursor"]
    # A cursor issued to this app does not work for the UI or another connection.
    assert user.get("/api/v2/changes", params={"cursor": rest["next_cursor"]}).status_code == 409
    _, _, other = connect(user, server)
    assert server.get("/api/v2/changes", params={"cursor": rest["next_cursor"]}, headers=bearer(other["access_token"])).status_code == 409


def test_feed_needs_events_read(user, server):
    _, _, tokens = connect(user, server, scope="openid")
    assert server.get("/api/v2/changes", headers=bearer(tokens["access_token"])).status_code == 403


# --- webhooks ------------------------------------------------------------------

@pytest.fixture()
def db():
    from app.infrastructure.db.session import SessionLocal
    with SessionLocal() as session:
        yield session


def dispatch(db, **kwargs):
    """Like one tick of run_forever, which opens a fresh session: start from a new transaction,
    so MySQL/MariaDB REPEATABLE READ does not hide changes the API committed meanwhile."""
    from app.application.webhooks import dispatch_due
    db.rollback()
    return dispatch_due(db, **kwargs)


def same_second(stored, expected):
    """MySQL/MariaDB DATETIME keeps whole seconds; SQLite keeps microseconds."""
    return stored.replace(microsecond=0) == expected.replace(microsecond=0)


def subscription(db, webhook_id):
    from app.infrastructure.db.models import WebhookSubscriptionModel
    db.expire_all()
    return db.get(WebhookSubscriptionModel, webhook_id)


def test_webhook_registration_rules(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    created = server.post("/api/v2/webhooks", json={"url": "https://tutor.example/hooks/calendar"}, headers=auth)
    assert created.status_code == 201, created.text
    assert created.json()["secret"].startswith("pcw_")
    for bad in ["http://tutor.example/h", "https://user:pw@tutor.example/h", "https://tutor.example/h#x", "ftp://x", ""]:
        assert server.post("/api/v2/webhooks", json={"url": bad}, headers=auth).status_code == 422, bad
    assert server.post("/api/v2/webhooks", json={"url": "https://a.example", "extra": 1}, headers=auth).status_code == 422
    assert user.post("/api/v2/webhooks", json={"url": "https://tutor.example/h"}).status_code == 403
    for n in range(4):
        assert server.post("/api/v2/webhooks", json={"url": f"https://tutor.example/{n}"}, headers=auth).status_code == 201
    assert server.post("/api/v2/webhooks", json={"url": "https://tutor.example/6"}, headers=auth).status_code == 409

    _, _, other = connect(user, server)
    assert server.delete(f"/api/v2/webhooks/{created.json()['id']}", headers=bearer(other["access_token"])).status_code == 404
    assert server.delete(f"/api/v2/webhooks/{created.json()['id']}", headers=auth).json() == {"id": created.json()["id"], "deleted": True}


def test_webhook_notifies_about_others_changes_only_and_is_signed(user, server, db):
    client_id, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    hook = server.post("/api/v2/webhooks", json={"url": "https://tutor.example/hooks"}, headers=auth).json()
    sent = []
    sender = lambda url, secret, payload: sent.append((url, secret, payload))  # noqa: E731

    event = server.post("/api/v2/events", json=lesson("lesson-1"), headers=auth).json()
    assert ui_create(user, personal_id(user)).status_code == 200  # a calendar this app was not given
    assert subscription(db, hook["id"]).pending is False
    assert dispatch(db, sender=sender) == 0

    assert ui_patch(user, event, "Перенесли").status_code == 200
    assert ui_patch(user, {**event, "revision": event["revision"] + 1}, "Ещё раз").status_code == 200  # one notice
    assert dispatch(db, sender=sender) == 1
    url, secret, payload = sent[0]
    assert (url, secret) == ("https://tutor.example/hooks", hook["secret"])
    assert payload["type"] == "changes" and payload["webhook_id"] == hook["id"]
    feed = server.get("/api/v2/changes", headers=auth).json()
    assert payload["change_cursor"] == feed["next_cursor"]
    assert subscription(db, hook["id"]).pending is False and subscription(db, hook["id"]).last_delivered_at is not None


def test_webhook_retries_with_backoff_then_gives_up_after_a_day(user, server, db):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    hook = server.post("/api/v2/webhooks", json={"url": "https://tutor.example/hooks"}, headers=auth).json()
    event = server.post("/api/v2/events", json=lesson("lesson-1"), headers=auth).json()
    assert ui_patch(user, event, "Перенесли").status_code == 200
    failing = lambda *_: "HTTP 500"  # noqa: E731

    start = datetime.utcnow() + timedelta(seconds=1)
    assert dispatch(db, now=start, sender=failing) == 1
    row = subscription(db, hook["id"])
    assert row.pending and row.failures == 1 and same_second(row.next_attempt_at, start + timedelta(seconds=30))
    assert dispatch(db, now=start + timedelta(seconds=10), sender=failing) == 0  # not due yet
    assert dispatch(db, now=start + timedelta(seconds=31), sender=failing) == 1
    assert same_second(subscription(db, hook["id"]).next_attempt_at, start + timedelta(seconds=31 + 60))

    late = start + timedelta(hours=24, seconds=1)
    assert dispatch(db, now=late, sender=failing) == 1
    row = subscription(db, hook["id"])
    assert row.pending is False and row.active is True and row.last_error == "HTTP 500"


def test_revoked_connection_gets_no_webhooks(user, server, db):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    hook = server.post("/api/v2/webhooks", json={"url": "https://tutor.example/hooks"}, headers=auth).json()
    event = server.post("/api/v2/events", json=lesson("lesson-1"), headers=auth).json()
    assert ui_patch(user, event, "Перенесли").status_code == 200
    grant = user.get("/api/v2/grants").json()[0]
    user.delete(f"/api/v2/grants/{grant['id']}")
    sent = []
    dispatch(db, sender=lambda *a: sent.append(a))
    assert sent == []


def test_signature_and_ssrf_guard(monkeypatch):
    from app.application import webhooks
    body = b'{"type":"changes"}'
    expected = "sha256=" + hmac.new(b"pcw_s", b"1700000000." + body, hashlib.sha256).hexdigest()
    assert webhooks.sign("pcw_s", "1700000000", body) == expected
    for host in ["127.0.0.1", "10.1.2.3", "192.168.0.1", "169.254.169.254", "::1", "localhost", "no-such-host.invalid"]:
        assert webhooks.public_address(host) is False, host
    assert webhooks.public_address("8.8.8.8") is True
    called = []
    monkeypatch.setattr(webhooks.httpx, "post", lambda *a, **k: called.append(a))
    assert webhooks.send("https://127.0.0.1/hook", "pcw_s", {}) == "address is not public"
    assert called == []


def test_send_posts_signed_json(monkeypatch):
    from app.application import webhooks

    class Reply:
        status_code = 204

    seen = {}

    def fake_post(url, content, headers, timeout, follow_redirects):
        seen.update(url=url, content=content, headers=headers, follow_redirects=follow_redirects)
        return Reply()

    monkeypatch.setattr(webhooks, "public_address", lambda host: True)
    monkeypatch.setattr(webhooks.httpx, "post", fake_post)
    assert webhooks.send("https://tutor.example/h", "pcw_s", {"type": "changes"}) is None
    assert json.loads(seen["content"]) == {"type": "changes"} and seen["follow_redirects"] is False
    ts = seen["headers"]["X-Calendar-Timestamp"]
    assert seen["headers"]["X-Calendar-Signature"] == webhooks.sign("pcw_s", ts, seen["content"])
