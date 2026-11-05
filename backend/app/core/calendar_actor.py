from dataclasses import dataclass
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.db.models import CalendarModel, CalendarPrincipalModel
from app.infrastructure.repositories import _iso


@dataclass(frozen=True)
class CalendarActor:
    principal_id: str
    folio_user_id: str | None
    scopes: frozenset[str]
    session_id: str | None = None


def require_actor(request: Request) -> CalendarActor:
    actor = getattr(request.state, "actor", None)
    if actor is None:
        raise AppError("unauthorized", "Требуется вход", status_code=401)
    return actor


def require_scope(actor: CalendarActor, scope: str) -> None:
    if scope not in actor.scopes:
        raise AppError("forbidden", "Calendar scope is required", status_code=403)


def require_owned_calendar(db: Session, actor: CalendarActor, calendar_id: str) -> CalendarModel:
    row = db.get(CalendarModel, calendar_id)
    if row is None or row.owner_id != actor.principal_id or row.deleted_at is not None:
        raise AppError("not_found", "Calendar not found", status_code=404)
    return row


def calendar_read(row: CalendarModel) -> dict:
    return {"id": row.id, "name": row.name, "owner_id": row.owner_id,
            "timezone": row.timezone, "revision": row.revision,
            "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}


def ensure_actor_calendar(db: Session, actor: CalendarActor, timezone: str, idempotency_key: str) -> dict:
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise AppError("validation_error", "Invalid timezone", status_code=422) from None
    # Unique folio identity and default_owner provide the concurrent onboarding boundary.
    principal = db.get(CalendarPrincipalModel, actor.principal_id)
    if principal is None:
        principal = CalendarPrincipalModel(id=actor.principal_id, folio_user_id=actor.folio_user_id)
        try:
            with db.begin_nested():
                db.add(principal)
                db.flush()
        except IntegrityError:
            principal = db.scalar(select(CalendarPrincipalModel).where(CalendarPrincipalModel.folio_user_id == actor.folio_user_id))
    if principal is None or not principal.active or principal.id != actor.principal_id:
        raise AppError("forbidden", "Principal is inactive or mismatched", status_code=403)
    row = db.scalar(select(CalendarModel).where(CalendarModel.default_owner == actor.principal_id))
    if row is None:
        try:
            with db.begin_nested():
                row = CalendarModel(id=str(uuid4()), name="Personal Calendar", timezone=timezone,
                                    owner_id=actor.principal_id, default_owner=actor.principal_id, kind="personal")
                db.add(row)
                db.flush()
        except IntegrityError:
            row = db.scalar(select(CalendarModel).where(CalendarModel.default_owner == actor.principal_id))
    if row is None:
        raise AppError("conflict", "Concurrent onboarding; retry", status_code=409)
    return calendar_read(row)
