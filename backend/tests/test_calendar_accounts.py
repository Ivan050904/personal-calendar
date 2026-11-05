"""Wave 1 (D34): own accounts, login + password, sessions, owner script, registration flag."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

PASSWORD = "correct-horse-1"


@pytest.fixture(autouse=True)
def fresh_limits():
    from app.core import login_rate_limit
    login_rate_limit.reset()
    yield
    login_rate_limit.reset()


@pytest.fixture()
def anon():
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def unique_login(prefix="user"):
    return f"{prefix}-{uuid4().hex[:8]}"


def make_account(login=None, password=PASSWORD):
    from app.application.accounts import create_account
    from app.infrastructure.db.session import SessionLocal
    login = login or unique_login()
    with SessionLocal() as db:
        row = create_account(db, login, password, "Тест", "Europe/Moscow")
        db.commit()
        return row.id, login


def login_client(login, password=PASSWORD):
    from app.main import create_app
    c = TestClient(create_app())
    c.__enter__()
    r = c.post("/api/auth/login", json={"username": login, "password": password})
    assert r.status_code == 200, r.text
    return c


def test_registration_is_closed_by_default(anon):
    r = anon.post("/api/v2/accounts", json={"login": unique_login(), "password": PASSWORD})
    assert r.status_code == 503


def test_registration_creates_account_session_and_personal_calendar(anon, monkeypatch):
    from app.core.config import get_settings
    from app.infrastructure.db.models import CalendarModel
    from app.infrastructure.db.session import SessionLocal
    from sqlalchemy import select
    monkeypatch.setattr(get_settings(), "registration_enabled", True)
    login = unique_login("New")
    r = anon.post("/api/v2/accounts", json={"login": login, "password": PASSWORD, "display_name": "Петя"})
    assert r.status_code == 201, r.text
    assert r.json()["login"] == login.lower()
    me = anon.get("/api/v2/me")
    assert me.status_code == 200 and me.json()["display_name"] == "Петя"
    assert anon.get("/api/auth/me").json()["username"] == login.lower()
    with SessionLocal() as db:
        cals = db.scalars(select(CalendarModel).where(CalendarModel.owner_id == r.json()["id"])).all()
    assert [(c.name, c.default_owner) for c in cals] == [("Личное", r.json()["id"])]
    again = anon.post("/api/v2/accounts", json={"login": login.upper(), "password": PASSWORD})
    assert again.status_code == 409


@pytest.mark.parametrize("login,password", [("ab", PASSWORD), ("bad login", PASSWORD), ("кириллица", PASSWORD),
                                            (unique_login(), "short"), (unique_login(), "x" * 257)])
def test_registration_validates_login_and_password(anon, monkeypatch, login, password):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "registration_enabled", True)
    assert anon.post("/api/v2/accounts", json={"login": login, "password": password}).status_code == 422


def test_login_wrong_password_and_unknown_login_look_the_same(anon):
    _, login = make_account()
    wrong = anon.post("/api/auth/login", json={"username": login, "password": "wrong-password"})
    unknown = anon.post("/api/auth/login", json={"username": unique_login(), "password": "wrong-password"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    ok = anon.post("/api/auth/login", json={"username": login.upper(), "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["username"] == login


def test_failed_logins_are_rate_limited(anon):
    _, login = make_account()
    for _ in range(5):
        assert anon.post("/api/auth/login", json={"username": login, "password": "wrong-password"}).status_code == 401
    blocked = anon.post("/api/auth/login", json={"username": login, "password": PASSWORD})
    assert blocked.status_code == 429


def test_change_password_revokes_other_sessions_only():
    _, login = make_account()
    a, b = login_client(login), login_client(login)
    try:
        bad = a.post("/api/v2/me/password", json={"current_password": "nope-nope", "new_password": "new-password-1"})
        assert bad.status_code == 401
        ok = a.post("/api/v2/me/password", json={"current_password": PASSWORD, "new_password": "new-password-1"})
        assert ok.status_code == 200
        assert a.get("/api/v2/me").status_code == 200
        assert b.get("/api/v2/me").status_code == 401
        assert a.post("/api/auth/login", json={"username": login, "password": PASSWORD}).status_code == 401
        assert a.post("/api/auth/login", json={"username": login, "password": "new-password-1"}).status_code == 200
    finally:
        a.__exit__(None, None, None)
        b.__exit__(None, None, None)


def test_revoke_other_sessions():
    _, login = make_account()
    a, b = login_client(login), login_client(login)
    try:
        assert a.post("/api/v2/me/sessions/revoke-others").json() == {"revoked": 1}
        assert a.get("/api/v2/me").status_code == 200
        assert b.get("/api/v2/me").status_code == 401
    finally:
        a.__exit__(None, None, None)
        b.__exit__(None, None, None)


def test_account_management_requires_a_session_not_an_app_token():
    from app.api.routes.accounts import require_session_actor
    from app.core.calendar_actor import CalendarActor
    from app.core.errors import AppError
    with pytest.raises(AppError) as error:
        require_session_actor(CalendarActor("someone", "folio-someone", frozenset()))
    assert error.value.status_code == 403


def test_two_accounts_see_only_their_own_data(db_session):
    from app.application.accounts import create_account
    from app.application.entity_service import EntityService
    from app.core.bridge_auth import SCOPES
    from app.core.calendar_actor import CalendarActor
    alice = create_account(db_session, unique_login("alice"), PASSWORD)
    bob = create_account(db_session, unique_login("bob"), PASSWORD)
    alice_cals = EntityService(db_session, CalendarActor(alice.id, None, SCOPES)).list_entities("calendars")
    bob_cals = EntityService(db_session, CalendarActor(bob.id, None, SCOPES)).list_entities("calendars")
    assert len(alice_cals) == len(bob_cals) == 1
    assert alice_cals[0]["id"] != bob_cals[0]["id"]


def test_owner_script_creates_account_and_resets_password(anon):
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "accounts.py"
    spec = importlib.util.spec_from_file_location("owner_accounts_script", path)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)

    login, lines = unique_login("script"), []
    assert script.main(["create", login, "--name", "Ученик"], out=lines.append) == 0
    first = lines[-1].split(": ", 1)[1]
    assert anon.post("/api/auth/login", json={"username": login, "password": first}).status_code == 200
    assert anon.get("/api/v2/me").status_code == 200

    assert script.main(["reset-password", login], out=lines.append) == 0
    second = lines[-1].split(": ", 1)[1]
    assert anon.get("/api/v2/me").status_code == 401  # reset revokes every session
    assert anon.post("/api/auth/login", json={"username": login, "password": first}).status_code == 401
    assert anon.post("/api/auth/login", json={"username": login, "password": second}).status_code == 200
    assert script.main(["create", login], out=lines.append) == 1
    assert script.main(["reset-password", unique_login("ghost")], out=lines.append) == 1
