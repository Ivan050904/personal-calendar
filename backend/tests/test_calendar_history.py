from uuid import uuid4
import pytest
from app.core.errors import AppError
from test_calendar_commands import setup_actor


def test_rolling_completion_preserves_reference_and_happened_date(db_session):
    from app.application.calendar_commands import execute_calendar_command
    actor,_=setup_actor(db_session)
    task=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Daily','timezone':'UTC','due_date':'2026-10-01','recurrence':{'frequency':'daily','interval':1}}})['entity']
    complete={'command_id':str(uuid4()),'kind':'task','operation':'complete','entity_id':task['id'],'expected_revision':1,'occurrence_key':'2026-10-01','payload':{'happened_date':'2026-10-08'}}
    result=execute_calendar_command(db_session,actor,complete)
    assert result['confirmation']['occurrence_key']=='2026-10-01'
    assert result['confirmation']['happened_date']=='2026-10-08'
    assert result['entity']['due_date']=='2026-10-09'
    assert execute_calendar_command(db_session,actor,complete)['confirmation']['id']==result['confirmation']['id']
    second=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'complete','entity_id':task['id'],'expected_revision':2,'occurrence_key':'2026-10-09','payload':{'happened_date':'2026-10-09'}})
    undo={'command_id':str(uuid4()),'kind':'task','operation':'confirm','entity_id':task['id'],'expected_revision':3,'occurrence_key':'2026-10-01','payload':{'status':'revoked','happened_date':'2026-10-08','expected_confirmation_revision':1}}
    with pytest.raises(AppError) as error:
        execute_calendar_command(db_session,actor,undo)
    assert error.value.status_code==409
