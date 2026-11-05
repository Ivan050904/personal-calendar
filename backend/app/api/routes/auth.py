from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.accounts import authenticate, find_by_login, normalize_login
from app.core import login_rate_limit
from app.core.auth import clear_session_cookie, passwords_match, set_session_cookie
from app.core.bridge_auth import SCOPES, exchange_folio_launch, principal_id, safe_launch_target
from app.core.calendar_actor import CalendarActor, ensure_actor_calendar, require_owned_calendar
from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.db.auth_sessions import create_session
from app.infrastructure.db.models import CalendarPrincipalModel, CalendarSessionModel
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/auth', tags=['auth'])

class LoginBody(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)

@router.post('/login')
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    settings = get_settings()
    key, ip = normalize_login(body.username), request.client.host if request.client else 'unknown'
    login_rate_limit.check(key, ip)
    if find_by_login(db, key) is not None:
        # Own account (D34): never falls through to the env legacy login for the same name.
        principal = authenticate(db, key, body.password)
        if principal is None:
            login_rate_limit.record_failure(key, ip)
            raise AppError('unauthorized', 'Неверный логин или пароль', status_code=401)
        login_rate_limit.record_success(key)
        token, _ = create_session(db, principal)
        db.commit()
        set_session_cookie(response, token, secure=settings.app_env == 'production')
        return {'ok': True, 'username': principal.login}
    try:
        return _legacy_login(body, response, db, settings)
    except AppError as exc:
        if exc.status_code == 401:
            login_rate_limit.record_failure(key, ip)
        raise


def _legacy_login(body: LoginBody, response: Response, db: Session, settings):
    if not settings.legacy_auth_enabled or not settings.legacy_principal_id or not settings.auth_session_secret:
        raise AppError('unavailable', 'Verified legacy login is not configured', status_code=503)
    if body.username != settings.auth_username or not settings.auth_password or not passwords_match(body.password, settings.auth_password):
        raise AppError('unauthorized', 'Неверный логин или пароль', status_code=401)
    principal = db.get(CalendarPrincipalModel, settings.legacy_principal_id)
    if principal is None:
        principal = CalendarPrincipalModel(id=settings.legacy_principal_id, legacy_alias=body.username)
        db.add(principal)
        db.flush()
    if not principal.active:
        raise AppError('forbidden', 'Principal inactive', status_code=403)
    login_rate_limit.record_success(normalize_login(body.username))
    token, _ = create_session(db, principal)
    db.commit()
    set_session_cookie(response, token, secure=settings.app_env == 'production')
    return {'ok': True, 'username': body.username}

@router.post('/logout')
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    actor = getattr(request.state, 'actor', None)
    if actor and actor.session_id:
        row = db.get(CalendarSessionModel, actor.session_id)
        if row:
            row.revoked_at = datetime.utcnow()
            db.commit()
    clear_session_cookie(response)
    return {'ok': True}

@router.get('/me')
def me(request: Request, db: Session = Depends(get_db)):
    actor = getattr(request.state, 'actor', None)
    principal = db.get(CalendarPrincipalModel, actor.principal_id) if actor else None
    username = principal.login if principal is not None and principal.login else getattr(request.state, 'username', None)
    return {'authenticated': actor is not None, 'username': username,
            'principal_id': actor.principal_id if actor else None,
            'folio_user_id': actor.folio_user_id if actor else None,
            'session_id': actor.session_id if actor else None}

@router.get('/folio')
def folio_launch(request: Request, db: Session = Depends(get_db)):
    settings = get_settings()
    code = request.query_params.get('code', '')
    if not code:
        raise AppError('unauthorized', 'Launch code is required', status_code=401)
    launch = exchange_folio_launch(code, settings)
    actor = CalendarActor(principal_id(launch['folio_user_id']), launch['folio_user_id'], SCOPES)
    ensure_actor_calendar(db, actor, launch.get('timezone') or 'UTC', code)
    if launch.get('calendar_id'):
        require_owned_calendar(db, actor, launch['calendar_id'])
    target = safe_launch_target(launch.get('target'))
    principal = db.get(CalendarPrincipalModel, actor.principal_id)
    token, _ = create_session(db, principal)
    db.commit()
    response = RedirectResponse(target, status_code=302, headers={'Referrer-Policy':'no-referrer', 'Cache-Control':'no-store'})
    set_session_cookie(response, token, secure=settings.app_env == 'production')
    return response

@router.get('/sso')
def legacy_sso():
    raise AppError('unavailable', 'Legacy SSO disabled; use one-time launch', status_code=503)
