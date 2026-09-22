from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.auth import COOKIE_NAME, auth_configured, read_session_username
from app.core.config import get_settings
from app.core.errors import error_body


def _is_public_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    return any(
        normalized.endswith(suffix)
        for suffix in ("/health", "/auth/login", "/auth/me", "/auth/logout", "/docs", "/openapi.json", "/redoc")
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if not auth_configured(settings.auth_username, settings.auth_password, settings.auth_session_secret):
            return await call_next(request)

        if request.method == "OPTIONS" or _is_public_path(request.url.path):
            return await call_next(request)

        username = read_session_username(
            request.cookies.get(COOKIE_NAME),
            secret=settings.auth_session_secret,
        )
        if username is None or username != settings.auth_username:
            return JSONResponse(
                status_code=401,
                content=error_body("unauthorized", "Требуется вход"),
            )
        request.state.username = username
        return await call_next(request)
