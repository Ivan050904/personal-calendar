"""OAuth 2.0 Authorization Code + PKCE server for connected apps (D35, wave 3).

Codes and tokens are random strings with a recognisable prefix; only their SHA-256 is stored.
"""
import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.calendar_actor import CalendarActor
from app.infrastructure.db import models as m

# Scopes this server can grant today. freebusy.read and sharing.invite arrive with their waves.
SUPPORTED_SCOPES = ("openid", "profile", "calendars.read", "events.read", "events.write")
SCOPE_TEXT = {
    "openid": "узнать ваш аккаунт календаря",
    "profile": "видеть ваш логин и имя",
    "calendars.read": "видеть список выбранных календарей",
    "events.read": "читать события в выбранных календарях",
    "events.write": "создавать, менять и удалять события в своём календаре «{app}»",
}
READ_SCOPES = {"calendars.read", "events.read"}

CODE_TTL = timedelta(seconds=60)
ACCESS_TTL = timedelta(minutes=15)
REFRESH_TTL = timedelta(days=30)
APP_CALENDAR_COLOR = "#7c3aed"
PKCE_RE = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")


class OAuthError(Exception):
    """RFC 6749 error; `redirectable` errors go back to the client's redirect_uri."""

    def __init__(self, error: str, description: str, status: int = 400, redirectable: bool = True):
        super().__init__(description)
        self.error, self.description, self.status, self.redirectable = error, description, status, redirectable


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _new(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(32)


def validate_redirect_uri(uri: str) -> str:
    parts = urlsplit(uri)
    local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
    if parts.fragment or not parts.netloc or not (parts.scheme == "https" or (parts.scheme == "http" and local)):
        raise ValueError(f"redirect_uri must be https (http only for localhost), no fragment: {uri}")
    return uri


# --- Authorization request -------------------------------------------------

@dataclass(frozen=True)
class AuthorizeRequest:
    client: m.OAuthClientModel
    redirect_uri: str
    scopes: tuple[str, ...]
    state: str
    code_challenge: str


def parse_authorize(db: Session, params: dict) -> AuthorizeRequest:
    client = db.get(m.OAuthClientModel, params.get("client_id") or "")
    redirect_uri = params.get("redirect_uri") or ""
    if client is None or not client.active:
        raise OAuthError("invalid_client", "Приложение не зарегистрировано в календаре", redirectable=False)
    if redirect_uri not in client.redirect_uris:
        raise OAuthError("invalid_request", "Адрес возврата не совпадает с зарегистрированным", redirectable=False)
    state = params.get("state") or ""
    if not state or len(state) > 512:
        raise OAuthError("invalid_request", "state is required")
    if params.get("response_type") != "code":
        raise OAuthError("unsupported_response_type", "Only response_type=code")
    challenge = params.get("code_challenge") or ""
    if params.get("code_challenge_method") != "S256" or not PKCE_RE.fullmatch(challenge):
        raise OAuthError("invalid_request", "PKCE S256 code_challenge is required")
    requested = tuple(dict.fromkeys((params.get("scope") or "").split()))
    allowed = set(client.allowed_scopes) & set(SUPPORTED_SCOPES)
    if not requested or not set(requested) <= allowed:
        raise OAuthError("invalid_scope", "Requested scope is not allowed for this app")
    return AuthorizeRequest(client, redirect_uri, requested, state, challenge)


def active_grant(db: Session, principal_id: str, client_id: str) -> m.OAuthGrantModel | None:
    return db.scalar(select(m.OAuthGrantModel).where(m.OAuthGrantModel.principal_id == principal_id,
                                                     m.OAuthGrantModel.client_id == client_id,
                                                     m.OAuthGrantModel.revoked_at.is_(None)))


def _live_calendar(db: Session, principal_id: str, calendar_id: str | None) -> m.CalendarModel | None:
    row = db.get(m.CalendarModel, calendar_id) if calendar_id else None
    return row if row is not None and row.owner_id == principal_id and row.deleted_at is None else None


def needs_consent(db: Session, principal_id: str, req: AuthorizeRequest) -> bool:
    grant = active_grant(db, principal_id, req.client.id)
    if grant is None or not set(req.scopes) <= set(grant.scopes):
        return True
    # A deleted app calendar means the user withdrew write access: ask again.
    return "events.write" in req.scopes and _live_calendar(db, principal_id, grant.app_calendar_id) is None


def owned_calendars(db: Session, principal_id: str) -> list[m.CalendarModel]:
    return list(db.scalars(select(m.CalendarModel).where(m.CalendarModel.owner_id == principal_id,
                                                         m.CalendarModel.deleted_at.is_(None))))


def approve(db: Session, principal_id: str, req: AuthorizeRequest, chosen_calendar_ids: list[str] | None) -> m.OAuthGrantModel:
    """Create or widen the grant after the user pressed «Разрешить»."""
    grant = active_grant(db, principal_id, req.client.id)
    if grant is None:
        grant = m.OAuthGrantModel(id=str(uuid4()), principal_id=principal_id, client_id=req.client.id, scopes=[],
                                  readable_calendar_ids=[])
        db.add(grant)
    grant.scopes = sorted(set(grant.scopes) | set(req.scopes))
    if "events.write" in req.scopes and _live_calendar(db, principal_id, grant.app_calendar_id) is None:
        # Reconnecting after a revoke reuses the app's surviving calendar instead of making a twin.
        grant.app_calendar_id = db.scalar(select(m.CalendarModel.id).where(
            m.CalendarModel.owner_id == principal_id, m.CalendarModel.kind == "app",
            m.CalendarModel.source_client_id == req.client.id, m.CalendarModel.deleted_at.is_(None)))
    if "events.write" in req.scopes and grant.app_calendar_id is None:
        personal = db.scalar(select(m.CalendarModel).where(m.CalendarModel.default_owner == principal_id,
                                                           m.CalendarModel.deleted_at.is_(None)))
        app_calendar = m.CalendarModel(id=str(uuid4()), name=req.client.name, owner_id=principal_id, kind="app",
                                       source_client_id=req.client.id, color=APP_CALENDAR_COLOR,
                                       timezone=personal.timezone if personal else "UTC", visible=True, sort_order=0)
        db.add(app_calendar)
        db.flush()
        grant.app_calendar_id = app_calendar.id
    if chosen_calendar_ids is not None:
        owned = {row.id for row in owned_calendars(db, principal_id)}
        grant.readable_calendar_ids = sorted(set(chosen_calendar_ids) & owned)
    db.flush()
    return grant


def issue_code(db: Session, grant: m.OAuthGrantModel, req: AuthorizeRequest) -> str:
    code = _new("pcc_")
    db.add(m.OAuthAuthorizationCodeModel(code_hash=digest(code), grant_id=grant.id, client_id=req.client.id,
                                         redirect_uri=req.redirect_uri, code_challenge=req.code_challenge,
                                         expires_at=datetime.utcnow() + CODE_TTL))
    db.flush()
    return code


# --- Token endpoint --------------------------------------------------------

def authenticate_client(db: Session, client_id: str | None, client_secret: str | None) -> m.OAuthClientModel:
    client = db.get(m.OAuthClientModel, client_id or "")
    if client is None or not client.active:
        raise OAuthError("invalid_client", "Unknown client", status=401)
    if client.client_type == "confidential":
        if not client_secret or not secrets.compare_digest(digest(client_secret), client.secret_hash or ""):
            raise OAuthError("invalid_client", "Client authentication failed", status=401)
    elif client_secret:
        raise OAuthError("invalid_client", "Public clients have no secret", status=401)
    return client


def revoke_grant(db: Session, grant: m.OAuthGrantModel) -> None:
    now = datetime.utcnow()
    grant.revoked_at = grant.revoked_at or now
    db.execute(update(m.OAuthTokenModel).where(m.OAuthTokenModel.grant_id == grant.id,
                                               m.OAuthTokenModel.revoked_at.is_(None)).values(revoked_at=now))
    db.flush()


def _issue_tokens(db: Session, grant: m.OAuthGrantModel) -> tuple[dict, str]:
    now = datetime.utcnow()
    access, refresh = _new("pca_"), _new("pcr_")
    db.add(m.OAuthTokenModel(token_hash=digest(access), grant_id=grant.id, kind="access", expires_at=now + ACCESS_TTL))
    db.add(m.OAuthTokenModel(token_hash=digest(refresh), grant_id=grant.id, kind="refresh", expires_at=now + REFRESH_TTL))
    db.flush()
    body = {"access_token": access, "token_type": "Bearer", "expires_in": int(ACCESS_TTL.total_seconds()),
            "refresh_token": refresh, "scope": " ".join(grant.scopes)}
    return body, digest(refresh)


def exchange_code(db: Session, client: m.OAuthClientModel, code: str, redirect_uri: str, verifier: str) -> dict:
    row = db.get(m.OAuthAuthorizationCodeModel, digest(code or ""))
    if row is None or row.client_id != client.id:
        raise OAuthError("invalid_grant", "Invalid authorization code")
    grant = db.get(m.OAuthGrantModel, row.grant_id)
    if row.used_at is not None:
        # Replayed code: everything issued under this grant is suspect.
        revoke_grant(db, grant)
        raise OAuthError("invalid_grant", "Authorization code already used")
    row.used_at = datetime.utcnow()
    db.flush()
    if row.expires_at <= datetime.utcnow() or row.redirect_uri != redirect_uri or grant.revoked_at is not None:
        raise OAuthError("invalid_grant", "Invalid authorization code")
    if not PKCE_RE.fullmatch(verifier or ""):
        raise OAuthError("invalid_grant", "Invalid code_verifier")
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    if not secrets.compare_digest(expected, row.code_challenge):
        raise OAuthError("invalid_grant", "PKCE verification failed")
    return _issue_tokens(db, grant)[0]


def refresh(db: Session, client: m.OAuthClientModel, refresh_token: str) -> dict:
    row = db.get(m.OAuthTokenModel, digest(refresh_token or ""))
    grant = db.get(m.OAuthGrantModel, row.grant_id) if row is not None else None
    if row is None or row.kind != "refresh" or grant is None or grant.client_id != client.id:
        raise OAuthError("invalid_grant", "Invalid refresh token")
    if row.revoked_at is not None:
        if row.replaced_by is not None:
            # Rotation reuse: an old refresh token came back, so it leaked. Kill the whole grant.
            revoke_grant(db, grant)
        raise OAuthError("invalid_grant", "Invalid refresh token")
    if row.expires_at <= datetime.utcnow() or grant.revoked_at is not None:
        raise OAuthError("invalid_grant", "Invalid refresh token")
    body, new_hash = _issue_tokens(db, grant)
    row.revoked_at, row.replaced_by = datetime.utcnow(), new_hash
    db.flush()
    return body


def revoke_token(db: Session, client: m.OAuthClientModel, token: str) -> None:
    row = db.get(m.OAuthTokenModel, digest(token or ""))
    grant = db.get(m.OAuthGrantModel, row.grant_id) if row is not None else None
    if grant is not None and grant.client_id == client.id:
        revoke_grant(db, grant)


# --- Resource side ---------------------------------------------------------

def actor_for_access_token(db: Session, token: str) -> CalendarActor | None:
    row = db.get(m.OAuthTokenModel, digest(token))
    if row is None or row.kind != "access" or row.revoked_at is not None or row.expires_at <= datetime.utcnow():
        return None
    grant = db.get(m.OAuthGrantModel, row.grant_id)
    principal = db.get(m.CalendarPrincipalModel, grant.principal_id) if grant else None
    client = db.get(m.OAuthClientModel, grant.client_id) if grant else None
    if grant is None or grant.revoked_at is not None or principal is None or not principal.active or client is None or not client.active:
        return None
    now = datetime.utcnow()
    if grant.last_used_at is None or now - grant.last_used_at > timedelta(minutes=1):
        grant.last_used_at = now
        db.commit()
    app_calendar = _live_calendar(db, principal.id, grant.app_calendar_id)
    return CalendarActor(principal.id, None, frozenset(grant.scopes), None, client.id, grant.id,
                         grant_calendar_ids(db, grant), app_calendar.id if app_calendar else None)


def grant_calendar_ids(db: Session, grant: m.OAuthGrantModel) -> frozenset[str]:
    """Calendars this connection may read: the ticked ones plus the app's own, if they still exist."""
    ids = {cid for cid in [*grant.readable_calendar_ids, grant.app_calendar_id]
           if _live_calendar(db, grant.principal_id, cid)}
    return frozenset(ids)


def grant_read(db: Session, grant: m.OAuthGrantModel) -> dict:
    client = db.get(m.OAuthClientModel, grant.client_id)
    iso = lambda v: v.isoformat() + "Z" if v else None  # noqa: E731
    return {"id": grant.id, "client_id": grant.client_id, "client_name": client.name if client else grant.client_id,
            "scopes": grant.scopes, "readable_calendar_ids": grant.readable_calendar_ids,
            "app_calendar_id": grant.app_calendar_id, "created_at": iso(grant.created_at),
            "last_used_at": iso(grant.last_used_at)}
