"""Wave 3 (D35/D36): OAuth Authorization Code + PKCE, consent, tokens, app calendar, app API limits."""
import base64
import hashlib
import importlib.util
import re
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

PASSWORD = "correct-horse-1"
REDIRECT = "https://tutor.example/calendar/callback"
ALL = "openid profile calendars.read events.read events.write"


def _script(name):
    spec = importlib.util.spec_from_file_location(f"owner_{name}", Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def register_client(*extra):
    lines = []
    assert _script("oauth_clients").main(["create", "--name", "Репетитор", "--redirect-uri", REDIRECT, *extra], out=lines.append) == 0
    values = {}
    for line in lines:
        key, value = line.split(": ", 1)
        values[key.split(" ")[0]] = value
    return values["client_id"], values.get("client_secret")


def new_client():
    from app.main import create_app
    c = TestClient(create_app(), follow_redirects=False)
    c.__enter__()
    return c


@pytest.fixture()
def user():
    from app.application.accounts import create_account
    from app.core import login_rate_limit
    from app.infrastructure.db.session import SessionLocal
    login_rate_limit.reset()
    login = f"oa-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        create_account(db, login, PASSWORD, "Учитель", "Europe/Moscow")
        db.commit()
    c = new_client()
    assert c.post("/api/auth/login", json={"username": login, "password": PASSWORD}).status_code == 200
    c.login = login
    yield c
    c.__exit__(None, None, None)


@pytest.fixture()
def server():
    """The app's own backend: no calendar cookies."""
    c = new_client()
    yield c
    c.__exit__(None, None, None)


def pkce():
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    return verifier, challenge


def auth_params(client_id, challenge, scope=ALL, **over):
    return {"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "scope": scope,
            "state": "st-123", "code_challenge": challenge, "code_challenge_method": "S256", **over}


def csrf_of(html):
    return re.search(r'name="csrf" value="([^"]+)"', html).group(1)


def consent(user, params, calendar_ids=(), decision="allow"):
    page = user.get("/api/oauth/authorize", params=params)
    assert page.status_code == 200, page.text
    form = {**params, "csrf": csrf_of(page.text), "decision": decision, "calendar_ids": list(calendar_ids)}
    return user.post("/api/oauth/authorize", data=form)


def code_from(response):
    assert response.status_code == 303, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["state"] == ["st-123"]
    return query["code"][0]


def exchange(server, client_id, secret, code, verifier, redirect=REDIRECT):
    data = {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect, "code_verifier": verifier,
            "client_id": client_id}
    if secret:
        data["client_secret"] = secret
    return server.post("/api/oauth/token", data=data)


def connect(user, server, calendar_ids=(), scope=ALL):
    client_id, secret = register_client()
    verifier, challenge = pkce()
    code = code_from(consent(user, auth_params(client_id, challenge, scope), calendar_ids))
    tokens = exchange(server, client_id, secret, code, verifier)
    assert tokens.status_code == 200, tokens.text
    return client_id, secret, tokens.json()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def personal_id(user):
    return user.get("/api/v2/calendars").json()[0]["id"]


def new_event(title="Урок"):
    return {"title": title, "timezone": "Europe/Moscow", "start_at": "2026-11-12T09:00:00Z", "end_at": "2026-11-12T10:00:00Z"}


# --- happy path --------------------------------------------------------------

def test_full_flow_creates_app_calendar_and_scoped_access(user, server):
    page = user.get("/api/oauth/authorize", params=auth_params(register_client()[0], pkce()[1]))
    assert "«Репетитор» хочет доступ" in page.text
    assert page.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in page.headers["content-security-policy"]

    personal = personal_id(user)
    client_id, _, tokens = connect(user, server, [personal])
    assert tokens["token_type"] == "Bearer" and tokens["expires_in"] == 900
    assert tokens["access_token"].startswith("pca_") and tokens["refresh_token"].startswith("pcr_")
    auth = bearer(tokens["access_token"])

    me = server.get("/api/oauth/userinfo", headers=auth).json()
    assert me["preferred_username"] == user.login and me["name"] == "Учитель"

    mine = user.get("/api/v2/calendars").json()
    app_cal = next(c for c in mine if c["kind"] == "app")
    assert (app_cal["name"], app_cal["source_client_id"]) == ("Репетитор", client_id)
    seen = {c["id"] for c in server.get("/api/v2/calendars", headers=auth).json()}
    assert seen == {personal, app_cal["id"]}

    created = server.post("/api/v2/events", json=new_event(), headers={**auth, "Idempotency-Key": str(uuid4())})
    assert created.status_code == 201, created.text
    assert created.json()["calendar_id"] == app_cal["id"]
    listed = server.get("/api/v2/events", params={"calendar_id": app_cal["id"], "from": "2026-11-12", "to": "2026-11-12"}, headers=auth)
    assert [i["title"] for i in listed.json()["items"]] == ["Урок"]
    # The user sees the lesson on the board through the app calendar.
    assert user.get("/api/occurrences", params={"calendar_id": app_cal["id"], "from": "2026-11-12", "to": "2026-11-12"}).json()["items"][0]["title"] == "Урок"

    event = created.json()
    patched = server.patch(f"/api/v2/events/{event['id']}", json={"title": "Урок 2"}, headers={**auth, "If-Match": str(event["revision"])})
    assert patched.status_code == 200 and patched.json()["title"] == "Урок 2"
    stale = server.patch(f"/api/v2/events/{event['id']}", json={"title": "x"}, headers={**auth, "If-Match": str(event["revision"])})
    assert stale.status_code == 409
    assert server.patch(f"/api/v2/events/{event['id']}", json={"title": "x"}, headers=auth).status_code == 428
    gone = server.delete(f"/api/v2/events/{event['id']}", headers={**auth, "If-Match": str(patched.json()["revision"])})
    assert gone.status_code == 200


def test_consent_form_posts_like_a_browser(user):
    """Pages must not use Referrer-Policy: no-referrer, or browsers send `Origin: null` and the POST is refused."""
    client_id, _ = register_client()
    params = auth_params(client_id, pkce()[1])
    page = user.get("/api/oauth/authorize", params=params)
    assert page.headers["referrer-policy"] == "same-origin"
    same_site = user.post("/api/oauth/authorize", headers={"Origin": "http://testserver"},
                          data={**params, "csrf": csrf_of(page.text), "decision": "allow"})
    assert same_site.status_code == 303
    cross_site = user.post("/api/oauth/authorize", headers={"Origin": "https://evil.example"},
                           data={**params, "csrf": csrf_of(page.text), "decision": "allow"})
    assert cross_site.status_code == 403


def test_same_scopes_again_skip_consent(user, server):
    client_id, _, _ = connect(user, server)
    again = user.get("/api/oauth/authorize", params=auth_params(client_id, pkce()[1]))
    assert again.status_code == 303 and "code=" in again.headers["location"]


# --- authorize-request validation ------------------------------------------

def test_unknown_client_and_foreign_redirect_never_redirect(user):
    challenge = pkce()[1]
    unknown = user.get("/api/oauth/authorize", params=auth_params("pcl_nope", challenge))
    assert unknown.status_code == 400 and "location" not in unknown.headers
    client_id, _ = register_client()
    evil = user.get("/api/oauth/authorize", params=auth_params(client_id, challenge, redirect_uri="https://evil.example/cb"))
    assert evil.status_code == 400 and "location" not in evil.headers


@pytest.mark.parametrize("over,error", [
    ({"code_challenge_method": "plain"}, "invalid_request"),
    ({"code_challenge": "short"}, "invalid_request"),
    ({"state": ""}, "invalid_request"),
    ({"response_type": "token"}, "unsupported_response_type"),
    ({"scope": "events.read sharing.invite"}, "invalid_scope"),
    ({"scope": ""}, "invalid_scope"),
])
def test_bad_requests_return_error_to_client(user, over, error):
    client_id, _ = register_client()
    r = user.get("/api/oauth/authorize", params=auth_params(client_id, pkce()[1], **over))
    assert r.status_code == 303
    assert parse_qs(urlsplit(r.headers["location"]).query)["error"] == [error]


def test_scope_outside_client_allowance_is_refused(user):
    lines = []
    _script("oauth_clients").main(["create", "--name", "RO", "--redirect-uri", REDIRECT, "--scope", "events.read"], out=lines.append)
    client_id = lines[0].split(": ")[1]
    r = user.get("/api/oauth/authorize", params=auth_params(client_id, pkce()[1], scope="events.read events.write"))
    assert parse_qs(urlsplit(r.headers["location"]).query)["error"] == ["invalid_scope"]


def test_deny_and_csrf(user):
    client_id, _ = register_client()
    params = auth_params(client_id, pkce()[1])
    denied = consent(user, params, decision="deny")
    assert parse_qs(urlsplit(denied.headers["location"]).query)["error"] == ["access_denied"]
    forged = user.post("/api/oauth/authorize", data={**params, "csrf": "0" * 64, "decision": "allow"})
    assert forged.status_code == 403
    assert user.get("/api/v2/grants").json() == []


def test_login_page_when_not_signed_in(user, server):
    client_id, _ = register_client()
    params = auth_params(client_id, pkce()[1])
    page = server.get("/api/oauth/authorize", params=params)
    assert page.status_code == 200 and 'name="password"' in page.text
    assert server.post("/api/oauth/login", data={**params, "login": user.login, "password": "wrong-pass"}).status_code == 401
    ok = server.post("/api/oauth/login", data={**params, "login": user.login, "password": PASSWORD})
    assert ok.status_code == 303 and ok.headers["location"].startswith("authorize?")
    assert "csrf" in server.get("/api/oauth/authorize", params=params).text  # now the consent screen


# --- token endpoint ---------------------------------------------------------

def test_code_is_single_use_and_replay_kills_tokens(user, server):
    client_id, secret = register_client()
    verifier, challenge = pkce()
    code = code_from(consent(user, auth_params(client_id, challenge)))
    first = exchange(server, client_id, secret, code, verifier).json()
    replay = exchange(server, client_id, secret, code, verifier)
    assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant"
    assert server.get("/api/oauth/userinfo", headers=bearer(first["access_token"])).status_code == 401


@pytest.mark.parametrize("case", ["verifier", "redirect", "expired", "secret", "other_client"])
def test_code_exchange_failures(user, server, case):
    from app.infrastructure.db.models import OAuthAuthorizationCodeModel
    from app.infrastructure.db.session import SessionLocal
    client_id, secret = register_client()
    verifier, challenge = pkce()
    code = code_from(consent(user, auth_params(client_id, challenge)))
    if case == "expired":
        with SessionLocal() as db:
            for row in db.query(OAuthAuthorizationCodeModel).filter_by(client_id=client_id):
                row.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
    other_id, other_secret = register_client()
    r = exchange(server, *{
        "verifier": (client_id, secret, code, pkce()[0]),
        "redirect": (client_id, secret, code, verifier, "https://tutor.example/other"),
        "expired": (client_id, secret, code, verifier),
        "secret": (client_id, "pcs_wrong", code, verifier),
        "other_client": (other_id, other_secret, code, verifier),
    }[case])
    assert r.status_code == (401 if case == "secret" else 400)
    assert r.json()["error"] == ("invalid_client" if case == "secret" else "invalid_grant")
    assert r.headers["cache-control"] == "no-store"


def test_basic_auth_and_public_client(user, server):
    client_id, secret = register_client()
    verifier, challenge = pkce()
    code = code_from(consent(user, auth_params(client_id, challenge)))
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    ok = server.post("/api/oauth/token", headers={"Authorization": f"Basic {basic}"},
                     data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT, "code_verifier": verifier})
    assert ok.status_code == 200

    public_id, public_secret = register_client("--public")
    assert public_secret is None
    verifier, challenge = pkce()
    code = code_from(consent(user, auth_params(public_id, challenge)))
    assert exchange(server, public_id, "pcs_any", code, verifier).json()["error"] == "invalid_client"
    verifier, challenge = pkce()
    code = code_from(user.get("/api/oauth/authorize", params=auth_params(public_id, challenge)))
    assert exchange(server, public_id, None, code, verifier).status_code == 200


def test_refresh_rotation_and_reuse_detection(user, server):
    client_id, secret, tokens = connect(user, server)
    data = {"grant_type": "refresh_token", "client_id": client_id, "client_secret": secret}
    second = server.post("/api/oauth/token", data={**data, "refresh_token": tokens["refresh_token"]})
    assert second.status_code == 200
    fresh = second.json()
    assert fresh["refresh_token"] != tokens["refresh_token"]
    assert server.get("/api/oauth/userinfo", headers=bearer(fresh["access_token"])).status_code == 200
    reuse = server.post("/api/oauth/token", data={**data, "refresh_token": tokens["refresh_token"]})
    assert reuse.json()["error"] == "invalid_grant"
    # A leaked old refresh token revokes the whole connection.
    assert server.get("/api/oauth/userinfo", headers=bearer(fresh["access_token"])).status_code == 401
    assert server.post("/api/oauth/token", data={**data, "refresh_token": fresh["refresh_token"]}).json()["error"] == "invalid_grant"
    assert user.get("/api/v2/grants").json() == []


def test_expired_access_token(user, server):
    from app.application.oauth import digest
    from app.infrastructure.db.models import OAuthTokenModel
    from app.infrastructure.db.session import SessionLocal
    _, _, tokens = connect(user, server)
    with SessionLocal() as db:
        db.get(OAuthTokenModel, digest(tokens["access_token"])).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.commit()
    assert server.get("/api/oauth/userinfo", headers=bearer(tokens["access_token"])).status_code == 401


# --- what an app may and may not do ----------------------------------------

def test_app_reads_only_ticked_calendars_and_writes_only_its_own(user, server):
    personal = personal_id(user)
    hidden = user.post("/api/v2/calendars", json={"name": "Личное тайное"}).json()
    cid = str(uuid4())
    own_event = user.post("/api/commands", headers={"Idempotency-Key": cid},
                          json={"command_id": cid, "kind": "event", "operation": "create", "payload": new_event("Моё")}).json()["entity"]
    _, _, tokens = connect(user, server, [personal])
    auth = bearer(tokens["access_token"])
    span = {"from": "2026-11-12", "to": "2026-11-12"}
    assert server.get("/api/v2/events", params={"calendar_id": personal, **span}, headers=auth).status_code == 200
    assert server.get("/api/v2/events", params={"calendar_id": hidden["id"], **span}, headers=auth).status_code == 404
    assert server.post("/api/v2/events", params={"calendar_id": personal}, json=new_event(), headers=auth).status_code == 403
    assert server.patch(f"/api/v2/events/{own_event['id']}", json={"title": "x"}, headers={**auth, "If-Match": "1"}).status_code == 403
    assert server.delete(f"/api/v2/events/{own_event['id']}", headers={**auth, "If-Match": "1"}).status_code == 403
    assert server.get(f"/api/v2/events/{own_event['id']}", headers=auth).status_code == 200


def test_read_only_app_cannot_write(user, server):
    _, _, tokens = connect(user, server, [], scope="events.read calendars.read")
    assert server.post("/api/v2/events", json=new_event(), headers=bearer(tokens["access_token"])).status_code == 403
    assert not any(c["kind"] == "app" for c in user.get("/api/v2/calendars").json())


@pytest.mark.parametrize("method,path", [
    ("GET", "/api/v2/me"), ("GET", "/api/v2/grants"), ("POST", "/api/v2/calendars"), ("GET", "/api/entities/events"),
    ("POST", "/api/commands"), ("GET", "/api/calendars/local"), ("GET", "/api/integration/v1/status"),
    ("POST", "/api/v2/me/password"), ("GET", "/api/occurrences"), ("POST", "/api/ai/chat"),
])
def test_app_token_cannot_reach_ui_endpoints(user, server, method, path):
    _, _, tokens = connect(user, server)
    assert server.request(method, path, headers=bearer(tokens["access_token"]), json={}).status_code == 403


def test_user_revokes_in_settings_and_app_revokes_itself(user, server):
    _, _, tokens = connect(user, server)
    grant = user.get("/api/v2/grants").json()[0]
    assert grant["client_name"] == "Репетитор"
    assert user.delete(f"/api/v2/grants/{grant['id']}").json() == {"id": grant["id"], "revoked": True}
    assert server.get("/api/oauth/userinfo", headers=bearer(tokens["access_token"])).status_code == 401

    client_id, secret, tokens = connect(user, server)
    assert server.post("/api/oauth/revoke", data={"token": tokens["refresh_token"], "client_id": client_id, "client_secret": secret}).status_code == 200
    assert server.get("/api/oauth/userinfo", headers=bearer(tokens["access_token"])).status_code == 401


def test_reconnect_after_revoke_reuses_app_calendar(user, server):
    client_id, _, _ = connect(user, server)
    grant = user.get("/api/v2/grants").json()[0]
    user.delete(f"/api/v2/grants/{grant['id']}")
    verifier, challenge = pkce()
    code_from(consent(user, auth_params(client_id, challenge)))
    assert [c["kind"] for c in user.get("/api/v2/calendars").json()].count("app") == 1


def test_grants_are_private_to_the_account(user, server):
    connect(user, server)
    grant = user.get("/api/v2/grants").json()[0]
    from app.application.accounts import create_account
    from app.infrastructure.db.session import SessionLocal
    other_login = f"oa-{uuid4().hex[:8]}"
    with SessionLocal() as db:
        create_account(db, other_login, PASSWORD)
        db.commit()
    other = new_client()
    other.post("/api/auth/login", json={"username": other_login, "password": PASSWORD})
    assert other.get("/api/v2/grants").json() == []
    assert other.delete(f"/api/v2/grants/{grant['id']}").status_code == 404
    other.__exit__(None, None, None)


def test_deleting_app_calendar_withdraws_write_until_reconsent(user, server):
    client_id, _, tokens = connect(user, server)
    auth = bearer(tokens["access_token"])
    app_cal = next(c for c in user.get("/api/v2/calendars").json() if c["kind"] == "app")
    assert user.delete(f"/api/v2/calendars/{app_cal['id']}").status_code == 200
    assert server.post("/api/v2/events", json=new_event(), headers=auth).status_code == 403
    again = user.get("/api/oauth/authorize", params=auth_params(client_id, pkce()[1]))
    assert again.status_code == 200 and "csrf" in again.text  # consent is asked again


def test_owner_script_validates_redirect_uris():
    out = []
    script = _script("oauth_clients")
    assert script.main(["create", "--name", "X", "--redirect-uri", "http://evil.example/cb"], out=out.append) == 1
    assert script.main(["create", "--name", "X", "--redirect-uri", "https://a.example/cb#frag"], out=out.append) == 1
    assert script.main(["create", "--name", "X", "--redirect-uri", "http://localhost:3000/cb"], out=out.append) == 0
    assert script.main(["create", "--name", "X", "--redirect-uri", REDIRECT, "--scope", "freebusy.read"], out=out.append) == 1  # not supported yet


def test_metadata(server):
    meta = server.get("/api/.well-known/oauth-authorization-server").json()
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["token_endpoint"].endswith("/api/oauth/token")
