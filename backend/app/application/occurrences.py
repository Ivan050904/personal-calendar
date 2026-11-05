import base64
import calendar
import hashlib
import hmac
import json
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy import select

from app.application.calendar_time import normalize_all_day, range_bounds, zone
from app.core.calendar_actor import require_owned_calendar
from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.db import models as m
from app.infrastructure.repositories import _iso


def source_href(calendar_id, kind, entity_id, occurrence_key=None):
    params = {'calendar_id':calendar_id, 'kind':kind, 'entity_id':entity_id}
    if occurrence_key is not None:
        params['occurrence_key'] = occurrence_key
    return '/calendar?' + urlencode(params)


def _cursor_secret():
    s = get_settings()
    return (s.auth_session_secret or s.calendar_bridge_secret).encode()


def encode_cursor(bound, offset):
    payload = base64.urlsafe_b64encode(json.dumps({'b':bound,'o':offset},separators=(',',':')).encode()).decode().rstrip('=')
    return payload+'.'+hmac.new(_cursor_secret(),payload.encode(),hashlib.sha256).hexdigest()


def decode_cursor(cursor, bound):
    if cursor is None:
        return 0
    try:
        body, sig = cursor.split('.')
        assert hmac.compare_digest(sig,hmac.new(_cursor_secret(),body.encode(),hashlib.sha256).hexdigest())
        data = json.loads(base64.urlsafe_b64decode(body+'='*(-len(body)%4)))
        assert data['b'] == bound and type(data['o']) is int and data['o'] >= 0
        return data['o']
    except (ValueError,KeyError,TypeError,AssertionError):
        raise AppError('cursor_invalid','Projection changed; restart bounded range',status_code=409) from None


def recurrence_read(rule):
    if rule is None:
        return None
    return {'frequency':rule.frequency,'interval':rule.interval,'weekdays':list(rule.weekdays or []),
            'day_of_month':rule.day_of_month,'until_date':_iso(rule.until_date),'occurrence_count':rule.occurrence_count,
            'dst_gap_policy':'skip','dst_fold_policy':'earlier'}


def entity_read(db, actor, row, kind):
    cal = require_owned_calendar(db,actor,row.calendar_id)
    all_day = bool(getattr(row,'all_day',False))
    starts, ends = normalize_all_day(row) if all_day else (None,None)
    rule = db.get(m.RecurrenceRuleModel,getattr(row,'recurrence_rule_id',None)) if getattr(row,'recurrence_rule_id',None) else None
    return {'id':row.id,'calendar_id':cal.id,'kind':kind,'title':row.title,'description':getattr(row,'description',None) or '',
            'revision':row.revision,'timezone':getattr(row,'timezone',cal.timezone),'start_at':None if all_day else _iso(getattr(row,'start_at',None)),
            'end_at':None if all_day else _iso(getattr(row,'end_at',None)), 'all_day':all_day,'start_date':_iso(starts),'end_date_exclusive':_iso(ends),
            'due_date':_iso(getattr(row,'due_date',None)),'completed':getattr(row,'completed',None),
            'location':getattr(row,'location',None),'color':getattr(row,'color',None),'recurrence':recurrence_read(rule),
            'deleted_at':_iso(row.deleted_at),'created_at':_iso(row.created_at),'updated_at':_iso(row.updated_at),
            'source_href':source_href(cal.id,kind,row.id)}


def _occurrence(entity, key=None, start=None, end=None, cancelled=False):
    out = {k:v for k,v in entity.items() if k not in {'recurrence','deleted_at','created_at','updated_at'}}
    out.update(entity_id=entity['id'], id=entity['id'] + ('::'+key if key else ''),occurrence_key=key,
               confirmation_status=None,cancelled=cancelled,source_href=source_href(entity['calendar_id'],entity['kind'],entity['id'],key))
    if start is not None:
        out['start_at'] = _iso(start)
        out['end_at'] = _iso(end)
    return out


def candidate(rule, first, day):
    delta = (day-first).days
    step = max(1,rule.interval)
    if delta < 0:
        return False
    if rule.frequency == 'daily':
        return delta % step == 0
    if rule.frequency in {'weekly','weekdays'}:
        weekdays = list(rule.weekdays or ([first.isoweekday()] if rule.frequency == 'weekly' else [1,2,3,4,5]))
        return day.isoweekday() in weekdays and (delta//7)%step == 0
    if rule.frequency == 'monthly':
        months = (day.year-first.year)*12+day.month-first.month
        return months%step == 0 and day.day == min(rule.day_of_month or first.day,calendar.monthrange(day.year,day.month)[1])
    return False


def valid_local(local, tz):
    aware = local.replace(tzinfo=tz,fold=0)
    utc = aware.astimezone(timezone.utc)
    if utc.astimezone(tz).replace(tzinfo=None) != local:
        return None  # DST gap is skipped; fold=0 selects earlier instant.
    return utc


def remaining_occurrence_count(row, rule, split_day):
    """Keep the projection's valid-generation count, before exception overrides."""
    if rule.occurrence_count is None:
        return None
    tz = zone(row.timezone)
    local_start = datetime.combine(normalize_all_day(row)[0], datetime.min.time()) if row.all_day else row.start_at.replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)
    first = local_start.date()
    before = 0
    for offset in range((split_day - first).days):
        if offset >= 10000:
            raise AppError('range_too_dense', 'Recurrence expansion exceeds work budget', status_code=422)
        day = first + timedelta(days=offset)
        if candidate(rule, first, day) and valid_local(datetime.combine(day, local_start.time()), tz) is not None:
            before += 1
    return rule.occurrence_count - before


def all_occurrences(db, actor, calendar_id, from_day, to_day, display_zone, include_cancelled=False):
    cal = require_owned_calendar(db,actor,calendar_id)
    lo, hi = range_bounds(from_day,to_day,display_zone)
    result = []
    work = 0
    for kind, model in [('event',m.EventModel),('plan',m.PlanModel),('task',m.TaskModel)]:
        rows = db.scalars(select(model).where(model.calendar_id == cal.id,model.deleted_at.is_(None)).order_by(model.id)).all()
        for row in rows:
            entity = entity_read(db,actor,row,kind)
            if kind == 'task':
                if row.completed:
                    continue
                key = _iso(row.due_date)
                item = _occurrence(entity,key)
                if row.due_date is None:
                    item['_section'] = 'undated_tasks'
                elif row.due_date < from_day:
                    item['_section'] = 'overdue_tasks'
                elif row.due_date <= to_day:
                    item['_section'] = 'items'
                else:
                    continue
                result.append(item)
                continue
            rule_id = getattr(row,'recurrence_rule_id',None)
            if not rule_id:
                if entity['all_day']:
                    visible = entity['start_date'] <= to_day.isoformat() and entity['end_date_exclusive'] > from_day.isoformat()
                else:
                    visible = row.start_at.replace(tzinfo=timezone.utc) < hi and row.end_at.replace(tzinfo=timezone.utc) > lo
                if visible:
                    result.append(_occurrence(entity))
                continue
            rule = db.get(m.RecurrenceRuleModel,rule_id)
            if rule is None or rule.owner_id != actor.principal_id or rule.deleted_at:
                raise AppError('not_found','Recurrence rule not found',status_code=404)
            exceptions = {e.occurrence_key:e for e in db.scalars(select(m.EventExceptionModel).where(m.EventExceptionModel.event_id == row.id,m.EventExceptionModel.deleted_at.is_(None))).all()}
            tz = zone(row.timezone)
            first = date.fromisoformat(entity['start_date']) if entity['all_day'] else row.start_at.replace(tzinfo=timezone.utc).astimezone(tz).date()
            local_start = datetime.combine(first,datetime.min.time()) if entity['all_day'] else row.start_at.replace(tzinfo=timezone.utc).astimezone(tz).replace(tzinfo=None)
            duration = None if entity['all_day'] else row.end_at-row.start_at
            # Include moved exceptions whose original dates are outside the requested range.
            last = hi.astimezone(tz).date()
            if exceptions:
                last = max(last, max(date.fromisoformat(key[:10]) for key in exceptions))
            if rule.until_date:
                last = min(last,rule.until_date)
            day, count = first, 0
            while day <= last:
                work += 1
                if work > 10000:
                    raise AppError('range_too_dense','Recurrence expansion exceeds work budget',status_code=422)
                if candidate(rule,first,day):
                    local = datetime.combine(day,local_start.time())
                    instant = valid_local(local,tz)
                    if instant is not None:
                        count += 1
                        if rule.occurrence_count and count > rule.occurrence_count:
                            break
                        key = local.isoformat(timespec='minutes')
                        exc = exceptions.get(key)
                        cancelled = bool(exc and exc.type == 'cancelled')
                        start = exc.override_start_at.replace(tzinfo=timezone.utc) if exc and exc.override_start_at else instant
                        end = exc.override_end_at.replace(tzinfo=timezone.utc) if exc and exc.override_end_at else start + (duration or timedelta(days=1))
                        item = _occurrence(entity,key,start,end,cancelled)
                        if exc:
                            item.update(exc.override_payload or {})
                        if entity['all_day']:
                            item.update(start_at=None,end_at=None,start_date=day.isoformat(),end_date_exclusive=(day+(date.fromisoformat(entity['end_date_exclusive'])-first)).isoformat())
                            visible = item['start_date'] <= to_day.isoformat() and item['end_date_exclusive'] > from_day.isoformat()
                        else:
                            visible = start < hi and end > lo
                        if visible and (not cancelled or include_cancelled):
                            result.append(item)
                day += timedelta(days=1)
    for item in result:
        item.setdefault('_section','items')
        fact = db.scalar(select(m.CalendarConfirmationModel).where(m.CalendarConfirmationModel.owner_id == actor.principal_id,m.CalendarConfirmationModel.entity_id == item['entity_id'],m.CalendarConfirmationModel.occurrence_ref == (item['occurrence_key'] or '')))
        if fact and fact.status in {'occurred','not_occurred'}:
            item['confirmation_status'] = fact.status
    # Include aggregate revision in binding even when generic children changed.
    result.sort(key=lambda i:({'items':0,'overdue_tasks':1,'undated_tasks':2}[i['_section']],i['due_date'] or i['start_date'] or i['start_at'] or '',i['id']))
    return cal, result


def project_occurrences(db,actor,calendar_id,from_day,to_day,display_zone,cursor=None,limit=500,include_cancelled=False):
    if not 1 <= limit <= 500:
        raise AppError('validation_error','Limit must be 1–500',status_code=422)
    cal, rows = all_occurrences(db,actor,calendar_id,from_day,to_day,display_zone,include_cancelled)
    fingerprint = hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
    bound = '|'.join([actor.principal_id,cal.id,str(cal.revision),str(from_day),str(to_day),display_zone,fingerprint,str(include_cancelled)])
    offset = decode_cursor(cursor,bound)
    page = rows[offset:offset+limit]
    complete = offset+limit >= len(rows)
    return {'contract_version':2,'calendar_id':cal.id,'items':page,'next_cursor':None if complete else encode_cursor(bound,offset+limit),'complete':complete}
