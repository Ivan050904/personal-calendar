"""Events, tasks and plans API v2 for the calendar UI and connected apps (D35–D37, waves 3–5).

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
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_db
from app.schemas.calendar_commands import CalendarWriteRequest

KINDS = {'events': ('event', m.EventModel), 'tasks': ('task', m.TaskModel), 'plans': ('plan', m.PlanModel)}
SECTIONS = ('items', 'overdue_tasks', 'undated_tasks')


def can_read(actor: CalendarActor, calendar_id: str) -> None:
    if actor.client_id:
        require_scope(actor, 'events.read')
        if calendar_id not in actor.readable_calendar_ids:
            raise AppError('not_found', 'Calendar not found', status_code=404)
    else:
        require_scope(actor, 'calendar:read')


def write_actor(actor: CalendarActor) -> CalendarActor:
    """The executor checks the internal write scope; app rules are enforced before this point."""
    if actor.client_id:
        require_scope(actor, 'events.write')
        if actor.app_calendar_id is None:
            raise AppError('forbidden', 'Write access was withdrawn: reconnect the app', status_code=403)
        # Keeps client_id so the changes feed records which app made the change.
        return CalendarActor(actor.principal_id, None, frozenset({'calendar:write'}), client_id=actor.client_id)
    require_scope(actor, 'calendar:write')
    return actor


def owned_row(db: Session, actor: CalendarActor, model, entity_id: str, deleted_ok: bool = False):
    row = db.get(model, entity_id)
    if row is None or (row.deleted_at is not None and not deleted_ok):
        raise AppError('not_found', 'Not found', status_code=404)
    require_owned_calendar(db, actor, row.calendar_id)
    can_read(actor, row.calendar_id)
    return row


def external_ids(db: Session, items: list[dict]) -> list[dict]:
    """Adds `external_id` to projected items of any kind."""
    known = {}
    for kind, model in KINDS.values():
        ids = {i['entity_id'] for i in items if i['kind'] == kind}
        if ids:
            known.update(db.execute(select(model.id, model.external_id).where(model.id.in_(ids))).all())
    return [{**i, 'external_id': known.get(i['entity_id'])} for i in items]


def _command(db: Session, actor: CalendarActor, body: dict, commit: bool = True):
    try:
        request = CalendarWriteRequest.model_validate(body)
    except ValidationError as exc:
        raise AppError('validation_error', 'Invalid request', status_code=422,
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


def _external_id(actor: CalendarActor, payload: dict) -> str | None:
    value = payload.pop('external_id', None)
    if value is None:
        return None
    if not actor.client_id:
        raise AppError('validation_error', 'external_id is set only by connected apps', status_code=422)
    if not isinstance(value, str) or not 1 <= len(value) <= 255:
        raise AppError('validation_error', 'external_id must be a string of 1–255 characters', status_code=422)
    return value


def build_router(path: str, kind: str, model) -> APIRouter:
    router = APIRouter(prefix=f'/v2/{path}', tags=[path])

    def with_external(db: Session, entity: dict) -> dict:
        row = db.get(model, entity['id'])
        return {**entity, 'external_id': row.external_id if row else None}

    def mutate(db, actor, entity_id, operation, payload, if_match, idempotency_key, occurrence_key=None, scope=None):
        writer = write_actor(actor)
        row = owned_row(db, actor, model, entity_id, deleted_ok=operation == 'restore')
        if actor.client_id and row.calendar_id != actor.app_calendar_id:
            raise AppError('forbidden', 'Apps change only records in their own calendar', status_code=403)
        return with_external(db, _command(db, writer, {
            'command_id': _command_id(idempotency_key), 'kind': kind, 'operation': operation, 'entity_id': row.id,
            'expected_revision': _revision(if_match), 'payload': payload, 'occurrence_key': occurrence_key,
            'scope': scope}))

    @router.get('')
    def index(calendar_id: str, from_day: date = Query(alias='from'), to_day: date = Query(alias='to'),
              timezone: str | None = None, cursor: str | None = None, limit: int = Query(default=500, ge=1, le=500),
              db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        can_read(actor, calendar_id)
        cal = require_owned_calendar(db, actor, calendar_id)
        page = build_agenda(db, actor, cal.id, from_day, to_day, timezone or cal.timezone, cursor=cursor, limit=limit)
        items = [i for section in SECTIONS for i in page[section] if i['kind'] == kind]
        return {'calendar_id': cal.id, 'items': external_ids(db, items), 'complete': page['complete'],
                'next_cursor': page['next_cursor']}

    @router.get('/{entity_id}')
    def show(entity_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        row = owned_row(db, actor, model, entity_id)
        return {**entity_read(db, actor, row, kind), 'external_id': row.external_id}

    @router.post('', status_code=201)
    def create(response: Response, payload: dict = Body(...), calendar_id: str | None = Query(default=None),
               idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
               if_match: str | None = Header(default=None, alias='If-Match'),
               db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        writer = write_actor(actor)
        target = actor.app_calendar_id if actor.client_id else calendar_id
        if actor.client_id and calendar_id not in (None, actor.app_calendar_id):
            raise AppError('forbidden', 'Apps write only into their own calendar', status_code=403)
        external_id = _external_id(actor, payload)
        command_id = _command_id(idempotency_key)
        replay = db.get(m.CalendarWriteReceiptModel, (actor.principal_id, command_id)) is not None
        if external_id and not replay:
            # D37: sending the same external_id again updates that record instead of creating a twin.
            existing = db.scalar(select(model).where(model.calendar_id == target,
                                                     model.source_client_id == actor.client_id,
                                                     model.external_id == external_id))
            if existing is not None:
                if existing.deleted_at is not None:
                    raise AppError('conflict', 'The record with this external_id was deleted in the calendar',
                                   status_code=409, details={'entity_id': existing.id, 'deleted': True})
                response.status_code = 200
                return with_external(db, _command(db, writer, {
                    'command_id': command_id, 'kind': kind, 'operation': 'patch', 'entity_id': existing.id,
                    'expected_revision': _revision(if_match) if if_match else existing.revision, 'payload': payload,
                    'scope': 'series' if getattr(existing, 'recurrence_rule_id', None) else None}))
        body = {'command_id': command_id, 'kind': kind, 'operation': 'create', 'payload': payload}
        if target:
            body['calendar_id'] = target
        entity = _command(db, writer, body, commit=False)
        if external_id and not replay:
            row = db.get(model, entity['id'])
            row.source_client_id, row.external_id = actor.client_id, external_id
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise AppError('conflict', 'The same external_id is being created concurrently; retry',
                               status_code=409) from None
        db.commit()
        return with_external(db, entity)

    @router.patch('/{entity_id}')
    def patch(entity_id: str, payload: dict = Body(...), occurrence_key: str | None = None,
              scope: Literal['this', 'thisAndFollowing', 'series'] | None = None,
              if_match: str | None = Header(default=None, alias='If-Match'),
              idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
              db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        return mutate(db, actor, entity_id, 'patch', payload, if_match, idempotency_key, occurrence_key, scope)

    @router.delete('/{entity_id}')
    def delete(entity_id: str, occurrence_key: str | None = None,
               scope: Literal['this', 'thisAndFollowing', 'series'] | None = None,
               if_match: str | None = Header(default=None, alias='If-Match'),
               idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
               db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        mutate(db, actor, entity_id, 'delete', {}, if_match, idempotency_key, occurrence_key, scope)
        return {'id': entity_id, 'deleted': True}

    @router.post('/{entity_id}/{operation}')
    def act(entity_id: str, operation: Literal['confirm', 'complete', 'restore'], payload: dict = Body(default={}),
            occurrence_key: str | None = None, scope: Literal['this', 'thisAndFollowing', 'series'] | None = None,
            if_match: str | None = Header(default=None, alias='If-Match'),
            idempotency_key: str | None = Header(default=None, alias='Idempotency-Key'),
            db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
        """«было/не было» (confirm), task done (complete), undo delete (restore) — as in /integration/v1/commands."""
        return mutate(db, actor, entity_id, operation, payload, if_match, idempotency_key, occurrence_key, scope)

    return router


routers = [build_router(path, kind, model) for path, (kind, model) in KINDS.items()]
