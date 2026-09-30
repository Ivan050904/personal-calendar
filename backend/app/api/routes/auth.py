from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from app.core.auth import (
    COOKIE_NAME,
    auth_configured,
    clear_session_cookie,
    issue_session_token,
    passwords_match,
    read_session_username,
    set_session_cookie,
)
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.folio_sso import decode_folio_jwt, folio_identity_allowed, parse_csv_set

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    authenticated: bool
    username: str | None = None


@router.post("/login")
def login(body: LoginBody, response: Response) -> dict[str, object]:
    settings = get_settings()
    if not auth_configured(settings.auth_username, settings.auth_password, settings.auth_session_secret):
        raise AppError(
            "validation_error",
            "Auth is not configured on the server",
            status_code=503,
        )
    if body.username != settings.auth_username or not passwords_match(body.password, settings.auth_password):
        raise AppError("unauthorized", "Неверный логин или пароль", status_code=401)

    token = issue_session_token(username=settings.auth_username, secret=settings.auth_session_secret)
    set_session_cookie(response, token, secure=settings.app_env == "production")
    return {"ok": True, "username": settings.auth_username}


@router.post("/logout")
def logout(response: Response) -> dict[str, object]:
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    settings = get_settings()
    if not auth_configured(settings.auth_username, settings.auth_password, settings.auth_session_secret):
        return MeResponse(authenticated=True, username=None)
    username = read_session_username(
        request.cookies.get(COOKIE_NAME),
        secret=settings.auth_session_secret,
    )
    if username is None or username != settings.auth_username:
        return MeResponse(authenticated=False, username=None)
    return MeResponse(authenticated=True, username=username)


@router.get("/sso")
def folio_sso(request: Request) -> Response:
    """Accept Folio-One JWT and issue calendar pc_session for the mapped single-user."""
    settings = get_settings()
    if not auth_configured(settings.auth_username, settings.auth_password, settings.auth_session_secret):
        raise AppError("validation_error", "Auth is not configured on the server", status_code=503)
    if not settings.folio_jwt_secret.strip():
        raise AppError("validation_error", "Folio SSO is not configured", status_code=503)

    token = request.query_params.get("access_token", "").strip()
    if not token:
        raise AppError("unauthorized", "access_token is required", status_code=401)

    payload = decode_folio_jwt(
        token,
        secret=settings.folio_jwt_secret,
        algorithm=settings.folio_jwt_algorithm or "HS256",
    )
    if payload is None:
        raise AppError("unauthorized", "Invalid Folio token", status_code=401)

    allowed_emails = parse_csv_set(settings.folio_sso_emails)
    allowed_ids = parse_csv_set(settings.folio_sso_user_ids)
    if not folio_identity_allowed(payload, allowed_emails=allowed_emails, allowed_user_ids=allowed_ids):
        raise AppError("forbidden", "Folio user is not linked to this calendar", status_code=403)

    session = issue_session_token(username=settings.auth_username, secret=settings.auth_session_secret)
    redirect_to = settings.folio_sso_redirect.strip() or "/"
    response = RedirectResponse(url=redirect_to, status_code=302)
    set_session_cookie(response, session, secure=settings.app_env == "production")
    return response
