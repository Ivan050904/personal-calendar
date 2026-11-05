from datetime import date, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.agenda import build_agenda
from app.application.calendar_time import zone
from app.application.occurrences import entity_read, project_occurrences
from app.core.calendar_actor import CalendarActor, calendar_read, ensure_actor_calendar, require_actor, require_owned_calendar, require_scope
from app.core.errors import AppError
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/integration/v1', tags=['calendar-integration'])


class ConnectRequest(BaseModel):
    timezone: str
    idempotency_key: UUID


def owned_default(db,actor,calendar_id=None):
    if calendar_id:
        return require_owned_calendar(db,actor,calendar_id)
    cal = db.scalar(select(m.CalendarModel).where(m.CalendarModel.owner_id == actor.principal_id,m.CalendarModel.default_owner == actor.principal_id,m.CalendarModel.deleted_at.is_(None)))
    if cal is None:
        raise AppError('not_found','Connect calendar first',status_code=404)
    return cal


@router.post('/connect')
def connect(body:ConnectRequest,db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:connect')
    result = ensure_actor_calendar(db,actor,body.timezone,str(body.idempotency_key))
    db.commit()
    return result


@router.get('/status')
def status(db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:read')
    cal = owned_default(db,actor)
    return {'contract_version':2,'capabilities':{'read':True,'write':True,'history':True,'reminders':True}, 'calendar':calendar_read(cal)}


@router.get('/agenda')
def agenda(from_day:date=Query(alias='from'),to_day:date=Query(alias='to'),timezone:str|None=None,calendar_id:str|None=None,cursor:str|None=None,limit:int=Query(default=500,ge=1,le=500),db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:read')
    cal = owned_default(db,actor,calendar_id)
    return build_agenda(db,actor,cal.id,from_day,to_day,timezone or cal.timezone,cursor=cursor,limit=limit)


@router.get('/entities/{kind}/{entity_id}')
def detail(kind:str,entity_id:str,db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:read')
    model = {'event':m.EventModel,'task':m.TaskModel,'plan':m.PlanModel}.get(kind)
    if not model:
        raise AppError('not_found','Entity not found',status_code=404)
    row = db.get(model,entity_id)
    if row is None or row.deleted_at:
        raise AppError('not_found','Entity not found',status_code=404)
    return entity_read(db,actor,row,kind)


def occurrence_actor(actor:CalendarActor=Depends(require_actor)):
    if not actor.scopes & {'calendar:read','calendar:reminders'}:
        require_scope(actor,'calendar:read')
    return actor


@router.get('/occurrences/{entity_id}')
def occurrence(entity_id:str,occurrence_key:str|None=None,db:Session=Depends(get_db),actor:CalendarActor=Depends(occurrence_actor)):
    row,kind = next(((db.get(model,entity_id),kind) for kind,model in [('event',m.EventModel),('task',m.TaskModel),('plan',m.PlanModel)] if db.get(model,entity_id)),(None,None))
    if row is None or row.deleted_at:
        raise AppError('not_found','Occurrence not found',status_code=404)
    entity = entity_read(db,actor,row,kind)
    from app.application.occurrences import _occurrence
    if not getattr(row,'recurrence_rule_id',None):
        expected = str(row.due_date) if kind == 'task' and row.due_date else None
        if occurrence_key not in {None,expected}:
            raise AppError('not_found','Occurrence not found',status_code=404)
        return _occurrence(entity,expected)
    if not occurrence_key:
        raise AppError('validation_error','Occurrence key required',status_code=422)
    day = date.fromisoformat(occurrence_key[:10])
    exception = db.scalar(select(m.EventExceptionModel).where(m.EventExceptionModel.event_id == entity_id,m.EventExceptionModel.occurrence_key == occurrence_key,m.EventExceptionModel.deleted_at.is_(None))) if kind == 'event' else None
    target_day = exception.override_start_at.replace(tzinfo=timezone.utc).astimezone(zone(entity['timezone'])).date() if exception and exception.override_start_at else day
    page = project_occurrences(db,actor,row.calendar_id,target_day,target_day,entity['timezone'],include_cancelled=True)
    item = next((i for i in page['items'] if i['entity_id'] == entity_id and i['occurrence_key'] == occurrence_key),None)
    if item is None:
        raise AppError('not_found','Occurrence not found',status_code=404)
    item.pop('_section',None)
    return item


from app.application.calendar_commands import execute_calendar_command,lookup_calendar_command
from app.application.calendar_history import change_cursor,confirmation_read,current_confirmation,history_page
from app.application.occurrences import decode_cursor,encode_cursor
from app.schemas.calendar_commands import CalendarWriteRequest
from fastapi import Header
from datetime import datetime
from app.infrastructure.repositories import _iso


@router.post('/commands')
def command(body:CalendarWriteRequest,idempotency_key:str|None=Header(default=None,alias='Idempotency-Key'),db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    if idempotency_key != str(body.command_id):
        raise AppError('validation_error','Idempotency-Key must equal command_id',status_code=422)
    result = execute_calendar_command(db,actor,body)
    db.commit()
    return result


@router.get('/commands/{command_id}')
def command_result(command_id:UUID,db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    return lookup_calendar_command(db,actor,command_id)


@router.get('/history')
def history(from_day:date=Query(alias='from'),to_day:date=Query(alias='to'),cursor:str|None=None,limit:int=Query(default=100,ge=1,le=100),db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:history')
    return history_page(db,actor,from_day,to_day,cursor,limit)


@router.get('/confirmations/{entity_id}')
def confirmation(entity_id:str,occurrence_key:str|None=None,db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    if not actor.scopes & {'calendar:read','calendar:history'}:
        require_scope(actor,'calendar:history')
    row = next((db.get(model,entity_id) for model in [m.EventModel,m.TaskModel,m.PlanModel] if db.get(model,entity_id)),None)
    if row is None:
        raise AppError('not_found','Entity not found',status_code=404)
    require_owned_calendar(db,actor,row.calendar_id)
    fact = current_confirmation(db,actor,entity_id,occurrence_key)
    return {'confirmation':confirmation_read(fact) if fact else None}


@router.get('/changes')
def changes(cursor:str|None=None,limit:int=Query(default=500,ge=1,le=500),db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    if not actor.scopes & {'calendar:read','calendar:reminders','calendar:history'}:
        require_scope(actor,'calendar:read')
    bound = 'changes|'+actor.principal_id
    offset = decode_cursor(cursor,bound)
    rows = db.scalars(select(m.CalendarChangeModel).where(m.CalendarChangeModel.owner_id == actor.principal_id,m.CalendarChangeModel.id > offset).order_by(m.CalendarChangeModel.id).limit(limit+1)).all()
    page = rows[:limit]
    continuation = encode_cursor(bound,page[-1].id if page else offset)
    return {'contract_version':2,'items':[{'id':str(r.id),'calendar_id':r.calendar_id,'entity_id':r.entity_id,'kind':r.kind,'operation':r.operation,'revision':r.revision,'deleted':r.deleted,'changed_at':_iso(r.changed_at)} for r in page],
            'next_cursor':continuation if len(rows)>limit else None,'complete':len(rows)<=limit,'change_cursor':continuation,'server_now':_iso(datetime.utcnow())}


@router.get('/reminder-source')
def reminder_source(from_day:date=Query(alias='from'),to_day:date=Query(alias='to'),cursor:str|None=None,calendar_id:str|None=None,db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:reminders')
    if to_day < from_day or (to_day-from_day).days >= 7:
        raise AppError('validation_error','Reminder range must contain 1–7 days',status_code=422)
    cal = owned_default(db,actor,calendar_id)
    page = project_occurrences(db,actor,cal.id,from_day,to_day,cal.timezone,cursor=cursor,include_cancelled=True)
    for item in page['items']:
        item.pop('_section',None)
    entity_ids = {i['entity_id'] for i in page['items'] if i['kind'] == 'event'}
    reminders = db.scalars(select(m.ReminderModel).where(m.ReminderModel.event_id.in_(entity_ids),m.ReminderModel.deleted_at.is_(None))).all() if entity_ids else []
    page.update(reminders=[{'id':r.id,'entity_id':r.event_id,'offset_minutes':r.offset_minutes,'reminder_time':r.reminder_time,'enabled':r.enabled,'revision':r.revision} for r in reminders],server_now=_iso(datetime.utcnow()),change_cursor=change_cursor(db,actor),from_date=str(from_day),to_date=str(to_day))
    return page
