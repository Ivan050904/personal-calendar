"""Events API v2 for the calendar UI and connected apps (D35/D36, wave 3).

Thin layer over the existing projection (build_agenda) and command executor; it only adds the
per-app rules: read only ticked calendars, write only into the app's own calendar.
"""
from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, Header, Query, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.application.agenda import build_agenda
from app.application.calendar_commands import execute_calendar_command
from app.application.occurrences import entity_read
from app.core.calendar_actor import CalendarActor, require_actor, require_owned_calendar, require_scope
from app.core.errors import AppError
from app.infrastructure.db.models import CalendarWriteReceiptModel, EventModel
from app.infrastructure.db.session import get_db
from app.schemas.calendar_commands import CalendarWriteRequest

router = APIRouter(prefix='/v2/events', tags=['events'])


def _can_read(actor: CalendarActor, calendar_id: str) -> None:
    if actor.client_id:
        require_scope(actor, 'events.read')
        if calendar_id not in actor.readable_calendar_ids:
            raise AppError('not_found', 'Calendar not found', status_code=404)
    else:
        require_scope(actor, 'calendar:read')


def _write_actor(actor: CalendarActor) -> CalendarActor:
    """The executor checks the internal write scope; app rules are enforced before this point."""
    if actor.client_id:
        require_scope(actor, 'events.write')
        if actor.app_calendar_id is None:
            raise AppError('forbidden', 'Write access was withdrawn: reconnect the app', status_code=403)
        # Keeps client_id so the changes feed records which app made the change.
        return CalendarActor(actor.principal_id, None, frozenset({'calendar:write'}), client_id=actor.client_id)
    require_scope(actor, 'calendar:write')
    return actor


def _owned_event(db: Session, actor: CalendarActor, event_id: str) -> EventModel:
    row = db.get(EventModel, event_id)
    if row is None or row.deleted_at is not None:
        raise AppError('not_found', 'Event not found', status_code=404)
    require_owned_calendar(db, actor, row.calendar_id)
    _can_read(actor, row.calendar_id)
    return row


def _command(db: Session, actor: CalendarActor, body: dict, commit: bool = True):
    try:
        request = CalendarWriteRequest.model_validate(body)
    except ValidationError as exc:
        raise AppError('validation_error', 'Invalid event', status_code=422,
                       details={'errors': [e['msg'] for e in exc.errors()]}) from None
    result = execute_calendar_command(db, actor, request)
    if commit:
        db.commit()
    return result['entity']


def _revision(if_match: str | None) -> int:
    try:
        return int((if_match or '').strip('"W/ '))
    except ValueError:
        raise AppError('validation_error', 'If-Match: <revision> is required', status_code=428) from None


def _command_id(key: str | None) -> str:
    try:
        return str(UUID(key)) if key else str(uuid4())
    except ValueError:
        raise AppError('validation_error', 'Idempotency-Key must be a UUID', status_code=422) from None


@router.get('')
def index(calendar_id: str, from_day: date = Query(alias='from'), to_day: date = Query(alias='to'),
          timezone: str | None = None, cursor: str | None = None, limit: int = Query(default=500, ge=1, le=500),
          db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _can_read(actor, calendar_id)
    cal = require_owned_calendar(db, actor, calendar_id)
    page = build_agenda(db, actor, cal.id, from_day, to_day, timezone or cal.timezone, cursor=cursor, limit=limit)
    items = [i for i in page['items'] if i['kind'] == 'event']
    ids = {i['entity_id'] for i in items}
    external = dict(db.execute(select(EventModel.id, EventModel.external_id).where(EventModel.id.in_(ids))).all()) if ids else {}
    return {'calendar_id': cal.id, 'items': [{**i, 'external_id': external.get(i['entity_id'])} for i in items],
            'complete': page['complete'], 'next_cursor': page['next_cursor']}


@router.get('/{event_id}')
def show(event_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    row = _owned_event(db, actor, event_id)
    return {**entity_read(db, actor, row, 'event'), 'external_id': row.external_id}


def _with_external(db: Session, entity: dict) -> dict:
    row = db.get(EventModel, entity['id'])
    return {**entity, 'external_id': row.external_id if row else None}


def _external_id(actor: CalendarActor, payload: dict) -> str | None:
    value = payload.pop('external_id', None)
    if value is None:
        return None
    if not actor.client_id:
        raise AppError('validation_error', 'external_id is set only by connected apps', status_code=422)
    if not isinstance(value, str) or not 1 <= len(value) <= 255:
        raise AppError('validation_error', 'external_id must be a string of 1–255 characters', status_code=422)
    return value


@router.post('', status_code=201)
def create(response: Response, payload: dict = Body(...), calendar_id: str | None = Query(default=None),
           idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
           if_match: str | None = Header(default=None, alias='If-Match'),
           db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    writer = _write_actor(actor)
    target = actor.app_calendar_id if actor.client_id else calendar_id
    if actor.client_id and calendar_id not in (None, actor.app_calendar_id):
        raise AppError('forbidden', 'Apps write only into their own calendar', status_code=403)
    external_id = _external_id(actor, payload)
    command_id = _command_id(idempotency_key)
    replay = db.get(CalendarWriteReceiptModel, (actor.principal_id, command_id)) is not None
    if external_id and not replay:
        # D37: sending the same external_id again updates that event instead of creating a twin.
        existing = db.scalar(select(EventModel).where(EventModel.calendar_id == target,
                                                      EventModel.source_client_id == actor.client_id,
                                                      EventModel.external_id == external_id))
        if existing is not None:
            if existing.deleted_at is not None:
                raise AppError('conflict', 'The event with this external_id was deleted in the calendar',
                               status_code=409, details={'entity_id': existing.id, 'deleted': True})
            response.status_code = 200
            return _with_external(db, _command(db, writer, {
                'command_id': command_id, 'kind': 'event', 'operation': 'patch', 'entity_id': existing.id,
                'expected_revision': _revision(if_match) if if_match else existing.revision, 'payload': payload,
                'scope': 'series' if existing.recurrence_rule_id else None}))
    body = {'command_id': command_id, 'kind': 'event', 'operation': 'create', 'payload': payload}
    if target:
        body['calendar_id'] = target
    entity = _command(db, writer, body, commit=False)
    if external_id and not replay:
        row = db.get(EventModel, entity['id'])
        row.source_client_id, row.external_id = actor.client_id, external_id
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise AppError('conflict', 'The same external_id is being created concurrently; retry', status_code=409) from None
    db.commit()
    return _with_external(db, entity)


def _mutate(db: Session, actor: CalendarActor, event_id: str, operation: Literal['patch', 'delete'], payload: dict,
            if_match: str | None, idempotency_key: str | None, occurrence_key: str | None, scope: str | None):
    writer = _write_actor(actor)
    row = _owned_event(db, actor, event_id)
    if actor.client_id and row.calendar_id != actor.app_calendar_id:
        raise AppError('forbidden', 'Apps change only events in their own calendar', status_code=403)
    return _with_external(db, _command(db, writer, {
        'command_id': _command_id(idempotency_key), 'kind': 'event', 'operation': operation, 'entity_id': row.id,
        'expected_revision': _revision(if_match), 'payload': payload, 'occurrence_key': occurrence_key, 'scope': scope}))


@router.patch('/{event_id}')
def patch(event_id: str, payload: dict = Body(...), occurrence_key: str | None = None,
          scope: Literal['this', 'thisAndFollowing', 'series'] | None = None,
          if_match: str | None = Header(default=None, alias='If-Match'),
          idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
          db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    return _mutate(db, actor, event_id, 'patch', payload, if_match, idempotency_key, occurrence_key, scope)


@router.delete('/{event_id}')
def delete(event_id: str, occurrence_key: str | None = None,
           scope: Literal['this', 'thisAndFollowing', 'series'] | None = None,
           if_match: str | None = Header(default=None, alias='If-Match'),
           idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
           db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _mutate(db, actor, event_id, 'delete', {}, if_match, idempotency_key, occurrence_key, scope)
    return {'id': event_id, 'deleted': True}
