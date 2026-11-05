from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.auth import COOKIE_NAME, auth_configured, read_session_username
from app.core.config import get_settings
from app.core.errors import error_body
from datetime import datetime, timezone
from app.core.bridge_auth import verify_bridge_actor
from app.core.errors import AppError
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.auth_sessions import read_actor_session


def _is_public_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(
        normalized.endswith(suffix)
        for suffix in (
            "/health",
            "/auth/login",
            "/auth/me",
            "/auth/logout",
            "/auth/sso",
            "/auth/folio",
            "/v2/accounts",
            "/oauth/authorize",
            "/oauth/login",
            "/oauth/token",
            "/oauth/revoke",
            "/.well-known/oauth-authorization-server",
            "/docs",
            "/openapi.json",
            "/redoc",
        )
    )


def _app_may_call(method: str, path: str, api_prefix: str) -> bool:
    """Connected apps (OAuth tokens, D35) reach only the app API; everything else is UI-only."""
    rel = path[len(api_prefix):] if api_prefix and path.startswith(api_prefix + "/") else path
    rel = rel.rstrip("/") or "/"
    if rel == "/v2/calendars":
        return method in {"GET", "HEAD"}
    if rel == "/v2/changes":
        return method in {"GET", "HEAD"}
    return rel in {"/oauth/userinfo", "/v2/events", "/v2/webhooks"} or rel.startswith(("/v2/events/", "/v2/webhooks/"))


def _service_token_ok(request: Request, settings) -> bool:
    expected = (settings.folio_service_token or "").strip()
    if not expected:
        return False
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        provided = header[7:].strip()
        if provided and hmac_compare(provided, expected):
            return True
    provided = request.headers.get("X-Folio-Service-Token", "").strip()
    return bool(provided) and hmac_compare(provided, expected)


def hmac_compare(left: str, right: str) -> bool:
    import secrets

    a = left.encode("utf-8")
    b = right.encode("utf-8")
    if len(a) != len(b):
        secrets.compare_digest(b, b)
        return False
    return secrets.compare_digest(a, b)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        actor = None
        if request.method not in {'GET','HEAD','OPTIONS'}:
            origin = request.headers.get('origin')
            if origin and origin.rstrip('/') not in {str(request.base_url).rstrip('/'), *settings.cors_origin_list}:
                return JSONResponse(status_code=403,content=error_body('forbidden','Invalid request origin'))
        header = request.headers.get("Authorization", "")
        try:
            if header.lower().startswith("bearer ") and header[7:].strip().startswith("pca_"):
                from app.application.oauth import actor_for_access_token
                with SessionLocal() as db:
                    actor = actor_for_access_token(db, header[7:].strip())
            elif header.lower().startswith("bearer "):
                actor = verify_bridge_actor(header[7:], settings, datetime.now(timezone.utc))
                from app.infrastructure.db.models import CalendarPrincipalModel
                with SessionLocal() as db:
                    principal=db.get(CalendarPrincipalModel,actor.principal_id)
                    if principal is not None and not principal.active:
                        raise AppError('forbidden','Principal inactive',status_code=403)
            elif request.cookies.get(COOKIE_NAME):
                with SessionLocal() as db:
                    actor = read_actor_session(db, request.cookies.get(COOKIE_NAME))
        except AppError as exc:
            return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))
        if actor and actor.client_id and not _app_may_call(request.method, request.url.path, settings.api_prefix):
            return JSONResponse(status_code=403, content=error_body("forbidden", "Not available to connected apps"))
        if actor:
            request.state.actor = actor
            request.state.username = settings.auth_username if actor.folio_user_id is None else None
        if request.method == "OPTIONS" or _is_public_path(request.url.path):
            return await call_next(request)
        if actor is None:
            return JSONResponse(
                status_code=401,
                content=error_body("unauthorized", "Требуется вход"),
            )
        if actor.session_id and request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            if origin and origin.rstrip("/") not in {str(request.base_url).rstrip("/"), *settings.cors_origin_list}:
                return JSONResponse(status_code=403, content=error_body("forbidden", "Invalid request origin"))
        return await call_next(request)
