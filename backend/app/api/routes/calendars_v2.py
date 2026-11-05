"""Calendars API v2 (D36, wave 2)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.application.calendars import create_calendar, delete_calendar, list_calendars, patch_calendar
from app.core.calendar_actor import CalendarActor, require_actor, require_scope
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/v2/calendars', tags=['calendars'])


class CalendarCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(max_length=255)
    color: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)


class CalendarPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str | None = Field(default=None, max_length=255)
    color: str | None = Field(default=None, max_length=16)
    visible: bool | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100000)


def reader(actor: CalendarActor = Depends(require_actor)) -> CalendarActor:
    require_scope(actor, 'calendar:read')
    return actor


def writer(actor: CalendarActor = Depends(require_actor)) -> CalendarActor:
    require_scope(actor, 'calendar:write')
    return actor


@router.get('')
def index(db: Session = Depends(get_db), actor: CalendarActor = Depends(reader)):
    return list_calendars(db, actor)


@router.post('', status_code=201)
def create(body: CalendarCreate, db: Session = Depends(get_db), actor: CalendarActor = Depends(writer)):
    result = create_calendar(db, actor, body.name, body.color, body.timezone)
    db.commit()
    return result


@router.patch('/{calendar_id}')
def patch(calendar_id: str, body: CalendarPatch, db: Session = Depends(get_db), actor: CalendarActor = Depends(writer)):
    result = patch_calendar(db, actor, calendar_id, body.model_dump(exclude_unset=True, exclude_none=True))
    db.commit()
    return result


@router.delete('/{calendar_id}')
def delete(calendar_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(writer)):
    result = delete_calendar(db, actor, calendar_id)
    db.commit()
    return result
