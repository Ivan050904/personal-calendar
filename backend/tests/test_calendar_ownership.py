from datetime import datetime
from uuid import uuid4

import pytest

from app.application.entity_service import EntityService
from app.core.errors import AppError


def test_foreign_calendar_is_hidden_for_read_write_delete(db_session):
    from app.core.calendar_actor import CalendarActor, ensure_actor_calendar
    alice = CalendarActor("alice", "folio-alice", frozenset({"calendar:read", "calendar:write"}))
    bob = CalendarActor("bob", "folio-bob", frozenset({"calendar:read", "calendar:write"}))
    calendar = ensure_actor_calendar(db_session, bob, "UTC", str(uuid4()))
    service = EntityService(db_session, alice)
    assert service.list_entities("calendars") == []
    for action in [lambda: service.get_entity("calendars", calendar["id"]),
                   lambda: service.delete_entity("calendars", calendar["id"]),
                   lambda: service.put_entity("events", {"id": "attack", "calendarId": calendar["id"]})]:
        with pytest.raises(AppError) as error:
            action()
        assert error.value.status_code == 404


def test_onboarding_default_is_idempotent(db_session):
    from app.core.calendar_actor import CalendarActor, ensure_actor_calendar
    actor = CalendarActor("alice", "folio-alice", frozenset())
    one = ensure_actor_calendar(db_session, actor, "Europe/Berlin", str(uuid4()))
    two = ensure_actor_calendar(db_session, actor, "UTC", str(uuid4()))
    assert one["id"] == two["id"]
    assert two["timezone"] == "Europe/Berlin"


@pytest.mark.parametrize('collection',['calendars','events','recurrenceRules','eventExceptions','plans','planTasks','tasks','lists','listItems','categories','reminders'])
def test_all_collections_hide_foreign_reads_edits_deletes_and_restore(db_session,collection):
    from app.core.calendar_actor import CalendarActor
    from calendar_integration_fixtures import owner_entities
    _,rows=owner_entities(db_session,'isolated-bob')
    actor=CalendarActor('isolated-alice','folio-isolated-alice',frozenset({'calendar:read','calendar:write'}))
    service=EntityService(db_session,actor)
    row=rows[collection]
    assert service.list_entities(collection)==[]
    for operation in [lambda:service.get_entity(collection,row['id']),lambda:service.put_entity(collection,{**row,'deletedAt':None}),lambda:service.delete_entity(collection,row['id'],row['revision'])]:
        with pytest.raises(AppError) as error:
            operation()
        assert error.value.status_code==404
    assert service._repo(collection)._serialize(db_session.get(service._repo(collection).model,row['id']))['id']==row['id']
