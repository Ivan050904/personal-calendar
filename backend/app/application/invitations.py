"""Shared events (D38, wave 6): attendees by login, pending/accepted/declined.

The event lives in the organizer's calendar; only the organizer edits it. An attendee sees it
(as an incoming invitation until they answer), gets its changes in their own feed, and may only
change their own status.
"""
from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import select

from app.application.accounts import account_read, find_by_login
from app.application.occurrences import entity_read, project_occurrences
from app.application.webhooks import mark_pending
from app.core.calendar_actor import CalendarActor
from app.core.errors import AppError
from app.infrastructure.db import models as m

STATUSES = ("pending", "accepted", "declined")
READ = frozenset({"calendar:read"})


def organizer_id(db, event: m.EventModel) -> str:
    return db.get(m.CalendarModel, event.calendar_id).owner_id


def organizer_reader(db, event: m.EventModel) -> CalendarActor:
    """Projection helpers check calendar ownership, so attendee reads go through the organizer's identity."""
    return CalendarActor(organizer_id(db, event), None, READ)


def attendance(db, event_id: str, principal_id: str) -> m.EventAttendeeModel | None:
    return db.scalar(select(m.EventAttendeeModel).where(m.EventAttendeeModel.event_id == event_id,
                                                        m.EventAttendeeModel.principal_id == principal_id))


def attendee_ids(db, event_id: str) -> list[str]:
    return list(db.scalars(select(m.EventAttendeeModel.principal_id).where(m.EventAttendeeModel.event_id == event_id)))


def _actor_label(actor: CalendarActor) -> str:
    return "app:" + actor.client_id if actor.client_id else "user"


def record_change(db, owner_id: str, event: m.EventModel, operation: str, actor: CalendarActor) -> None:
    """A row in `owner_id`'s changes feed about an event that may live in someone else's calendar."""
    db.add(m.CalendarChangeModel(owner_id=owner_id, calendar_id=event.calendar_id, entity_id=event.id, kind="event",
                                 operation=operation, revision=event.revision, deleted=event.deleted_at is not None,
                                 actor=_actor_label(actor)))
    mark_pending(db, owner_id, event.calendar_id, actor.client_id)


def attendee_read(db, row: m.EventAttendeeModel) -> dict:
    person = db.get(m.CalendarPrincipalModel, row.principal_id)
    return {"id": row.id, "event_id": row.event_id, "login": person.login if person else None,
            "display_name": person.display_name if person else None, "status": row.status,
            "invited_at": row.invited_at.isoformat() + "Z",
            "responded_at": row.responded_at.isoformat() + "Z" if row.responded_at else None}


def invite(db, actor: CalendarActor, event: m.EventModel, login: str) -> tuple[m.EventAttendeeModel, bool]:
    """Returns (attendee, created). Inviting someone again is a no-op."""
    person = find_by_login(db, login)
    if person is None or not person.active:
        raise AppError("not_found", "Нет такого аккаунта", status_code=404)
    if person.id == actor.principal_id:
        raise AppError("validation_error", "Нельзя пригласить себя", status_code=422)
    existing = attendance(db, event.id, person.id)
    if existing is not None:
        return existing, False
    row = m.EventAttendeeModel(id=str(uuid4()), event_id=event.id, principal_id=person.id, status="pending",
                               invited_at=datetime.utcnow())
    db.add(row)
    record_change(db, person.id, event, "invited", actor)
    db.flush()
    return row, True


def respond(db, actor: CalendarActor, event: m.EventModel, status: str) -> m.EventAttendeeModel:
    if status not in ("accepted", "declined"):
        raise AppError("validation_error", "status: accepted или declined", status_code=422)
    row = attendance(db, event.id, actor.principal_id)
    if row is None:
        raise AppError("not_found", "Event not found", status_code=404)
    if row.status != status:
        row.status, row.responded_at = status, datetime.utcnow()
        record_change(db, organizer_id(db, event), event, "responded", actor)
        db.flush()
    return row


def mirror_change(db, actor: CalendarActor, event: m.EventModel, operation: str) -> None:
    """The organizer changed the event: every attendee's feed hears about it too."""
    for principal_id in attendee_ids(db, event.id):
        record_change(db, principal_id, event, operation, actor)


def my_invitations(db, actor: CalendarActor) -> list[dict]:
    rows = db.execute(select(m.EventAttendeeModel, m.EventModel)
                      .join(m.EventModel, m.EventModel.id == m.EventAttendeeModel.event_id)
                      .where(m.EventAttendeeModel.principal_id == actor.principal_id,
                             m.EventModel.deleted_at.is_(None))
                      .order_by(m.EventAttendeeModel.invited_at)).all()
    out = []
    for attendee, event in rows:
        organizer = db.get(m.CalendarPrincipalModel, organizer_id(db, event))
        out.append({**attendee_read(db, attendee), "event": entity_read(db, organizer_reader(db, event), event, "event"),
                    "organizer": account_read(organizer)})
    return out


def invitation_occurrences(db, actor: CalendarActor, from_day: date, to_day: date, display_zone: str) -> list[dict]:
    """Occurrences of events I was invited to and did not decline, for the board."""
    rows = db.execute(select(m.EventAttendeeModel, m.EventModel)
                      .join(m.EventModel, m.EventModel.id == m.EventAttendeeModel.event_id)
                      .where(m.EventAttendeeModel.principal_id == actor.principal_id,
                             m.EventAttendeeModel.status != "declined", m.EventModel.deleted_at.is_(None))).all()
    by_calendar: dict[str, dict[str, m.EventAttendeeModel]] = {}
    events: dict[str, m.EventModel] = {}
    for attendee, event in rows:
        by_calendar.setdefault(event.calendar_id, {})[event.id] = attendee
        events[event.calendar_id] = event
    items = []
    for calendar_id, wanted in by_calendar.items():
        reader = organizer_reader(db, events[calendar_id])
        cursor = None
        while True:
            page = project_occurrences(db, reader, calendar_id, from_day, to_day, display_zone, cursor=cursor)
            for item in page["items"]:
                attendee = wanted.get(item["entity_id"])
                if attendee is not None and item["kind"] == "event":
                    item.pop("_section", None)
                    items.append({**item, "invitation": {"id": attendee.id, "status": attendee.status}})
            if page["complete"]:
                break
            cursor = page["next_cursor"]
    return items
