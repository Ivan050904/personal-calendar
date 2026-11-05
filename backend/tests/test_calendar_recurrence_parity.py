from datetime import date,datetime
from test_calendar_occurrences import seed_series


def test_iso_weekday_monday_and_sunday(db_session):
    from app.application.occurrences import project_occurrences
    actor,cal,event,rule=seed_series(db_session)
    rule.frequency='weekly';rule.weekdays=[1,7]
    db_session.flush()
    page=project_occurrences(db_session,actor,cal['id'],date(2026,10,1),date(2026,10,7),'UTC')
    assert [i['start_at'][:10] for i in page['items']]==['2026-10-04','2026-10-05']


def test_dst_gap_not_counted_fold_earlier(db_session):
    from app.application.occurrences import project_occurrences
    actor,cal,event,rule=seed_series(db_session)
    event.timezone='Europe/Berlin';event.start_at=datetime(2026,3,28,1,30);event.end_at=datetime(2026,3,28,2,30)
    rule.occurrence_count=2
    db_session.flush()
    page=project_occurrences(db_session,actor,cal['id'],date(2026,3,28),date(2026,3,30),'Europe/Berlin')
    assert [i['start_at'] for i in page['items']]==['2026-03-28T01:30:00Z','2026-03-30T00:30:00Z']
    event.start_at=datetime(2026,10,24,0,30);event.end_at=datetime(2026,10,24,1,30)
    db_session.flush()
    page=project_occurrences(db_session,actor,cal['id'],date(2026,10,25),date(2026,10,25),'Europe/Berlin')
    assert page['items'][0]['start_at']=='2026-10-25T00:30:00Z'


def test_monthly_clamps_31_to_february(db_session):
    from app.application.occurrences import project_occurrences
    actor,cal,event,rule=seed_series(db_session)
    rule.frequency='monthly';rule.day_of_month=31
    event.start_at=datetime(2026,1,31,9);event.end_at=datetime(2026,1,31,10)
    db_session.flush()
    page=project_occurrences(db_session,actor,cal['id'],date(2026,2,1),date(2026,2,28),'UTC')
    assert page['items'][0]['occurrence_key']=='2026-02-28T09:00'
