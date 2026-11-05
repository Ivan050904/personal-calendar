from datetime import date
from uuid import uuid4
import pytest
from app.core.errors import AppError
from app.core.calendar_actor import CalendarActor,ensure_actor_calendar


def setup_actor(db):
    actor=CalendarActor('command-owner','command-folio',frozenset({'calendar:write'}))
    cal=ensure_actor_calendar(db,actor,'UTC',str(uuid4()))
    return actor,cal


def test_replay_receipt_and_changed_body_conflict(db_session):
    from app.application.calendar_commands import execute_calendar_command
    actor,cal=setup_actor(db_session)
    request={'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Task','timezone':'UTC','due_date':'2026-10-08'}}
    one=execute_calendar_command(db_session,actor,request)
    two=execute_calendar_command(db_session,actor,request)
    assert one['entity']['id']==two['entity']['id'] and two['replayed']
    assert one['confirmation'] is None
    request['payload']['title']='Changed'
    with pytest.raises(AppError) as error:
        execute_calendar_command(db_session,actor,request)
    assert error.value.status_code==409


def test_revision_and_nullable_clear(db_session):
    from app.application.calendar_commands import execute_calendar_command
    actor,_=setup_actor(db_session)
    created=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Task','timezone':'UTC','due_date':'2026-10-08'}})['entity']
    patch={'command_id':str(uuid4()),'kind':'task','operation':'patch','entity_id':created['id'],'expected_revision':1,'payload':{'due_date':None}}
    updated=execute_calendar_command(db_session,actor,patch)['entity']
    assert updated['due_date'] is None and updated['revision']==2
    patch['command_id']=str(uuid4())
    with pytest.raises(AppError) as error:
        execute_calendar_command(db_session,actor,patch)
    assert error.value.status_code==409
