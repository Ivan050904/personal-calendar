import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.core.errors import AppError


def token(payload):
    def enc(obj):
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).decode().rstrip("=")
    body = enc({"alg": "HS256", "typ": "JWT"}) + "." + enc(payload)
    return body + "." + base64.urlsafe_b64encode(hmac.new(b"synthetic-bridge", body.encode(), hashlib.sha256).digest()).decode().rstrip("=")


def test_bridge_requires_all_claims_and_purpose():
    from app.core.bridge_auth import verify_bridge_actor
    now = datetime.now(timezone.utc)
    ts = int(now.timestamp())
    payload = {"iss":"folio", "aud":"personal-calendar", "purpose":"calendar_bridge", "sub":"alice",
               "connection_id":"connection", "scopes":["calendar:read"], "iat":ts,"nbf":ts,"exp":ts+60,"jti":"id"}
    settings = SimpleNamespace(calendar_bridge_secret="synthetic-bridge")
    assert verify_bridge_actor(token(payload), settings, now).folio_user_id == "alice"
    for key in payload:
        invalid = {k:v for k,v in payload.items() if k != key}
        with pytest.raises(AppError):
            verify_bridge_actor(token(invalid), settings, now)
    payload["purpose"] = "access"
    with pytest.raises(AppError):
        verify_bridge_actor(token(payload), settings, now)
