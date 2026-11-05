from datetime import date, datetime, timezone
from test_calendar_occurrences import seed_series


def test_agenda_server_projection_has_explicit_nulls(db_session):
    from app.application.agenda import build_agenda
    actor, cal, _, _ = seed_series(db_session)
    page = build_agenda(db_session,actor,cal['id'],date(2026,10,8),date(2026,10,8),'UTC',now=datetime(2026,10,8,9,30,tzinfo=timezone.utc))
    assert page['contract_version'] == 2
    assert page['smart_day']['current']['title'] == 'Series'
    assert page['items'][0]['location'] is None
    assert page['items'][0]['confirmation_status'] is None
