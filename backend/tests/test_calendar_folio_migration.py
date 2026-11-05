"""Wave 5 (§8): API v2 does everything Folio does through /integration/v1, accounts made through Folio
get a login + password, the old bridge and the new OAuth path work on the same data, and the bridge
can be switched off."""
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from test_calendar_oauth import PASSWORD, bearer, connect, new_client, new_event, personal_id, server, user  # noqa: F401

DAY = {"from": "2026-11-12", "to": "2026-11-12"}


@pytest.fixture(scope="module", autouse=True)
def hide_created_rows():
    """Unscoped repository tests (test_repositories.py) list every calendar and plan in the shared DB:
    soft-delete what this module created so they keep seeing only their own rows."""
    from sqlalchemy import select, update
    from app.infrastructure.db.models import CalendarModel, PlanModel
    from app.infrastructure.db.session import SessionLocal
    with SessionLocal() as db:
        before = {model: set(db.scalars(select(model.id))) for model in (CalendarModel, PlanModel)}
    yield
    with SessionLocal() as db:
        for model, ids in before.items():
            db.execute(update(model).where(model.id.not_in(ids) if ids else True, model.deleted_at.is_(None))
                       .values(deleted_at=datetime.utcnow()))
        db.commit()


def app_calendar(user):
    return next(c for c in user.get("/api/v2/calendars").json() if c["kind"] == "app")


def ui_command(user, body):
    command_id = str(uuid4())
    return user.post("/api/commands", json={"command_id": command_id, **body}, headers={"Idempotency-Key": command_id})


def task(title="Задача", **extra):
    return {"title": title, "timezone": "Europe/Moscow", **extra}


def plan(title="План"):
    return {"title": title, "timezone": "Europe/Moscow", "start_at": "2026-11-12T12:00:00Z", "end_at": "2026-11-12T13:00:00Z"}


# --- v2 parity: tasks, plans, «было/не было», history, reminders -------------

def test_app_manages_tasks_and_plans_with_external_ids(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    cal = app_calendar(user)["id"]

    made = server.post("/api/v2/tasks", json={**task(due_date="2026-11-12"), "external_id": "t-1"}, headers=auth)
    assert made.status_code == 201, made.text
    again = server.post("/api/v2/tasks", json={**task("Задача 2", due_date="2026-11-12"), "external_id": "t-1"}, headers=auth)
    assert again.status_code == 200 and again.json()["id"] == made.json()["id"]
    undated = server.post("/api/v2/tasks", json=task("Без даты"), headers=auth)
    assert undated.status_code == 201

    tasks = server.get("/api/v2/tasks", params={"calendar_id": cal, **DAY}, headers=auth).json()["items"]
    assert {(t["title"], t["external_id"]) for t in tasks} == {("Задача 2", "t-1"), ("Без даты", None)}

    done = server.post(f"/api/v2/tasks/{made.json()['id']}/complete", json={},
                       headers={**auth, "If-Match": str(again.json()["revision"])})
    assert done.status_code == 200, done.text
    assert server.get(f"/api/v2/tasks/{made.json()['id']}", headers=auth).json()["completed"] is True

    p = server.post("/api/v2/plans", json={**plan(), "external_id": "p-1"}, headers=auth)
    assert p.status_code == 201, p.text
    plans = server.get("/api/v2/plans", params={"calendar_id": cal, **DAY}, headers=auth).json()["items"]
    assert [(x["title"], x["external_id"]) for x in plans] == [("План", "p-1")]
    gone = server.delete(f"/api/v2/plans/{p.json()['id']}", headers={**auth, "If-Match": str(p.json()["revision"])})
    assert gone.status_code == 200
    back = server.post(f"/api/v2/plans/{p.json()['id']}/restore", json={}, headers={**auth, "If-Match": str(p.json()["revision"] + 1)})
    assert back.status_code == 200, back.text

    agenda = server.get("/api/v2/agenda", params={"calendar_id": cal, **DAY}, headers=auth).json()
    assert [(i["kind"], i["external_id"]) for i in agenda["items"]] == [("plan", "p-1")]  # the done task drops out
    assert [t["title"] for t in agenda["undated_tasks"]] == ["Без даты"]


def test_confirmation_history_and_reminders(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    cal = app_calendar(user)["id"]
    event = server.post("/api/v2/events", json=new_event(), headers=auth).json()

    confirmed = server.post(f"/api/v2/events/{event['id']}/confirm", json={"status": "occurred", "happened_date": "2026-11-12"},
                            headers={**auth, "If-Match": str(event["revision"])})
    assert confirmed.status_code == 200, confirmed.text
    fact = server.get(f"/api/v2/confirmations/{event['id']}", headers=auth).json()["confirmation"]
    assert fact["status"] == "occurred"
    history = server.get("/api/v2/history", params=DAY, headers=auth).json()["items"]
    assert [h["entity_id"] for h in history] == [event["id"]]
    assert server.get(f"/api/v2/occurrences/{event['id']}", headers=auth).json()["entity_id"] == event["id"]

    reminders = server.get("/api/v2/reminder-source", params={"calendar_id": cal, **DAY}, headers=auth)
    assert reminders.status_code == 200 and [i["entity_id"] for i in reminders.json()["items"]] == [event["id"]]
    assert server.get("/api/v2/reminder-source", params={"calendar_id": personal_id(user), **DAY}, headers=auth).status_code == 404


def test_old_records_in_personal_are_readable_not_writable(user, server):
    """The owner's choice for Folio: old records stay in «Личное»; the app reads them if ticked, never edits."""
    personal = personal_id(user)
    old_event = ui_command(user, {"kind": "event", "operation": "create", "calendar_id": personal, "payload": new_event("Старое")}).json()["entity"]
    ui_command(user, {"kind": "event", "operation": "confirm", "entity_id": old_event["id"], "expected_revision": old_event["revision"],
                      "payload": {"status": "occurred", "happened_date": "2026-11-12"}})

    _, _, blind = connect(user, server)  # nothing ticked
    auth = bearer(blind["access_token"])
    assert server.get(f"/api/v2/events/{old_event['id']}", headers=auth).status_code == 404
    assert server.get(f"/api/v2/confirmations/{old_event['id']}", headers=auth).status_code == 404
    assert server.get("/api/v2/history", params=DAY, headers=auth).json()["items"] == []

    _, _, seeing = connect(user, server, [personal])
    auth = bearer(seeing["access_token"])
    assert server.get(f"/api/v2/events/{old_event['id']}", headers=auth).json()["title"] == "Старое"
    assert [h["entity_id"] for h in server.get("/api/v2/history", params=DAY, headers=auth).json()["items"]] == [old_event["id"]]
    current = server.get(f"/api/v2/events/{old_event['id']}", headers=auth).json()
    for call in (lambda h: server.patch(f"/api/v2/events/{old_event['id']}", json={"title": "x"}, headers=h),
                 lambda h: server.delete(f"/api/v2/events/{old_event['id']}", headers=h),
                 lambda h: server.post(f"/api/v2/events/{old_event['id']}/confirm", json={"status": "not_occurred", "happened_date": "2026-11-12"}, headers=h)):
        assert call({**auth, "If-Match": str(current["revision"])}).status_code == 403
    assert server.post("/api/v2/tasks", json=task(), params={"calendar_id": personal}, headers=auth).status_code == 403


def test_app_token_reaches_new_reads_but_not_v1(user, server):
    _, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    assert server.get("/api/integration/v1/agenda", params=DAY, headers=auth).status_code == 403
    assert server.post("/api/v2/agenda", headers=auth).status_code == 403


# --- §8.2/§8.5: an account without a login sets one ---------------------------

def session_for(principal_id):
    from app.core.auth import COOKIE_NAME
    from app.infrastructure.db.auth_sessions import create_session
    from app.infrastructure.db.models import CalendarPrincipalModel
    from app.infrastructure.db.session import SessionLocal
    with SessionLocal() as db:
        token, _ = create_session(db, db.get(CalendarPrincipalModel, principal_id))
        db.commit()
    c = new_client()
    c.cookies.set(COOKIE_NAME, token)
    return c


def bridge_token(sub, scopes=("calendar:connect", "calendar:read", "calendar:write", "calendar:history", "calendar:reminders")):
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    ts = int(datetime.now(timezone.utc).timestamp())
    body = enc({"alg": "HS256", "typ": "JWT"}) + "." + enc({
        "iss": "folio", "aud": "personal-calendar", "purpose": "calendar_bridge", "sub": sub, "connection_id": "c",
        "scopes": list(scopes), "iat": ts, "nbf": ts, "exp": ts + 60, "jti": str(uuid4())})
    return body + "." + base64.urlsafe_b64encode(hmac.new(b"synthetic-bridge", body.encode(), hashlib.sha256).digest()).decode().rstrip("=")


@pytest.fixture()
def bridge(monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "calendar_bridge_secret", "synthetic-bridge")
    monkeypatch.setattr(get_settings(), "folio_bridge_enabled", True)
    return get_settings()


def test_folio_account_sets_login_and_password_once(server, bridge):
    from app.core.bridge_auth import principal_id
    from app.core import login_rate_limit
    login_rate_limit.reset()
    sub = f"folio-{uuid4().hex[:8]}"
    assert server.post("/api/integration/v1/connect", json={"timezone": "Europe/Moscow", "idempotency_key": str(uuid4())},
                       headers=bearer(bridge_token(sub))).status_code == 200
    ui = session_for(principal_id(sub))
    assert ui.get("/api/v2/me").json()["login"] is None

    login = f"fo-{uuid4().hex[:8]}"
    assert ui.post("/api/v2/me/credentials", json={"login": login, "password": "short"}).status_code == 422
    done = ui.post("/api/v2/me/credentials", json={"login": login.upper(), "password": PASSWORD})
    assert done.status_code == 200 and done.json()["login"] == login
    assert ui.post("/api/v2/me/credentials", json={"login": "other-login", "password": PASSWORD}).status_code == 409

    fresh = new_client()
    signed_in = fresh.post("/api/auth/login", json={"username": login, "password": PASSWORD})
    assert signed_in.status_code == 200
    assert fresh.get("/api/v2/me").json()["id"] == principal_id(sub)  # same account
    ui.__exit__(None, None, None)
    fresh.__exit__(None, None, None)


def test_credentials_need_a_free_login_and_a_session(user, server, bridge):
    from app.core.bridge_auth import principal_id
    sub = f"folio-{uuid4().hex[:8]}"
    server.post("/api/integration/v1/connect", json={"timezone": "UTC", "idempotency_key": str(uuid4())}, headers=bearer(bridge_token(sub)))
    ui = session_for(principal_id(sub))
    assert ui.post("/api/v2/me/credentials", json={"login": user.login, "password": PASSWORD}).status_code == 409
    assert user.post("/api/v2/me/credentials", json={"login": "x-" + uuid4().hex[:6], "password": PASSWORD}).status_code == 409
    assert server.post("/api/v2/me/credentials", json={"login": "y-" + uuid4().hex[:6], "password": PASSWORD},
                       headers=bearer(bridge_token(sub))).status_code == 403
    ui.__exit__(None, None, None)


# --- §8.3/§8.4: old and new path on the same data; switching the bridge off ---------

def test_bridge_and_oauth_share_data_then_bridge_switches_off(server, bridge):
    from app.core.bridge_auth import principal_id
    from test_calendar_oauth import auth_params, code_from, consent, exchange, pkce, register_client
    sub = f"folio-{uuid4().hex[:8]}"
    old = bearer(bridge_token(sub))
    server.post("/api/integration/v1/connect", json={"timezone": "Europe/Moscow", "idempotency_key": str(uuid4())}, headers=old)
    command_id = str(uuid4())
    via_bridge = server.post("/api/integration/v1/commands", headers={**old, "Idempotency-Key": command_id},
                             json={"command_id": command_id, "kind": "event", "operation": "create", "payload": new_event("Через мост")})
    assert via_bridge.status_code == 200, via_bridge.text

    ui = session_for(principal_id(sub))
    ui.post("/api/v2/me/credentials", json={"login": f"fb-{uuid4().hex[:8]}", "password": PASSWORD})
    personal = personal_id(ui)
    client_id, secret = register_client()
    verifier, challenge = pkce()
    tokens = exchange(server, client_id, secret, code_from(consent(ui, auth_params(client_id, challenge), [personal])), verifier).json()
    new = bearer(tokens["access_token"])

    # New path reads what the old path wrote …
    assert server.get(f"/api/v2/events/{via_bridge.json()['entity']['id']}", headers=new).json()["title"] == "Через мост"
    # … and the old path reads what the new path wrote (in the app calendar).
    via_oauth = server.post("/api/v2/events", json=new_event("Через OAuth"), headers=new).json()
    agenda = server.get("/api/integration/v1/agenda", params={"calendar_id": via_oauth["calendar_id"], **DAY}, headers=bearer(bridge_token(sub)))
    assert [i["title"] for i in agenda.json()["items"]] == ["Через OAuth"]

    bridge.folio_bridge_enabled = False
    assert server.get("/api/integration/v1/agenda", params=DAY, headers=bearer(bridge_token(sub))).status_code == 401
    assert server.get("/api/auth/folio", params={"code": "anything"}).status_code == 401
    assert server.get(f"/api/v2/events/{via_oauth['id']}", headers=new).status_code == 200  # OAuth keeps working
    ui.__exit__(None, None, None)


def test_env_login_name_stays_with_the_env_owner(server, bridge):
    """An own account named like the env login would shadow it and lock the owner out (security review fix)."""
    from app.application.accounts import create_account
    from app.core.bridge_auth import principal_id
    from app.core.errors import AppError
    from app.infrastructure.db.session import SessionLocal
    reserved = get_settings_value("auth_username")
    sub = f"folio-{uuid4().hex[:8]}"
    server.post("/api/integration/v1/connect", json={"timezone": "UTC", "idempotency_key": str(uuid4())}, headers=bearer(bridge_token(sub)))
    ui = session_for(principal_id(sub))
    assert ui.post("/api/v2/me/credentials", json={"login": reserved.upper(), "password": PASSWORD}).status_code == 409
    with SessionLocal() as db, pytest.raises(AppError) as err:
        create_account(db, reserved, PASSWORD)
    assert err.value.status_code == 409
    ui.__exit__(None, None, None)


def get_settings_value(name):
    from app.core.config import get_settings
    return getattr(get_settings(), name)
