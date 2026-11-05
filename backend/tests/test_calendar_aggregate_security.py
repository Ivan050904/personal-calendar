from datetime import datetime
from uuid import uuid4
import pytest
from app.core.errors import AppError
from test_calendar_commands import setup_actor


def test_generic_delete_requires_revision(db_session):
    from app.application.calendar_commands import execute_calendar_command
    from app.application.entity_service import EntityService
    actor,_=setup_actor(db_session)
    task=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'task','operation':'create','payload':{'title':'Keep','timezone':'UTC'}})['entity']
    with pytest.raises(AppError) as error:
        EntityService(db_session,actor).delete_entity('tasks',task['id'])
    assert error.value.status_code==428


def test_child_write_bumps_parent_and_returns_no_foreign_rows(db_session):
    from app.application.calendar_commands import execute_calendar_command
    from app.application.entity_service import EntityService
    from app.infrastructure.db.models import PlanModel
    actor,_=setup_actor(db_session)
    plan=execute_calendar_command(db_session,actor,{'command_id':str(uuid4()),'kind':'plan','operation':'create','payload':{'title':'Plan','timezone':'UTC','start_at':'2026-10-08T09:00:00Z','end_at':'2026-10-08T10:00:00Z'}})['entity']
    service=EntityService(db_session,actor)
    now='2026-10-08T00:00:00Z'
    service.put_entity('planTasks',{'id':str(uuid4()),'planId':plan['id'],'title':'Step','completed':False,'order':0,'createdAt':now,'updatedAt':now})
    assert db_session.get(PlanModel,plan['id']).revision==2
