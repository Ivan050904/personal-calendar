from datetime import date, datetime
from uuid import uuid4

from app.core.calendar_actor import CalendarActor, ensure_actor_calendar
from app.infrastructure.db.models import EventModel, RecurrenceRuleModel, EventExceptionModel


def seed_series(db):
    actor = CalendarActor('projection', 'folio-projection', frozenset({'calendar:read','calendar:write'}))
    cal = ensure_actor_calendar(db, actor, 'UTC', str(uuid4()))
    rule = RecurrenceRuleModel(id=str(uuid4()),owner_id=actor.principal_id,frequency='daily',interval=1,weekdays=[])
    db.add(rule)
    event = EventModel(id=str(uuid4()),calendar_id=cal['id'],title='Series',start_at=datetime(2026,10,1,9),end_at=datetime(2026,10,1,10),timezone='UTC',all_day=False,color='#123456',recurrence_rule_id=rule.id)
    db.add(event)
    db.flush()
    return actor, cal, event, rule


def test_moved_from_outside_range_and_stable_occurrence_id(db_session):
    from app.application.occurrences import project_occurrences
    actor, cal, event, rule = seed_series(db_session)
    key = '2026-10-02T09:00'
    db_session.add(EventExceptionModel(id=str(uuid4()),event_id=event.id,recurrence_rule_id=rule.id,occurrence_key=key,type='modified',override_start_at=datetime(2026,10,8,11),override_end_at=datetime(2026,10,8,12)))
    db_session.flush()
    page = project_occurrences(db_session,actor,cal['id'],date(2026,10,8),date(2026,10,8),'UTC')
    moved = next(item for item in page['items'] if item['occurrence_key'] == key)
    assert moved['id'] == event.id+'::'+key
    assert moved['start_at'] == '2026-10-08T11:00:00Z'
    assert moved['due_date'] is None


def test_cursor_bound_to_range_and_revision(db_session):
    from app.application.occurrences import project_occurrences
    from app.core.errors import AppError
    import pytest
    actor, cal, _, _ = seed_series(db_session)
    page = project_occurrences(db_session,actor,cal['id'],date(2026,10,1),date(2026,10,8),'UTC',limit=2)
    assert not page['complete'] and len(page['items']) == 2
    second = project_occurrences(db_session,actor,cal['id'],date(2026,10,1),date(2026,10,8),'UTC',cursor=page['next_cursor'],limit=2)
    assert set(i['id'] for i in page['items']).isdisjoint(i['id'] for i in second['items'])
    with pytest.raises(AppError):
        project_occurrences(db_session,actor,cal['id'],date(2026,10,2),date(2026,10,8),'UTC',cursor=page['next_cursor'],limit=2)
