"""Wave 6 (D38): invitations by login, organizer-only edits, the invitee's view, feed and app access."""
from datetime import datetime
from uuid import uuid4

import pytest

from test_calendar_oauth import (PASSWORD, auth_params, bearer, code_from, consent, exchange, new_client, new_event,  # noqa: F401
                                 personal_id, pkce, register_client, server, user)

DAY = {"from": "2026-11-12", "to": "2026-11-12"}
WITH_INVITES = "openid profile calendars.read events.read events.write sharing.invite"


@pytest.fixture()
def guest():
    from app.application.accounts import create_account
    from app.infrastructure.db.session import SessionLocal
    login = f"gu-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        create_account(db, login, PASSWORD, "Гость", "Europe/Moscow")
        db.commit()
    c = new_client()
    assert c.post("/api/auth/login", json={"username": login, "password": PASSWORD}).status_code == 200
    c.login = login
    yield c
    c.__exit__(None, None, None)


def ui_event(user, title="Ужин вдвоём"):
    command_id = str(uuid4())
    made = user.post("/api/commands", json={"command_id": command_id, "kind": "event", "operation": "create",
                                            "calendar_id": personal_id(user), "payload": new_event(title)},
                     headers={"Idempotency-Key": command_id})
    assert made.status_code == 200, made.text
    return made.json()["entity"]


def connect_app(person, server, scope=WITH_INVITES, calendar_ids=()):
    extra = [arg for s in scope.split() for arg in ("--scope", s)]
    client_id, secret = register_client(*extra)
    verifier, challenge = pkce()
    code = code_from(consent(person, auth_params(client_id, challenge, scope), calendar_ids))
    return bearer(exchange(server, client_id, secret, code, verifier).json()["access_token"])


# --- spec §11 wave 6 test plan ---------------------------------------------------

def test_organizer_moves_event_and_invitee_sees_it(user, guest):
    event = ui_event(user)
    invited = user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login.upper()})
    assert invited.status_code == 201, invited.text
    assert (invited.json()["login"], invited.json()["status"]) == (guest.login, "pending")
    assert user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login}).status_code == 200  # no twin

    mine = guest.get("/api/v2/invitations").json()
    assert [(i["event"]["title"], i["status"], i["organizer"]["login"]) for i in mine] == [("Ужин вдвоём", "pending", user.login)]
    board = guest.get("/api/v2/invitations/occurrences", params={**DAY, "timezone": "Europe/Moscow"}).json()["items"]
    assert [(i["title"], i["invitation"]["status"]) for i in board] == [("Ужин вдвоём", "pending")]

    moved = user.patch(f"/api/v2/events/{event['id']}", json={"start_at": "2026-11-12T17:00:00Z", "end_at": "2026-11-12T19:00:00Z"},
                       headers={"If-Match": str(event["revision"])})
    assert moved.status_code == 200, moved.text
    board = guest.get("/api/v2/invitations/occurrences", params={**DAY, "timezone": "Europe/Moscow"}).json()["items"]
    assert board[0]["start_at"] == "2026-11-12T17:00:00Z"
    seen = guest.get(f"/api/v2/events/{event['id']}").json()
    assert seen["start_at"] == "2026-11-12T17:00:00Z" and seen["invitation"]["status"] == "pending"

    feed = guest.get("/api/v2/changes").json()["items"]
    assert [(i["entity_id"], i["operation"]) for i in feed if i["entity_id"] == event["id"]] == [
        (event["id"], "invited"), (event["id"], "patch")]


def test_invitee_cannot_change_the_event_only_answer(user, guest):
    event = ui_event(user)
    user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login})
    match = {"If-Match": str(event["revision"])}
    assert guest.patch(f"/api/v2/events/{event['id']}", json={"title": "Моё"}, headers=match).status_code == 403
    assert guest.delete(f"/api/v2/events/{event['id']}", headers=match).status_code == 403
    assert guest.post(f"/api/v2/events/{event['id']}/confirm", json={"status": "occurred", "happened_date": "2026-11-12"}, headers=match).status_code == 403
    assert guest.post(f"/api/v2/events/{event['id']}/attendees", json={"login": user.login}).status_code == 404
    command_id = str(uuid4())
    legacy = guest.post("/api/commands", headers={"Idempotency-Key": command_id}, json={
        "command_id": command_id, "kind": "event", "operation": "patch", "entity_id": event["id"],
        "expected_revision": event["revision"], "payload": {"title": "Моё"}})
    assert legacy.status_code == 404
    assert user.get(f"/api/v2/events/{event['id']}").json()["title"] == "Ужин вдвоём"

    assert guest.patch(f"/api/v2/events/{event['id']}/attendees/me", json={"status": "maybe"}).status_code == 422
    answered = guest.patch(f"/api/v2/events/{event['id']}/attendees/me", json={"status": "accepted"})
    assert answered.status_code == 200 and answered.json()["status"] == "accepted" and answered.json()["responded_at"]
    listed = user.get(f"/api/v2/events/{event['id']}/attendees").json()
    assert listed["organizer"]["login"] == user.login
    assert [(a["login"], a["status"]) for a in listed["attendees"]] == [(guest.login, "accepted")]
    assert guest.get(f"/api/v2/events/{event['id']}/attendees").status_code == 200
    organizer_feed = user.get("/api/v2/changes").json()["items"]
    assert (event["id"], "responded") in [(i["entity_id"], i["operation"]) for i in organizer_feed]


def test_inviting_unknown_login_or_self_fails(user, guest):
    event = ui_event(user)
    assert user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": "nobody-" + uuid4().hex[:6]}).status_code == 404
    assert user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": user.login}).status_code == 422
    assert user.post(f"/api/v2/events/{event['id']}/attendees", json={"name": "x"}).status_code == 422
    assert user.post(f"/api/v2/events/{uuid4()}/attendees", json={"login": guest.login}).status_code == 404
    from app.application.accounts import find_by_login
    from app.infrastructure.db.session import SessionLocal
    with SessionLocal() as db:
        find_by_login(db, guest.login).active = False
        db.commit()
    assert user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login}).status_code == 404


def test_declined_leaves_the_board_and_deleted_leaves_the_list(user, guest):
    event = ui_event(user)
    user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login})
    guest.patch(f"/api/v2/events/{event['id']}/attendees/me", json={"status": "declined"})
    assert guest.get("/api/v2/invitations/occurrences", params=DAY).json()["items"] == []
    assert [i["status"] for i in guest.get("/api/v2/invitations").json()] == ["declined"]
    user.delete(f"/api/v2/events/{event['id']}", headers={"If-Match": str(event["revision"])})
    assert guest.get("/api/v2/invitations").json() == []
    assert guest.get(f"/api/v2/events/{event['id']}").status_code == 404


def test_strangers_see_nothing(user, guest, server):
    event = ui_event(user)
    assert guest.get(f"/api/v2/events/{event['id']}").status_code == 404
    assert guest.get(f"/api/v2/events/{event['id']}/attendees").status_code == 404
    assert guest.patch(f"/api/v2/events/{event['id']}/attendees/me", json={"status": "accepted"}).status_code == 404


# --- connected apps (the couples app) ---------------------------------------------------

def test_app_with_sharing_invite_creates_and_invites(user, guest, server):
    auth = connect_app(user, server)
    made = server.post("/api/v2/events", json=new_event("Свидание"), headers=auth).json()
    invited = server.post(f"/api/v2/events/{made['id']}/attendees", json={"login": guest.login}, headers=auth)
    assert invited.status_code == 201, invited.text
    # Not into the user's own records, and not without the scope.
    personal_event = ui_event(user)
    assert server.post(f"/api/v2/events/{personal_event['id']}/attendees", json={"login": guest.login}, headers=auth).status_code in (403, 404)
    plain = connect_app(user, server, scope="openid events.read events.write")
    other = server.post("/api/v2/events", json=new_event("Без приглашений"), headers=plain).json()
    assert server.post(f"/api/v2/events/{other['id']}/attendees", json={"login": guest.login}, headers=plain).status_code == 403


def test_invitees_app_sees_invitations_and_feed_only_with_scope(user, guest, server, ):
    event = ui_event(user)
    user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login})

    plain = connect_app(guest, server, scope="openid events.read events.write")
    assert server.get("/api/v2/invitations", headers=plain).status_code == 403
    assert server.get(f"/api/v2/events/{event['id']}", headers=plain).status_code == 403
    assert all(i["entity_id"] != event["id"] for i in server.get("/api/v2/changes", headers=plain).json()["items"])

    couples = connect_app(guest, server)
    assert [i["event"]["id"] for i in server.get("/api/v2/invitations", headers=couples).json()] == [event["id"]]
    assert server.patch(f"/api/v2/events/{event['id']}/attendees/me", json={"status": "accepted"}, headers=couples).status_code == 200
    assert event["id"] in [i["entity_id"] for i in server.get("/api/v2/changes", headers=couples).json()["items"]]
    assert server.patch(f"/api/v2/events/{event['id']}", json={"title": "x"}, headers={**couples, "If-Match": "1"}).status_code == 403


def test_invitees_webhook_fires_when_organizer_changes_event(user, guest, server):
    from app.application.webhooks import dispatch_due
    from app.infrastructure.db.session import SessionLocal
    event = ui_event(user)
    user.post(f"/api/v2/events/{event['id']}/attendees", json={"login": guest.login})
    couples = connect_app(guest, server)
    server.post("/api/v2/webhooks", json={"url": "https://couples.example/hook"}, headers=couples)
    user.patch(f"/api/v2/events/{event['id']}", json={"title": "Ужин в 8"}, headers={"If-Match": str(event["revision"])})
    sent = []
    with SessionLocal() as db:
        dispatch_due(db, now=datetime.utcnow(), sender=lambda url, secret, payload: sent.append(url))
    assert "https://couples.example/hook" in sent
