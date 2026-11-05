from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.application.agenda import build_agenda
from app.api.routes.integration import owned_default
from app.core.calendar_actor import CalendarActor, require_actor, require_scope
from app.infrastructure.db.session import get_db

router = APIRouter(tags=['occurrences'])


@router.get('/occurrences')
def occurrences(calendar_id:str,from_day:date=Query(alias='from'),to_day:date=Query(alias='to'),timezone:str|None=None,cursor:str|None=None,limit:int=Query(default=500,ge=1,le=500),db:Session=Depends(get_db),actor:CalendarActor=Depends(require_actor)):
    require_scope(actor,'calendar:read')
    cal = owned_default(db,actor,calendar_id)
    return build_agenda(db,actor,cal.id,from_day,to_day,timezone or cal.timezone,cursor=cursor,limit=limit)
