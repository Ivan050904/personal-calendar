from uuid import uuid4
from datetime import datetime,timezone
from test_calendar_commands import setup_actor


def test_count_two_ends_and_undo_reopens_same_last_fact(db_session):
    from app.application.calendar_commands import execute_calendar_command
    actor,_=setup_actor(db_session)
    task=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Twice','timezone':'UTC','due_date':'2026-10-01','recurrence':{'frequency':'daily','interval':1,'occurrence_count':2}}})['entity']
    first=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'complete','entity_id':task['id'],'expected_revision':1,'payload':{'happened_date':'2026-10-08'}})
    second=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'complete','entity_id':task['id'],'expected_revision':2,'payload':{'happened_date':'2026-10-09'}})
    assert second['entity']['completed'] is True
    last=second['confirmation']
    revoked=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'confirm','entity_id':task['id'],'expected_revision':3,'occurrence_key':last['occurrence_key'],'payload':{'status':'revoked','happened_date':last['happened_date'],'expected_confirmation_revision':last['revision']}})
    assert revoked['confirmation']['id']==last['id'] and revoked['entity']['completed'] is False


def test_initial_completion_defaults_to_server_time_and_source_day(db_session):
    from app.application.calendar_commands import execute_calendar_command
    actor,_=setup_actor(db_session)
    task=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Past due','timezone':'UTC','due_date':'2026-01-01'}})['entity']
    before=datetime.now(timezone.utc)
    result=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'complete','entity_id':task['id'],'expected_revision':1,'payload':{}})
    assert result['confirmation']['occurrence_key']=='2026-01-01'
    assert result['confirmation']['happened_date']==before.date().isoformat()
    assert result['confirmation']['happened_at'] is not None
