from datetime import datetime
from app.infrastructure.db.models import CalendarModel


def test_unknown_legacy_owner_is_reported_without_assignment(db_session):
    from app.application.calendar_owner_migration import ownership_dry_run
    row=CalendarModel(id='verified-old-id',name='Legacy',timezone='UTC',created_at=datetime(2020,1,1),updated_at=datetime(2020,1,1))
    db_session.add(row);db_session.flush()
    report=ownership_dry_run(db_session)
    assert report['ready'] is False
    assert {'kind':'unknown_owner','entity_id':'verified-old-id'} in report['conflicts']
    assert row.owner_id is None and row.created_at==datetime(2020,1,1)
