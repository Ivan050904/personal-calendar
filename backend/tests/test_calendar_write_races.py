from uuid import uuid4
import pytest
from app.core.errors import AppError
from test_calendar_commands import setup_actor


def test_generic_put_cannot_bypass_revision(db_session):
    from app.application.calendar_commands import execute_calendar_command
    from app.application.entity_service import EntityService
    actor,cal=setup_actor(db_session)
    created=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Original','timezone':'UTC'}})['entity']
    service=EntityService(db_session,actor)
    existing=service.get_entity('tasks',created['id'])
    assert existing['revision']==1
    existing.pop('revision')
    existing['title']='Overwritten'
    with pytest.raises(AppError) as error:
        service.put_entity('tasks',existing)
    assert error.value.status_code==428
