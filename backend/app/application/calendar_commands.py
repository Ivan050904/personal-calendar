import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select, update

from app.application.calendar_history import record_confirmation,change_cursor
from app.application.calendar_time import normalize_all_day,validate_timed_input,zone
from app.application.occurrences import entity_read, remaining_occurrence_count
from app.core.calendar_actor import require_owned_calendar,require_scope
from app.core.errors import AppError
from app.infrastructure.db import models as m
from app.infrastructure.repositories import _parse_date,_parse_dt
from app.schemas.calendar_commands import CalendarWriteRequest

MODELS = {'event':m.EventModel,'task':m.TaskModel,'plan':m.PlanModel}


def cas(db,row,expected):
    if expected is None:
        raise AppError('revision_required','Expected revision required',status_code=428)
    result = db.execute(update(type(row)).where(type(row).id == row.id,type(row).revision == expected).values(revision=expected+1,updated_at=datetime.utcnow()).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.refresh(row)
        raise AppError('conflict','Entity revision changed',status_code=409,details={'entity_id':row.id,'current_revision':row.revision})
    db.refresh(row)


def add_change(db,actor,row,kind,operation):
    cal = require_owned_calendar(db,actor,row.calendar_id)
    db.execute(update(m.CalendarModel).where(m.CalendarModel.id == cal.id).values(revision=m.CalendarModel.revision+1,updated_at=datetime.utcnow()).execution_options(synchronize_session=False))
    db.add(m.CalendarChangeModel(owner_id=actor.principal_id,calendar_id=row.calendar_id,entity_id=row.id,kind=kind,operation=operation,revision=row.revision,deleted=row.deleted_at is not None))
    db.flush()


def apply_payload(db,actor,row,kind,payload,create=False):
    forbidden_task = {'start_at','end_at','all_day','start_date','end_date_exclusive','location','color'}
    if kind == 'task' and any(payload.get(k) is not None and payload.get(k) is not False for k in forbidden_task):
        raise AppError('validation_error','Tasks use due_date without timeline instants',status_code=422)
    if kind == 'plan' and (payload.get('all_day') or payload.get('recurrence') is not None or payload.get('location') is not None):
        raise AppError('validation_error','Plan payload is unsupported',status_code=422)
    for key in ['title','description','color','location','completed','timezone','all_day']:
        if key in payload and hasattr(row,key):
            value = payload[key]
            if key in {'title','timezone','color','all_day','completed'} and value is None:
                raise AppError('validation_error',key+' cannot be null',status_code=422)
            setattr(row,key,value)
    for key in ['start_at','end_at']:
        if key in payload and hasattr(row,key):
            setattr(row,key,_parse_dt(payload[key]))
    for key in ['start_date','end_date_exclusive','due_date']:
        if key in payload and hasattr(row,key):
            setattr(row,key,_parse_date(payload[key]))
    if kind != 'task':
        if getattr(row,'all_day',False):
            if row.start_date is None or row.end_date_exclusive is None or row.end_date_exclusive <= row.start_date:
                raise AppError('validation_error','Exclusive all-day dates required',status_code=422)
            row.start_at, row.end_at = None,None
        else:
            if row.start_at is None or row.end_at is None:
                raise AppError('validation_error','Timed bounds required',status_code=422)
            validate_timed_input(row.start_at.replace(tzinfo=timezone.utc),row.end_at.replace(tzinfo=timezone.utc),row.timezone)
    if 'recurrence' in payload:
        if payload['recurrence'] is None:
            row.recurrence_rule_id = None
        else:
            data = payload['recurrence']
            rule = db.get(m.RecurrenceRuleModel,row.recurrence_rule_id) if row.recurrence_rule_id else None
            if rule is None:
                rule = m.RecurrenceRuleModel(id=str(uuid4()),owner_id=actor.principal_id)
                db.add(rule)
                row.recurrence_rule_id = rule.id
            if rule.owner_id != actor.principal_id:
                raise AppError('not_found','Rule not found',status_code=404)
            for key in ['frequency','interval','weekdays','day_of_month','occurrence_count']:
                setattr(rule,key,data.get(key) if key != 'weekdays' else data.get(key) or [])
            rule.interval = data.get('interval') or 1
            rule.until_date = _parse_date(data.get('until_date'))
            rule.dst_gap_policy,rule.dst_fold_policy = 'skip','earlier'


def _default_calendar(db,actor):
    cal = db.scalar(select(m.CalendarModel).where(m.CalendarModel.default_owner == actor.principal_id,m.CalendarModel.deleted_at.is_(None)))
    if cal is None:
        raise AppError('not_found','Connect calendar first',status_code=404)
    return require_owned_calendar(db,actor,cal.id)


def execute_calendar_command(db,actor,request):
    require_scope(actor,'calendar:write')
    try:
        envelope = request if isinstance(request,CalendarWriteRequest) else CalendarWriteRequest.model_validate(request)
    except ValidationError:
        raise AppError('validation_error','Invalid calendar command',status_code=422) from None
    canonical = envelope.model_dump(mode='json',exclude_unset=True)
    body_hash = hashlib.sha256(json.dumps(canonical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    key = (actor.principal_id,str(envelope.command_id))
    receipt = db.get(m.CalendarWriteReceiptModel,key)
    if receipt:
        if receipt.body_hash != body_hash:
            raise AppError('conflict','Idempotency key used for a different command',status_code=409)
        return {**receipt.result,'replayed':True}
    # Receipt reservation and all changes share one transaction/savepoint.
    with db.begin_nested():
        reservation = m.CalendarWriteReceiptModel(owner_id=actor.principal_id,command_id=str(envelope.command_id),body_hash=body_hash,result={})
        db.add(reservation)
        db.flush()
        payload = envelope.payload.model_dump(mode='json',exclude_unset=True)
        model = MODELS[envelope.kind]
        confirmation = None
        if envelope.operation == 'create':
            cal = require_owned_calendar(db,actor,envelope.calendar_id) if envelope.calendar_id else _default_calendar(db,actor)
            row = model(id=str(uuid4()),calendar_id=cal.id,title=payload['title'],revision=1,created_at=datetime.utcnow(),updated_at=datetime.utcnow())
            if envelope.kind != 'task':
                row.timezone,row.color = payload['timezone'],payload.get('color') or '#0f766e'
            if envelope.kind == 'event':
                row.all_day = False
            if envelope.kind == 'task':
                row.completed = False
            apply_payload(db,actor,row,envelope.kind,payload,create=True)
            db.add(row)
        else:
            row = db.get(model,envelope.entity_id)
            if row is None:
                raise AppError('not_found','Entity not found',status_code=404)
            require_owned_calendar(db,actor,row.calendar_id)
            if row.deleted_at is not None and envelope.operation != 'restore':
                raise AppError('not_found','Entity deleted',status_code=404)
            recurring = bool(getattr(row,'recurrence_rule_id',None))
            if recurring and envelope.operation in {'patch','delete'} and envelope.scope is None:
                raise AppError('validation_error','Recurring mutation requires scope',status_code=422)
            cas(db,row,envelope.expected_revision)
            if envelope.operation in {'confirm','complete'}:
                if envelope.operation == 'complete':
                    payload.setdefault('status','occurred')
                    if not payload.get('happened_date'):
                        source_zone = db.get(m.CalendarModel,row.calendar_id).timezone
                        payload['happened_date'] = str(datetime.now(timezone.utc).astimezone(zone(source_zone)).date())
                    payload.setdefault('happened_at',datetime.now(timezone.utc).isoformat())
                key = envelope.occurrence_key
                if envelope.kind == 'task' and not key:
                    key = str(row.due_date) if row.due_date else None
                if recurring and envelope.kind == 'task' and envelope.operation == 'complete' and key != (str(row.due_date) if row.due_date else None):
                    raise AppError('conflict','Original due date changed',status_code=409)
                confirmation = record_confirmation(db,actor,row,envelope.kind,key,payload)
            elif envelope.operation == 'restore':
                if row.deleted_at and datetime.utcnow()-row.deleted_at > timedelta(days=30):
                    raise AppError('not_found','Retention expired',status_code=404)
                row.deleted_at = None
            elif recurring and envelope.scope == 'this':
                if envelope.kind != 'event' or not envelope.occurrence_key:
                    raise AppError('validation_error','Single event occurrence key required',status_code=422)
                from app.api.routes.integration import occurrence
                occurrence(row.id,envelope.occurrence_key,db,actor)
                exc = db.scalar(select(m.EventExceptionModel).where(m.EventExceptionModel.event_id == row.id,m.EventExceptionModel.occurrence_key == envelope.occurrence_key))
                if exc is None:
                    exc = m.EventExceptionModel(id=str(uuid4()),event_id=row.id,recurrence_rule_id=row.recurrence_rule_id,occurrence_key=envelope.occurrence_key)
                    db.add(exc)
                exc.type = 'cancelled' if envelope.operation == 'delete' else 'modified'
                exc.override_payload = {**(exc.override_payload or {}),**{k:v for k,v in payload.items() if k in {'title','description','location','color'}}}
                if 'start_at' in payload:
                    exc.override_start_at = _parse_dt(payload['start_at'])
                if 'end_at' in payload:
                    exc.override_end_at = _parse_dt(payload['end_at'])
            elif recurring and envelope.scope == 'thisAndFollowing':
                if envelope.kind != 'event' or not envelope.occurrence_key:
                    raise AppError('validation_error','Following event occurrence key required',status_code=422)
                from app.api.routes.integration import occurrence
                original = occurrence(row.id,envelope.occurrence_key,db,actor)
                rule = db.get(m.RecurrenceRuleModel,row.recurrence_rule_id)
                old_until = rule.until_date
                split_day = date.fromisoformat(envelope.occurrence_key[:10])
                remaining_count = remaining_occurrence_count(row, rule, split_day)
                rule.until_date = split_day-timedelta(days=1)
                if envelope.operation != 'delete':
                    new_rule = m.RecurrenceRuleModel(id=str(uuid4()),owner_id=actor.principal_id,frequency=rule.frequency,interval=rule.interval,weekdays=rule.weekdays,day_of_month=rule.day_of_month,until_date=old_until,occurrence_count=remaining_count)
                    db.add(new_rule)
                    new_row = m.EventModel(id=str(uuid4()),calendar_id=row.calendar_id,title=row.title,description=row.description,timezone=row.timezone,color=row.color,all_day=row.all_day,start_at=_parse_dt(original['start_at']),end_at=_parse_dt(original['end_at']),start_date=_parse_date(original['start_date']),end_date_exclusive=_parse_date(original['end_date_exclusive']),location=row.location,recurrence_rule_id=new_rule.id)
                    apply_payload(db,actor,new_row,envelope.kind,payload)
                    db.add(new_row)
                    add_change(db,actor,row,envelope.kind,'patch')
                    row = new_row
            elif envelope.operation == 'delete':
                row.deleted_at = datetime.utcnow()
            elif envelope.operation == 'patch':
                apply_payload(db,actor,row,envelope.kind,payload)
        db.flush()
        add_change(db,actor,row,envelope.kind,envelope.operation)
        result = {'command_id':str(envelope.command_id),'entity':entity_read(db,actor,row,envelope.kind),'confirmation':confirmation,'replayed':False,'change_cursor':change_cursor(db,actor)}
        reservation.result = result
        db.flush()
    return result


def lookup_calendar_command(db,actor,command_id):
    require_scope(actor,'calendar:write')
    receipt = db.get(m.CalendarWriteReceiptModel,(actor.principal_id,str(command_id)))
    if receipt is None:
        raise AppError('not_found','Command not found',status_code=404)
    return {**receipt.result,'replayed':True}
