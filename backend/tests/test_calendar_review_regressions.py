from datetime import date, timedelta
from uuid import uuid4

import pytest

from app.application.calendar_commands import execute_calendar_command
from app.application.occurrences import project_occurrences
from app.api.routes.integration import occurrence
from app.core.calendar_actor import CalendarActor, ensure_actor_calendar


def actor_calendar(db, timezone='UTC'):
    actor = CalendarActor('review-owner', 'review-folio', frozenset({'calendar:read', 'calendar:write'}))
    return actor, ensure_actor_calendar(db, actor, timezone, str(uuid4()))


def command(db, actor, kind, operation, payload, **kwargs):
    return execute_calendar_command(db, actor, dict(command_id=str(uuid4()), kind=kind, operation=operation, payload=payload, **kwargs))


def test_correcting_old_completion_keeps_next_rolling_task_open(db_session):
    actor, _ = actor_calendar(db_session)
    task = command(db_session, actor, 'task', 'create', {'title': 'Daily', 'timezone': 'UTC', 'due_date': '2026-10-09', 'recurrence': {'frequency': 'daily', 'interval': 1}})['entity']
    first = command(db_session, actor, 'task', 'complete', {'happened_date': '2026-10-09'}, entity_id=task['id'], expected_revision=1, occurrence_key='2026-10-09')
    corrected = command(db_session, actor, 'task', 'confirm', {'status': 'occurred', 'happened_date': '2026-10-08', 'expected_confirmation_revision': 1}, entity_id=task['id'], expected_revision=2, occurrence_key='2026-10-09')
    assert corrected['confirmation']['id'] == first['confirmation']['id']
    assert corrected['confirmation']['happened_date'] == '2026-10-08'
    assert corrected['entity']['due_date'] == '2026-10-10'
    assert corrected['entity']['completed'] is False


@pytest.mark.parametrize(('timezone', 'start', 'end', 'split', 'expected'), [
    ('UTC', '2026-10-09T09:00:00Z', '2026-10-09T10:00:00Z', '2026-10-10T09:00', ['2026-10-09', '2026-10-10', '2026-10-11']),
    ('Europe/Berlin', '2026-03-28T02:30:00+01:00', '2026-03-28T03:30:00+01:00', '2026-03-30T02:30', ['2026-03-28', '2026-03-30', '2026-03-31']),
])
def test_split_preserves_remaining_valid_count(db_session, timezone, start, end, split, expected):
    actor, cal = actor_calendar(db_session, timezone)
    event = command(db_session, actor, 'event', 'create', {'title': 'Three', 'timezone': timezone, 'start_at': start, 'end_at': end, 'recurrence': {'frequency': 'daily', 'interval': 1, 'occurrence_count': 3}})['entity']
    command(db_session, actor, 'event', 'patch', {'title': 'Following'}, entity_id=event['id'], expected_revision=1, occurrence_key=split, scope='thisAndFollowing')
    rows = project_occurrences(db_session, actor, cal['id'], date.fromisoformat(expected[0]), date.fromisoformat(expected[-1]) + timedelta(days=7), timezone)['items']
    assert sorted(row['occurrence_key'][:10] for row in rows) == expected


def test_exact_moved_occurrence_uses_entity_local_day(db_session):
    actor, cal = actor_calendar(db_session, 'Asia/Vladivostok')
    event = command(db_session, actor, 'event', 'create', {'title': 'Moved', 'timezone': 'Asia/Vladivostok', 'start_at': '2026-10-09T09:00:00+10:00', 'end_at': '2026-10-09T10:00:00+10:00', 'recurrence': {'frequency': 'daily', 'interval': 1}})['entity']
    key = '2026-10-09T09:00'
    command(db_session, actor, 'event', 'patch', {'start_at': '2026-10-10T08:00:00+10:00', 'end_at': '2026-10-10T09:00:00+10:00'}, entity_id=event['id'], expected_revision=1, occurrence_key=key, scope='this')
    exact = occurrence(event['id'], key, db_session, actor)
    agenda = project_occurrences(db_session, actor, cal['id'], date(2026, 10, 10), date(2026, 10, 10), 'Asia/Vladivostok')['items']
    assert exact['start_at'] == '2026-10-09T22:00:00Z'
    assert exact['id'] in [row['id'] for row in agenda]
