from __future__ import annotations

from fastapi import APIRouter, Request, Response
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
