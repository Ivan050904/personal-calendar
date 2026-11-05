"""Calendar accounts API v2 (D34, wave 1)."""
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.accounts import account_read, change_password, create_account, revoke_sessions
from app.core.auth import set_session_cookie
from app.core.calendar_actor import CalendarActor, require_actor
from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.db.auth_sessions import create_session
from app.infrastructure.db.models import CalendarPrincipalModel
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/v2', tags=['accounts'])


class RegisterBody(BaseModel):
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)
    display_name: str | None = Field(default=None, max_length=255)
    timezone: str = Field(default='UTC', max_length=64)


class PasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def require_session_actor(actor: CalendarActor = Depends(require_actor)) -> CalendarActor:
    # Account management is for the person in the calendar UI, never for a connected app.
    if not actor.session_id:
        raise AppError('forbidden', 'Session login is required', status_code=403)
    return actor


@router.post('/accounts', status_code=201)
def register(body: RegisterBody, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.registration_enabled:
        raise AppError('unavailable', 'Регистрация пока закрыта', status_code=503)
    principal = create_account(db, body.login, body.password, body.display_name, body.timezone)
    token, _ = create_session(db, principal)
    db.commit()
    set_session_cookie(response, token, secure=settings.app_env == 'production')
    return account_read(principal)


@router.get('/me')
def me(db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    row = db.get(CalendarPrincipalModel, actor.principal_id)
    if row is None:
        raise AppError('not_found', 'Account not found', status_code=404)
    return account_read(row)


@router.post('/me/password')
def set_password(body: PasswordBody, db: Session = Depends(get_db),
                 actor: CalendarActor = Depends(require_session_actor)):
    change_password(db, actor.principal_id, body.current_password, body.new_password, actor.session_id)
    db.commit()
    return {'ok': True}


@router.get('/grants')
def grants(db: Session = Depends(get_db), actor: CalendarActor = Depends(require_session_actor)):
    from sqlalchemy import select
    from app.application.oauth import grant_read
    from app.infrastructure.db.models import OAuthGrantModel
    rows = db.scalars(select(OAuthGrantModel).where(OAuthGrantModel.principal_id == actor.principal_id,
                                                    OAuthGrantModel.revoked_at.is_(None)))
    return [grant_read(db, row) for row in rows]


@router.delete('/grants/{grant_id}')
def revoke_grant(grant_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(require_session_actor)):
    from app.application.oauth import revoke_grant as revoke
    from app.infrastructure.db.models import OAuthGrantModel
    row = db.get(OAuthGrantModel, grant_id)
    if row is None or row.principal_id != actor.principal_id or row.revoked_at is not None:
        raise AppError('not_found', 'Connection not found', status_code=404)
    revoke(db, row)
    db.commit()
    return {'id': grant_id, 'revoked': True}


@router.post('/me/sessions/revoke-others')
def revoke_other_sessions(db: Session = Depends(get_db), actor: CalendarActor = Depends(require_session_actor)):
    revoked = revoke_sessions(db, actor.principal_id, actor.session_id)
    db.commit()
    return {'revoked': revoked}
