from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from starlette.responses import Response

COOKIE_NAME = "pc_session"
SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def auth_configured(username: str, password: str, session_secret: str) -> bool:
    return bool(username.strip() and password and session_secret.strip())


def passwords_match(provided: str, expected: str) -> bool:
    left = provided.encode("utf-8")
    right = expected.encode("utf-8")
    if len(left) != len(right):
        secrets.compare_digest(right, right)
        return False
    return secrets.compare_digest(left, right)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_session_token(*, username: str, secret: str) -> str:
    payload = {"u": username, "exp": int(time.time()) + SESSION_MAX_AGE_SECONDS}
    body = _b64encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    sig = _b64encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def read_session_username(token: str | None, *, secret: str) -> str | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = _b64encode(hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest())
    if not secrets.compare_digest(sig, expected):
        return None
    try:
        data: Any = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    exp = data.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    username = data.get("u")
    return username if isinstance(username, str) and username else None


def set_session_cookie(response: Response, token: str, *, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
