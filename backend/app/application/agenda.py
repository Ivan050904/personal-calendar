from datetime import datetime, timezone

from app.application.occurrences import project_occurrences
from app.core.calendar_actor import require_owned_calendar
from app.infrastructure.repositories import _iso


def smart_day(rows,now):
    timed = [r for r in rows if r['kind'] != 'task' and not r['all_day'] and not r.get('cancelled')]
    timed.sort(key=lambda r:(r['start_at'],r['end_at'],r['id']))
    value = _iso(now.astimezone(timezone.utc).replace(tzinfo=None))
    current = [r for r in timed if r['start_at'] <= value < r['end_at']]
    future = [r for r in timed if r['start_at'] > value]
    overlaps = [r for r in timed if any(r['id'] != o['id'] and r['start_at'] < o['end_at'] and r['end_at'] > o['start_at'] for o in timed)]
    return {'current':current[0] if current else None,'next':future[0] if future else None,'overlaps':overlaps}


def build_agenda(db,actor,calendar_id,from_day,to_day,display_zone,now=None,cursor=None,limit=500):
    now = now or datetime.now(timezone.utc)
    cal = require_owned_calendar(db,actor,calendar_id)
    page = project_occurrences(db,actor,calendar_id,from_day,to_day,display_zone,cursor,limit)
    sections = {'items':[],'overdue_tasks':[],'undated_tasks':[]}
    for item in page['items']:
        sections[item.pop('_section','items')].append(item)
    page.update(sections,calendar_timezone=cal.timezone,timezone=display_zone,from_date=str(from_day),to_date=str(to_day),
                server_now=_iso(now.astimezone(timezone.utc).replace(tzinfo=None)),fetched_at=_iso(now.astimezone(timezone.utc).replace(tzinfo=None)),
                freshness='live',smart_day=smart_day(sections['items'],now) if cursor is None else None)
    return page
