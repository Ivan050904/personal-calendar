"""Several calendars per account (D36, wave 2)."""
import re
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.calendar_actor import CalendarActor, require_owned_calendar
from app.core.errors import AppError
from app.infrastructure.db.models import CalendarModel
from app.infrastructure.repositories import _iso

COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
KIND_ORDER = {"personal": 0, "user": 1, "app": 2}


def calendar_v2_read(row: CalendarModel) -> dict:
    return {"id": row.id, "name": row.name, "kind": row.kind, "color": row.color, "visible": row.visible,
            "sort_order": row.sort_order, "timezone": row.timezone, "source_client_id": row.source_client_id,
            "revision": row.revision, "created_at": _iso(row.created_at), "updated_at": _iso(row.updated_at)}


def _name(value: str) -> str:
    name = (value or "").strip()
    if not 1 <= len(name) <= 255:
        raise AppError("validation_error", "Название: от 1 до 255 символов", status_code=422)
    return name


def _color(value: str) -> str:
    if not COLOR_RE.fullmatch(value or ""):
        raise AppError("validation_error", "Цвет в формате #RRGGBB", status_code=422)
    return value.lower()


def list_calendars(db: Session, actor: CalendarActor) -> list[dict]:
    rows = db.scalars(select(CalendarModel).where(CalendarModel.owner_id == actor.principal_id,
                                                  CalendarModel.deleted_at.is_(None))).all()
    rows = sorted(rows, key=lambda r: (KIND_ORDER.get(r.kind, 9), r.sort_order, r.created_at or datetime.min, r.id))
    return [calendar_v2_read(r) for r in rows]


def create_calendar(db: Session, actor: CalendarActor, name: str, color: str | None = None,
                    timezone: str | None = None) -> dict:
    personal = db.scalar(select(CalendarModel).where(CalendarModel.default_owner == actor.principal_id,
                                                     CalendarModel.deleted_at.is_(None)))
    zone = timezone or (personal.timezone if personal else "UTC")
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise AppError("validation_error", "Invalid timezone", status_code=422) from None
    top = db.scalar(select(func.max(CalendarModel.sort_order)).where(CalendarModel.owner_id == actor.principal_id))
    row = CalendarModel(id=str(uuid4()), name=_name(name), timezone=zone, owner_id=actor.principal_id, kind="user",
                        color=_color(color or "#2563eb"), visible=True, sort_order=(top or 0) + 1)
    db.add(row)
    db.flush()
    return calendar_v2_read(row)


def patch_calendar(db: Session, actor: CalendarActor, calendar_id: str, changes: dict) -> dict:
    row = require_owned_calendar(db, actor, calendar_id)
    if "name" in changes:
        row.name = _name(changes["name"])
    if "color" in changes:
        row.color = _color(changes["color"])
    if "visible" in changes:
        row.visible = bool(changes["visible"])
    if "sort_order" in changes:
        row.sort_order = int(changes["sort_order"])
    row.revision += 1
    row.updated_at = datetime.utcnow()
    db.flush()
    return calendar_v2_read(row)


def delete_calendar(db: Session, actor: CalendarActor, calendar_id: str) -> dict:
    row = require_owned_calendar(db, actor, calendar_id)
    if row.kind == "personal" or row.default_owner is not None:
        raise AppError("conflict", "Календарь «Личное» удалить нельзя", status_code=409)
    # Soft delete like the rest of the calendar: entries stay in the DB but every read hides them.
    row.deleted_at = row.updated_at = datetime.utcnow()
    row.revision += 1
    db.flush()
    return {"id": row.id, "deleted": True}
