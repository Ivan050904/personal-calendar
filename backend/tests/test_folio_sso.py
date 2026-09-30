from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from app.core.folio_sso import decode_folio_jwt, folio_identity_allowed, parse_csv_set


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_token(payload: dict, secret: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64url(hmac.new(secret.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def test_decode_folio_jwt_ok():
    secret = "test-secret"
    token = _make_token({"sub": "u1", "email": "petr@petr.local", "exp": int(time.time()) + 60}, secret)
    payload = decode_folio_jwt(token, secret=secret)
    assert payload is not None
    assert payload["email"] == "petr@petr.local"


def test_decode_folio_jwt_rejects_bad_sig():
    token = _make_token({"sub": "u1", "exp": int(time.time()) + 60}, "a")
    assert decode_folio_jwt(token, secret="b") is None


def test_folio_identity_allowed_by_email():
    assert folio_identity_allowed(
        {"sub": "x", "email": "petr@petr.local"},
        allowed_emails={"petr@petr.local"},
        allowed_user_ids=set(),
    )
    assert not folio_identity_allowed(
        {"sub": "x", "email": "other@x.local"},
        allowed_emails={"petr@petr.local"},
        allowed_user_ids=set(),
    )


def test_parse_csv_set():
    assert parse_csv_set(" petr@petr.local , A@B.C ") == {"petr@petr.local", "a@b.c"}
