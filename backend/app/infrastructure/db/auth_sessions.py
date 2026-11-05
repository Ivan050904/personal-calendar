import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.bridge_auth import SCOPES
from app.core.calendar_actor import CalendarActor
from app.infrastructure.db.models import CalendarPrincipalModel, CalendarSessionModel


def create_session(db, principal):
    token = secrets.token_urlsafe(32)
    row = CalendarSessionModel(id=str(uuid4()), token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               principal_id=principal.id, expires_at=datetime.utcnow()+timedelta(days=30))
    db.add(row)
    db.flush()
    return token, row


def read_actor_session(db, token):
    if not token:
        return None
    row = db.scalar(select(CalendarSessionModel).where(CalendarSessionModel.token_hash == hashlib.sha256(token.encode()).hexdigest()))
    if row is None or row.revoked_at or row.expires_at <= datetime.utcnow():
        return None
    principal = db.get(CalendarPrincipalModel, row.principal_id)
    if principal is None or not principal.active:
        return None
    return CalendarActor(principal.id, principal.folio_user_id, SCOPES, row.id)
