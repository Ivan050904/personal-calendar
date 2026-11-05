import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import unquote, urlencode
from uuid import NAMESPACE_URL, uuid5

import httpx

from app.core.calendar_actor import CalendarActor
from app.core.errors import AppError

SCOPES = frozenset({"calendar:connect", "calendar:read", "calendar:write", "calendar:history", "calendar:reminders"})


def principal_id(folio_user_id: str) -> str:
    return str(uuid5(NAMESPACE_URL, "personal-calendar:folio:" + folio_user_id))


def verify_bridge_actor(token: str, settings, now: datetime) -> CalendarActor:
    if not settings.calendar_bridge_secret:
        raise AppError("unavailable", "Bridge is not configured", status_code=503)
    try:
        head, body, signature = token.split(".")
        def decode(value):
            return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        header = json.loads(decode(head))
        claims = json.loads(decode(body))
        assert isinstance(header,dict) and isinstance(claims,dict)
        digest = hmac.new(settings.calendar_bridge_secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest()
        assert header.get("alg") == "HS256" and hmac.compare_digest(digest, decode(signature))
        assert claims["iss"] == "folio" and claims["aud"] == "personal-calendar" and claims["purpose"] == "calendar_bridge"
        for key in ["sub", "connection_id", "jti"]:
            assert isinstance(claims[key], str) and claims[key]
        for key in ["iat", "nbf", "exp"]:
            assert type(claims[key]) in (int, float)
        ts = now.astimezone(timezone.utc).timestamp()
        assert 0 < claims["exp"] - claims["iat"] <= 60
        assert claims['iat'] <= claims['nbf'] < claims['exp']
        assert claims["iat"] <= ts + 30 and claims["nbf"] <= ts + 30 and claims["exp"] > ts - 30
        assert isinstance(claims["scopes"], list) and all(isinstance(s, str) for s in claims["scopes"])
        scopes = frozenset(claims["scopes"])
        assert scopes <= SCOPES
    except (ValueError, KeyError, TypeError, AssertionError, UnicodeError):
        raise AppError("unauthorized", "Invalid bridge credential", status_code=401) from None
    return CalendarActor(principal_id(claims["sub"]), claims["sub"], scopes)


def safe_launch_target(target) -> str:
    if isinstance(target, dict):
        allowed = {"calendar_id", "kind", "entity_id", "occurrence_key"}
        if not set(target) <= allowed or target.get("kind") not in {None, "event", "plan", "task"}:
            raise AppError("validation_error", "Invalid calendar target", status_code=422)
        return "/?" + urlencode({k:v for k,v in target.items() if v is not None})
    value = str(target or "/")
    decoded = unquote(value)
    if not decoded.startswith("/") or decoded.startswith("//") or "\\" in decoded or any(ord(c) < 32 for c in decoded):
        raise AppError("validation_error", "Invalid calendar target", status_code=422)
    return value


def exchange_folio_launch(code: str, settings) -> dict:
    if not settings.folio_exchange_base_url or not settings.folio_exchange_secret:
        raise AppError("unavailable", "Launch exchange is not configured", status_code=503)
    try:
        response = httpx.post(settings.folio_exchange_base_url.rstrip("/") + "/calendar/sso/exchange",
                              json={"code": code}, headers={"X-Calendar-Client-Id": settings.folio_server_client_id,
                              "X-Calendar-Exchange-Secret": settings.folio_exchange_secret}, timeout=10)
    except httpx.HTTPError:
        raise AppError("unavailable", "Launch exchange unavailable", status_code=503) from None
    if response.status_code != 200:
        raise AppError("unauthorized", "Invalid or consumed launch code", status_code=401)
    actor = response.json()
    if not actor.get("folio_user_id") or not actor.get("connection_id"):
        raise AppError("unauthorized", "Invalid exchange response", status_code=401)
    return actor
