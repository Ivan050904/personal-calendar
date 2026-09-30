from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def decode_folio_jwt(token: str, *, secret: str, algorithm: str = "HS256") -> dict[str, Any] | None:
    """Verify Folio-One HS256 JWT without adding python-jose."""
    if algorithm != "HS256" or not token or token.count(".") != 2:
        return None
    header_b64, payload_b64, sig_b64 = token.split(".")
    try:
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "HS256":
            return None
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        actual = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected, actual):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and int(exp) < int(time.time()):
        return None
    return payload


def parse_csv_set(raw: str) -> set[str]:
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def folio_identity_allowed(
    payload: dict[str, Any],
    *,
    allowed_emails: set[str],
    allowed_user_ids: set[str],
) -> bool:
    if not allowed_emails and not allowed_user_ids:
        return False
    subject = str(payload.get("sub") or "").strip().lower()
    email = str(payload.get("email") or "").strip().lower()
    if allowed_user_ids and subject in allowed_user_ids:
        return True
    if allowed_emails and email and email in allowed_emails:
        return True
    return False
