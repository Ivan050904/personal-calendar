from uuid import uuid4
import pytest
from app.core.errors import AppError
from test_calendar_commands import setup_actor


def test_ai_update_preserves_proposed_revision(db_session):
    from app.application.calendar_commands import execute_calendar_command
    from app.application.drafts import DraftService
    actor,_=setup_actor(db_session)
    task=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Original','timezone':'UTC'}})['entity']
    drafts=DraftService(db_session,actor)
    draft=drafts.create_from_action(action={'intent':'UPDATE','entityType':'task','targetSelector':{'id':task['id']},'payload':{'title':'AI title'}})
    execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'patch','entity_id':task['id'],'expected_revision':1,'payload':{'title':'Other client'}})
    with pytest.raises(AppError) as error:
        drafts.confirm(draft['draftId'])
    assert error.value.status_code==409
