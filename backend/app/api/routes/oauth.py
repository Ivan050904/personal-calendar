"""OAuth 2.0 endpoints and the server-rendered login / consent pages (D35, wave 3).

Mounted under the API prefix (`/api/oauth/*`) because the edge proxy sends only `/api` to the backend.
"""
import base64
import hashlib
import hmac
import secrets
from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.application import oauth
from app.application.accounts import account_read, authenticate, normalize_login
from app.core import login_rate_limit
from app.core.auth import set_session_cookie
from app.core.calendar_actor import CalendarActor, require_actor, require_scope
from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.db.auth_sessions import create_session
from app.infrastructure.db.models import CalendarPrincipalModel
from app.infrastructure.db.session import get_db

router = APIRouter(tags=['oauth'])

AUTHORIZE_PARAMS = ('response_type', 'client_id', 'redirect_uri', 'scope', 'state', 'code_challenge', 'code_challenge_method')
# same-origin, not no-referrer: with no-referrer browsers post the forms with `Origin: null`,
# which the cross-site check rightly rejects. Cross-site requests still get no referrer.
PAGE_HEADERS = {'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store', 'Referrer-Policy': 'same-origin',
                'Content-Security-Policy': "frame-ancestors 'none'; default-src 'none'; style-src 'unsafe-inline'"}
_fallback_secret = secrets.token_bytes(32)


def _csrf(session_id: str) -> str:
    key = (get_settings().auth_session_secret or '').encode() or _fallback_secret
    return hmac.new(key, ('oauth-consent:' + session_id).encode(), hashlib.sha256).hexdigest()


def _page(title: str, body: str, status: int = 200) -> HTMLResponse:
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)}</title>
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:#f6f1ef;color:#2b2326;display:flex;justify-content:center;padding:24px 16px}}
main{{max-width:420px;width:100%;background:#fff;border-radius:14px;padding:24px;box-shadow:0 2px 12px #0001}}
h1{{font-size:1.3rem;margin:0 0 12px}} p,li{{line-height:1.45}} label{{display:block;margin:10px 0}}
input[type=text],input[type=password]{{width:100%;box-sizing:border-box;padding:10px;border:1px solid #ccc;border-radius:8px;font-size:1rem}}
.row{{display:flex;gap:10px;margin-top:18px}} button{{flex:1;padding:11px;border-radius:8px;border:0;font-size:1rem;cursor:pointer}}
.primary{{background:#b44a6a;color:#fff}} .ghost{{background:#eee}} .err{{color:#b00020}} .muted{{color:#6b5d62;font-size:.9rem}}
</style></head><body><main>{body}</main></body></html>"""
    return HTMLResponse(html, status_code=status, headers=PAGE_HEADERS)


def _hidden(params: dict) -> str:
    return ''.join(f'<input type="hidden" name="{k}" value="{escape(params.get(k) or "")}">' for k in AUTHORIZE_PARAMS)


def _error_redirect(req_params: dict, error: oauth.OAuthError) -> RedirectResponse:
    query = urlencode({'error': error.error, 'error_description': error.description, 'state': req_params.get('state') or ''})
    return RedirectResponse(f"{req_params['redirect_uri']}?{query}", status_code=303)


def _session_actor(request: Request) -> CalendarActor | None:
    actor = getattr(request.state, 'actor', None)
    return actor if actor is not None and actor.session_id else None


def _login_page(params: dict, error: str | None = None, status: int = 200) -> HTMLResponse:
    message = f'<p class="err">{escape(error)}</p>' if error else ''
    return _page('Вход в Календарь', f"""<h1>Вход в Календарь</h1>
<p class="muted">Войдите в свой аккаунт календаря, чтобы подключить приложение.</p>{message}
<form method="post" action="login">{_hidden(params)}
<label>Логин<input type="text" name="login" autocomplete="username" required></label>
<label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
<div class="row"><button class="primary" type="submit">Войти</button></div></form>""", status)


def _consent_page(db: Session, actor: CalendarActor, req: oauth.AuthorizeRequest, params: dict) -> HTMLResponse:
    principal = db.get(CalendarPrincipalModel, actor.principal_id)
    who = escape(principal.login or principal.display_name or '') if principal else ''
    name = escape(req.client.name)
    items = ''.join(f'<li>{escape(oauth.SCOPE_TEXT[s].format(app=req.client.name))}</li>' for s in req.scopes)
    picker = ''
    if oauth.READ_SCOPES & set(req.scopes):
        grant = oauth.active_grant(db, actor.principal_id, req.client.id)
        chosen = set(grant.readable_calendar_ids) if grant else set()
        rows = ''.join(
            f'<label><input type="checkbox" name="calendar_ids" value="{escape(c.id)}"{" checked" if c.id in chosen else ""}> '
            f'{escape(c.name)}</label>'
            for c in oauth.owned_calendars(db, actor.principal_id) if c.source_client_id != req.client.id)
        own = f'<p class="muted">Свой календарь «{name}» приложение видит всегда.</p>' if 'events.write' in req.scopes else ''
        picker = f'<p><b>Какие календари показать приложению:</b></p>{rows}{own}'
    return _page('Подключение приложения', f"""<h1>«{name}» хочет доступ к вашему календарю</h1>
<p class="muted">Аккаунт: {who}</p><p>Приложение сможет:</p><ul>{items}</ul>
<form method="post" action="authorize">{_hidden(params)}<input type="hidden" name="csrf" value="{_csrf(actor.session_id)}">
{picker}<div class="row"><button class="ghost" type="submit" name="decision" value="deny">Отмена</button>
<button class="primary" type="submit" name="decision" value="allow">Разрешить</button></div></form>
<p class="muted">Отключить приложение можно в любой момент: Настройки → Подключённые приложения.</p>""")


def _approve_and_redirect(db: Session, actor: CalendarActor, req: oauth.AuthorizeRequest, chosen: list[str] | None):
    grant = oauth.approve(db, actor.principal_id, req, chosen)
    code = oauth.issue_code(db, grant, req)
    db.commit()
    return RedirectResponse(f"{req.redirect_uri}?{urlencode({'code': code, 'state': req.state})}", status_code=303)


@router.get('/oauth/authorize')
def authorize(request: Request, db: Session = Depends(get_db)):
    params = {k: request.query_params.get(k) for k in AUTHORIZE_PARAMS}
    try:
        req = oauth.parse_authorize(db, params)
    except oauth.OAuthError as exc:
        if not exc.redirectable:
            return _page('Ошибка подключения', f'<h1>Подключение невозможно</h1><p class="err">{escape(exc.description)}</p>', 400)
        return _error_redirect(params, exc)
    actor = _session_actor(request)
    if actor is None:
        return _login_page(params)
    if not oauth.needs_consent(db, actor.principal_id, req):
        return _approve_and_redirect(db, actor, req, None)
    return _consent_page(db, actor, req, params)


@router.post('/oauth/authorize')
async def authorize_decision(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    params = {k: form.get(k) for k in AUTHORIZE_PARAMS}
    try:
        req = oauth.parse_authorize(db, params)
    except oauth.OAuthError as exc:
        if not exc.redirectable:
            return _page('Ошибка подключения', f'<h1>Подключение невозможно</h1><p class="err">{escape(exc.description)}</p>', 400)
        return _error_redirect(params, exc)
    actor = _session_actor(request)
    if actor is None:
        return _login_page(params, 'Сессия истекла, войдите снова', 401)
    if not secrets.compare_digest(str(form.get('csrf') or ''), _csrf(actor.session_id)):
        return _page('Ошибка подключения', '<h1>Подключение невозможно</h1><p class="err">Форма устарела, начните заново.</p>', 403)
    if form.get('decision') != 'allow':
        return _error_redirect(params, oauth.OAuthError('access_denied', 'The user declined'))
    chosen = [str(v) for v in form.getlist('calendar_ids')] if oauth.READ_SCOPES & set(req.scopes) else []
    return _approve_and_redirect(db, actor, req, chosen)


@router.post('/oauth/login')
async def authorize_login(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    params = {k: form.get(k) for k in AUTHORIZE_PARAMS}
    try:
        oauth.parse_authorize(db, params)  # never log in on behalf of an unregistered client / redirect
    except oauth.OAuthError as exc:
        if not exc.redirectable:
            return _page('Ошибка подключения', f'<h1>Подключение невозможно</h1><p class="err">{escape(exc.description)}</p>', 400)
    key, ip = normalize_login(str(form.get('login') or '')), request.client.host if request.client else 'unknown'
    try:
        login_rate_limit.check(key, ip)
    except AppError as exc:
        return _login_page(params, exc.message, 429)
    principal = authenticate(db, key, str(form.get('password') or ''))
    if principal is None:
        login_rate_limit.record_failure(key, ip)
        return _login_page(params, 'Неверный логин или пароль', 401)
    login_rate_limit.record_success(key)
    token, _ = create_session(db, principal)
    db.commit()
    response = RedirectResponse('authorize?' + urlencode({k: v or '' for k, v in params.items()}), status_code=303)
    set_session_cookie(response, token, secure=get_settings().app_env == 'production')
    return response


def _token_error(exc: oauth.OAuthError) -> JSONResponse:
    headers = {'Cache-Control': 'no-store'}
    if exc.status == 401:
        headers['WWW-Authenticate'] = 'Basic realm="calendar"'
    return JSONResponse({'error': exc.error, 'error_description': exc.description}, status_code=exc.status, headers=headers)


def _client_credentials(request: Request, form) -> tuple[str | None, str | None]:
    header = request.headers.get('authorization', '')
    if header.lower().startswith('basic '):
        try:
            client_id, _, secret = base64.b64decode(header[6:]).decode().partition(':')
            return client_id, secret
        except (ValueError, UnicodeDecodeError):
            return None, None
    return form.get('client_id'), form.get('client_secret')


@router.post('/oauth/token')
async def token(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    client_id, secret = _client_credentials(request, form)
    ip = request.client.host if request.client else 'unknown'
    limiter_key = 'client:' + str(client_id or '')
    try:
        login_rate_limit.check(limiter_key, ip)
        client = oauth.authenticate_client(db, client_id, secret)
        grant_type = form.get('grant_type')
        if grant_type == 'authorization_code':
            body = oauth.exchange_code(db, client, str(form.get('code') or ''), str(form.get('redirect_uri') or ''),
                                       str(form.get('code_verifier') or ''))
        elif grant_type == 'refresh_token':
            body = oauth.refresh(db, client, str(form.get('refresh_token') or ''))
        else:
            raise oauth.OAuthError('unsupported_grant_type', 'Unsupported grant_type')
    except AppError as exc:
        return _token_error(oauth.OAuthError('slow_down', exc.message, status=429))
    except oauth.OAuthError as exc:
        db.commit()  # keep code-used / reuse-revocation effects
        login_rate_limit.record_failure(limiter_key, ip)
        return _token_error(exc)
    db.commit()
    return JSONResponse(body, headers={'Cache-Control': 'no-store', 'Pragma': 'no-cache'})


@router.post('/oauth/revoke')
async def revoke(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    client_id, secret = _client_credentials(request, form)
    try:
        client = oauth.authenticate_client(db, client_id, secret)
    except oauth.OAuthError as exc:
        return _token_error(exc)
    oauth.revoke_token(db, client, str(form.get('token') or ''))
    db.commit()
    return JSONResponse({}, headers={'Cache-Control': 'no-store'})


@router.get('/oauth/userinfo')
def userinfo(db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    require_scope(actor, 'openid')
    row = db.get(CalendarPrincipalModel, actor.principal_id)
    info = {'sub': actor.principal_id}
    if 'profile' in actor.scopes and row is not None:
        account = account_read(row)
        info.update(preferred_username=account['login'], name=account['display_name'])
    return info


@router.get('/.well-known/oauth-authorization-server')
def metadata(request: Request):
    base = str(request.base_url).rstrip('/') + get_settings().api_prefix
    return {'issuer': base, 'authorization_endpoint': base + '/oauth/authorize', 'token_endpoint': base + '/oauth/token',
            'revocation_endpoint': base + '/oauth/revoke', 'userinfo_endpoint': base + '/oauth/userinfo',
            'response_types_supported': ['code'], 'grant_types_supported': ['authorization_code', 'refresh_token'],
            'code_challenge_methods_supported': ['S256'], 'scopes_supported': list(oauth.SUPPORTED_SCOPES),
            'token_endpoint_auth_methods_supported': ['client_secret_basic', 'client_secret_post', 'none']}
