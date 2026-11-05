from datetime import date, datetime, timedelta
from uuid import uuid4
from sqlalchemy import select,func

from app.application.occurrences import candidate, source_href, encode_cursor, decode_cursor
from app.core.errors import AppError
from app.infrastructure.db import models as m
from app.infrastructure.repositories import _iso, _parse_dt


def confirmation_read(row):
    return {'id':row.id,'revision':row.revision,'calendar_id':row.calendar_id,'entity_id':row.entity_id,'kind':row.kind,
            'occurrence_key':row.occurrence_ref or None,'status':row.status,'happened_at':_iso(row.happened_at),
            'happened_date':str(row.happened_date),'time_zone':row.time_zone,'title':row.title,
            'recorded_at':_iso(row.recorded_at),'updated_at':_iso(row.updated_at),
            'source_href':source_href(row.calendar_id,row.kind,row.entity_id,row.occurrence_ref or None)}


def current_confirmation(db,actor,entity_id,key):
    return db.scalar(select(m.CalendarConfirmationModel).where(m.CalendarConfirmationModel.owner_id == actor.principal_id,
                     m.CalendarConfirmationModel.entity_id == entity_id,m.CalendarConfirmationModel.occurrence_ref == (key or '')))


def record_confirmation(db,actor,row,kind,key,payload):
    now = datetime.utcnow()
    fact = current_confirmation(db,actor,row.id,key)
    expected = payload.get('expected_confirmation_revision')
    if fact and expected != fact.revision:
        raise AppError('conflict','Confirmation revision changed',status_code=409)
    if not fact and expected is not None:
        raise AppError('conflict','Confirmation does not exist',status_code=409)
    status = payload.get('status') or 'occurred'
    happened = date.fromisoformat(payload['happened_date'])
    if kind == 'task' and fact and status == 'revoked':
        latest = db.scalar(select(m.CalendarConfirmationModel).where(m.CalendarConfirmationModel.owner_id == actor.principal_id,m.CalendarConfirmationModel.entity_id == row.id).order_by(m.CalendarConfirmationModel.recorded_at.desc(),m.CalendarConfirmationModel.id.desc()).limit(1))
        if latest.id != fact.id or (fact.next_due_date and row.due_date != fact.next_due_date):
            raise AppError('conflict','Later completion prevents this undo',status_code=409)
    is_new = fact is None
    old_status = fact.status if fact else None
    if fact is None:
        if status == 'revoked':
            raise AppError('conflict','Cannot revoke missing fact',status_code=409)
        fact = m.CalendarConfirmationModel(id=str(uuid4()),owner_id=actor.principal_id,calendar_id=row.calendar_id,
                   entity_id=row.id,kind=kind,occurrence_ref=key or '',revision=1,status=status,happened_date=happened,
                   time_zone=getattr(row,'timezone',None) or db.get(m.CalendarModel,row.calendar_id).timezone,title=row.title,recorded_at=now,updated_at=now,audit=[])
        if kind == 'task':
            fact.previous_due_date = row.due_date
        db.add(fact)
    else:
        fact.audit = [*(fact.audit or []),confirmation_read(fact)]
        fact.revision += 1
    fact.status, fact.happened_date, fact.happened_at, fact.updated_at = status,happened,_parse_dt(payload.get('happened_at')),now
    if kind == 'task':
        rule = db.get(m.RecurrenceRuleModel,row.recurrence_rule_id) if row.recurrence_rule_id else None
        if status == 'revoked':
            row.due_date = fact.previous_due_date
            row.completed = False
        elif status == 'occurred' and rule and (is_new or old_status != 'occurred'):
            db.flush()
            active_count = db.scalar(select(func.count()).select_from(m.CalendarConfirmationModel).where(m.CalendarConfirmationModel.owner_id == actor.principal_id,m.CalendarConfirmationModel.entity_id == row.id,m.CalendarConfirmationModel.status == 'occurred')) or 0
            if rule.occurrence_count and active_count >= rule.occurrence_count:
                row.completed = True
                db.flush()
                return confirmation_read(fact)
            first = fact.previous_due_date or happened
            day = max(first,happened)+timedelta(days=1)
            for _ in range(10000):
                if rule.until_date and day > rule.until_date:
                    row.completed = True
                    break
                if candidate(rule,first,day):
                    row.due_date, row.completed = day,False
                    fact.next_due_date = day
                    break
                day += timedelta(days=1)
            else:
                raise AppError('range_too_dense','Task recurrence exceeds work budget',status_code=422)
        elif status == 'occurred' and (is_new or old_status != 'occurred'):
            row.completed = True
    db.flush()
    return confirmation_read(fact)


def change_cursor(db,actor):
    last = db.scalar(select(m.CalendarChangeModel.id).where(m.CalendarChangeModel.owner_id == actor.principal_id).order_by(m.CalendarChangeModel.id.desc()).limit(1)) or 0
    return encode_cursor('changes|'+actor.principal_id,last)


def history_page(db,actor,from_day,to_day,cursor=None,limit=100):
    if to_day < from_day or not 1 <= limit <= 100:
        raise AppError('validation_error','Invalid history range/page',status_code=422)
    rows = db.scalars(select(m.CalendarConfirmationModel).where(m.CalendarConfirmationModel.owner_id == actor.principal_id,m.CalendarConfirmationModel.happened_date >= from_day,m.CalendarConfirmationModel.happened_date <= to_day).order_by(m.CalendarConfirmationModel.happened_date,m.CalendarConfirmationModel.id)).all()
    bound = 'history|'+actor.principal_id+'|'+str(from_day)+'|'+str(to_day)+'|'+','.join(r.id+':'+str(r.revision) for r in rows)
    offset = decode_cursor(cursor,bound)
    return {'contract_version':2,'items':[confirmation_read(r) for r in rows[offset:offset+limit]],
            'complete':offset+limit>=len(rows),'next_cursor':None if offset+limit>=len(rows) else encode_cursor(bound,offset+limit),
            'server_now':_iso(datetime.utcnow()),'change_cursor':change_cursor(db,actor)}
