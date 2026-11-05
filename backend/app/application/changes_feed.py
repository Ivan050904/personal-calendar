"""Changes feed v2 (D37, wave 4): `calendar_changes` filtered to what one reader may see, with `actor`."""
from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select

from app.application.occurrences import decode_cursor, encode_cursor
from app.infrastructure.db import models as m
from app.infrastructure.repositories import _iso


def feed_bound(principal_id: str, grant_id: str | None) -> str:
    # A cursor works only for the reader it was issued to (the UI or one app connection).
    return f"v2changes|{principal_id}|{grant_id or 'ui'}"


def _scope(stmt, principal_id: str, calendar_ids: Collection[str] | None):
    stmt = stmt.where(m.CalendarChangeModel.owner_id == principal_id)
    return stmt if calendar_ids is None else stmt.where(m.CalendarChangeModel.calendar_id.in_(list(calendar_ids)))


def feed_cursor(db, principal_id: str, grant_id: str | None, calendar_ids: Collection[str] | None) -> str:
    last = db.scalar(_scope(select(m.CalendarChangeModel.id), principal_id, calendar_ids)
                     .order_by(m.CalendarChangeModel.id.desc()).limit(1)) or 0
    return encode_cursor(feed_bound(principal_id, grant_id), last)


def feed_page(db, principal_id: str, grant_id: str | None, calendar_ids: Collection[str] | None,
              cursor: str | None, limit: int) -> dict:
    """`calendar_ids=None` means every calendar of the account (the calendar UI)."""
    bound = feed_bound(principal_id, grant_id)
    offset = decode_cursor(cursor, bound)
    rows = db.scalars(_scope(select(m.CalendarChangeModel), principal_id, calendar_ids)
                      .where(m.CalendarChangeModel.id > offset).order_by(m.CalendarChangeModel.id).limit(limit + 1)).all()
    page = rows[:limit]
    continuation = encode_cursor(bound, page[-1].id if page else offset)
    return {"items": [{"id": str(r.id), "calendar_id": r.calendar_id, "entity_id": r.entity_id, "kind": r.kind,
                       "operation": r.operation, "revision": r.revision, "deleted": r.deleted,
                       "actor": r.actor or "user", "changed_at": _iso(r.changed_at)} for r in page],
            "next_cursor": continuation, "complete": len(rows) <= limit, "server_now": _iso(datetime.utcnow())}
