"""Invitations API v2 (D38, wave 6): attendees by login, answers, the invitee's view."""
from datetime import date

from fastapi import APIRouter, Body, Depends, Query, Response
from sqlalchemy.orm import Session

from app.application import invitations
from app.core.calendar_actor import CalendarActor, require_actor, require_owned_calendar, require_scope
from app.core.errors import AppError
from app.infrastructure.db.models import CalendarPrincipalModel, EventModel
from app.infrastructure.db.session import get_db

router = APIRouter(prefix='/v2', tags=['invitations'])


def _event(db: Session, event_id: str) -> EventModel:
    row = db.get(EventModel, event_id)
    if row is None or row.deleted_at is not None:
        raise AppError('not_found', 'Event not found', status_code=404)
    return row


def _as_attendee(actor: CalendarActor) -> None:
    if actor.client_id:
        require_scope(actor, 'sharing.invite')


def _body_text(body: dict, key: str) -> str:
    if set(body) != {key} or not isinstance(body[key], str):
        raise AppError('validation_error', f'Body must be {{"{key}": "…"}}', status_code=422)
    return body[key]


@router.post('/events/{event_id}/attendees', status_code=201)
def invite(event_id: str, response: Response, body: dict = Body(...),
           db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    event = _event(db, event_id)
    require_owned_calendar(db, actor, event.calendar_id)
    if actor.client_id:
        # An app invites people only to events in its own calendar (it created them with events.write).
        require_scope(actor, 'sharing.invite')
        if event.calendar_id != actor.app_calendar_id:
            raise AppError('forbidden', 'Apps invite only to events in their own calendar', status_code=403)
    else:
        require_scope(actor, 'calendar:write')
    row, created = invitations.invite(db, actor, event, _body_text(body, 'login'))
    db.commit()
    if not created:
        response.status_code = 200
    return invitations.attendee_read(db, row)


@router.get('/events/{event_id}/attendees')
def attendees(event_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    event = _event(db, event_id)
    if invitations.organizer_id(db, event) == actor.principal_id:
        from app.api.routes.entities_v2 import can_read
        can_read(actor, event.calendar_id)
    elif invitations.attendance(db, event.id, actor.principal_id) is not None:
        _as_attendee(actor)
    else:
        raise AppError('not_found', 'Event not found', status_code=404)
    organizer = db.get(CalendarPrincipalModel, invitations.organizer_id(db, event))
    from app.application.accounts import account_read
    return {'organizer': account_read(organizer),
            'attendees': [invitations.attendee_read(db, row) for row in
                          [invitations.attendance(db, event.id, pid) for pid in invitations.attendee_ids(db, event.id)]]}


@router.patch('/events/{event_id}/attendees/me')
def answer(event_id: str, body: dict = Body(...), db: Session = Depends(get_db),
           actor: CalendarActor = Depends(require_actor)):
    _as_attendee(actor)
    row = invitations.respond(db, actor, _event(db, event_id), _body_text(body, 'status'))
    db.commit()
    return invitations.attendee_read(db, row)


@router.get('/invitations')
def mine(db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _as_attendee(actor)
    return invitations.my_invitations(db, actor)


@router.get('/invitations/occurrences')
def occurrences(from_day: date = Query(alias='from'), to_day: date = Query(alias='to'), timezone: str = 'UTC',
                db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    _as_attendee(actor)
    if to_day < from_day or (to_day - from_day).days > 62:
        raise AppError('validation_error', 'Range must be 1–63 days', status_code=422)
    from app.application.calendar_time import zone
    zone(timezone)
    return {'items': invitations.invitation_occurrences(db, actor, from_day, to_day, timezone)}
