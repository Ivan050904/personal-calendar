"""Read API v2 beyond single records (wave 5): agenda, one occurrence, «было/не было» history,
confirmations and the reminder source. Same data as /integration/v1, with the per-app calendar rules."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.routes import integration as v1
from app.api.routes.entities_v2 import KINDS, SECTIONS, can_read, external_ids
from app.application.agenda import build_agenda
from app.application.calendar_history import history_page
from app.core.calendar_actor import CalendarActor, require_actor, require_owned_calendar, require_scope
from app.core.errors import AppError
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/v2', tags=['reads'])
READER_SCOPES = frozenset({'calendar:read', 'calendar:reminders', 'calendar:history'})


def _reader(actor: CalendarActor) -> CalendarActor:
    """The v1 helpers check internal scopes; app rules are enforced by the caller first."""
    return CalendarActor(actor.principal_id, None, READER_SCOPES) if actor.client_id else actor


def _check_entity(db: Session, actor: CalendarActor, entity_id: str) -> None:
    row = next((r for r in (db.get(model, entity_id) for _, model in KINDS.values()) if r is not None), None)
    if row is None:
        raise AppError('not_found', 'Not found', status_code=404)
    require_owned_calendar(db, actor, row.calendar_id)
    can_read(actor, row.calendar_id)


@router.get('/agenda')
def agenda(calendar_id: str, from_day: date = Query(alias='from'), to_day: date = Query(alias='to'),
           timezone: str | None = None, cursor: str | None = None, limit: int = Query(default=500, ge=1, le=500),
           db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    can_read(actor, calendar_id)
    cal = require_owned_calendar(db, actor, calendar_id)
    page = build_agenda(db, actor, cal.id, from_day, to_day, timezone or cal.timezone, cursor=cursor, limit=limit)
    for section in SECTIONS:
        page[section] = external_ids(db, page[section])
    return page


@router.get('/occurrences/{entity_id}')
def occurrence(entity_id: str, occurrence_key: str | None = None,
               db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _check_entity(db, actor, entity_id)
    return v1.occurrence(entity_id, occurrence_key, db, _reader(actor))


@router.get('/confirmations/{entity_id}')
def confirmation(entity_id: str, occurrence_key: str | None = None,
                 db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _check_entity(db, actor, entity_id)
    return v1.confirmation(entity_id, occurrence_key, db, _reader(actor))


@router.get('/history')
def history(from_day: date = Query(alias='from'), to_day: date = Query(alias='to'), cursor: str | None = None,
            limit: int = Query(default=100, ge=1, le=100),
            db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    if actor.client_id:
        require_scope(actor, 'events.read')
        return history_page(db, _reader(actor), from_day, to_day, cursor, limit, actor.readable_calendar_ids)
    require_scope(actor, 'calendar:history')
    return history_page(db, actor, from_day, to_day, cursor, limit)


@router.get('/reminder-source')
def reminder_source(calendar_id: str, from_day: date = Query(alias='from'), to_day: date = Query(alias='to'),
                    cursor: str | None = None, db: Session = Depends(get_db),
                    actor: CalendarActor = Depends(require_actor)):
    can_read(actor, calendar_id)
    return v1.reminder_source(from_day, to_day, cursor, calendar_id, db, _reader(actor))
