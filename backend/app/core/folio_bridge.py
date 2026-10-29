"""Folio calendar bridge (contract v2) over the single local calendar."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.application.entity_service import EntityService
from app.core.errors import AppError

SCOPES = frozenset(
    {
        "calendar:connect",
        "calendar:read",
        "calendar:write",
        "calendar:history",
        "calendar:reminders",
    }
)
OWNER_ID = "local"


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_bridge_token(token: str, secret: str, *, now: datetime | None = None) -> dict[str, Any]:
    if not secret.strip():
        raise AppError("unavailable", "Bridge is not configured", status_code=503)
    if token.count(".") != 2:
        raise AppError("unauthorized", "Invalid bridge credential", status_code=401)
    header_b64, payload_b64, signature_b64 = token.split(".")
    try:
        header = json.loads(_b64decode(header_b64))
        claims = json.loads(_b64decode(payload_b64))
        digest = hmac.new(
            secret.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        if header.get("alg") != "HS256" or not hmac.compare_digest(digest, _b64decode(signature_b64)):
            raise ValueError("bad signature")
        if not isinstance(claims, dict):
            raise ValueError("bad claims")
    except (ValueError, json.JSONDecodeError, UnicodeError):
        raise AppError("unauthorized", "Invalid bridge credential", status_code=401) from None
    current = now or datetime.now(UTC)
    timestamp = current.astimezone(UTC).timestamp()
    try:
        if claims.get("iss") != "folio" or claims.get("aud") != "personal-calendar":
            raise ValueError("audience")
        if claims.get("purpose") != "calendar_bridge":
            raise ValueError("purpose")
        for key in ("sub", "connection_id", "jti"):
            if not isinstance(claims.get(key), str) or not claims[key]:
                raise ValueError(key)
        for key in ("iat", "nbf", "exp"):
            if type(claims.get(key)) not in (int, float):
                raise ValueError(key)
        if not (0 < claims["exp"] - claims["iat"] <= 60):
            raise ValueError("lifetime")
        if not (claims["iat"] <= claims["nbf"] < claims["exp"]):
            raise ValueError("window")
        if claims["iat"] > timestamp + 30 or claims["nbf"] > timestamp + 30 or claims["exp"] <= timestamp - 30:
            raise ValueError("skew")
        scopes = claims.get("scopes")
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise ValueError("scopes")
        if not frozenset(scopes) <= SCOPES:
            raise ValueError("scope")
    except (TypeError, ValueError):
        raise AppError("unauthorized", "Invalid bridge credential", status_code=401) from None
    return claims


def require_scope(claims: dict[str, Any], scope: str) -> None:
    if scope not in claims.get("scopes", []):
        raise AppError("forbidden", "Calendar scope is required", status_code=403)


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise AppError("invalid_payload", "Invalid timezone", status_code=422) from exc


def _parse_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _stamp(value: str | None) -> str:
    parsed = _parse_instant(value) or datetime.now(UTC)
    return parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def calendar_payload(row: dict[str, Any]) -> dict[str, Any]:
    _zone(str(row.get("timezone") or ""))
    return {
        "id": row["id"],
        "name": row.get("name") or "Personal Calendar",
        "owner_id": OWNER_ID,
        "timezone": row["timezone"],
        "revision": 1,
        "created_at": _stamp(row.get("createdAt")),
        "updated_at": _stamp(row.get("updatedAt")),
    }


def ensure_local_calendar(db: Session, timezone_name: str) -> dict[str, Any]:
    _zone(timezone_name)
    service = EntityService(db)
    current = service.get_local_calendar()
    if current is not None:
        return calendar_payload(current)
    now = _stamp(None)
    created = service.put_entity(
        "calendars",
        {
            "id": str(uuid4()),
            "name": "Personal Calendar",
            "timezone": timezone_name,
            "createdAt": now,
            "updatedAt": now,
        },
    )
    return calendar_payload(created)


def _occurrence(
    *,
    calendar_id: str,
    entity_id: str,
    kind: str,
    title: str,
    description: str,
    timezone_name: str,
    start_at: datetime | None = None,
    end_at: datetime | None = None,
    all_day: bool = False,
    start_date: date | None = None,
    end_date_exclusive: date | None = None,
    due_date: date | None = None,
    completed: bool | None = None,
    color: str | None = None,
) -> dict[str, Any]:
    def instant(value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    return {
        "id": f"{kind}:{entity_id}",
        "calendar_id": calendar_id,
        "entity_id": entity_id,
        "kind": kind,
        "occurrence_key": None,
        "title": (title or "Без названия")[:255],
        "description": (description or "")[:10000],
        "start_at": instant(start_at),
        "end_at": instant(end_at),
        "timezone": timezone_name,
        "all_day": all_day,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date_exclusive": end_date_exclusive.isoformat() if end_date_exclusive else None,
        "due_date": due_date.isoformat() if due_date else None,
        "completed": completed,
        "revision": 1,
        "location": None,
        "color": color or None,
        "confirmation_status": None,
        "source_href": f"/?calendar_id={calendar_id}&kind={kind}&entity_id={entity_id}",
    }


def _overlaps(start: datetime, end: datetime, start_day: date, end_day: date, timezone_name: str) -> bool:
    zone = _zone(timezone_name)
    window_start = datetime.combine(start_day, time.min, tzinfo=zone)
    window_end = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=zone)
    return start < window_end and end > window_start


def _all_day_bounds(start: datetime, end: datetime, timezone_name: str) -> tuple[date, date]:
    zone = _zone(timezone_name)
    start_date = start.astimezone(zone).date()
    end_local = end.astimezone(zone)
    end_date = end_local.date()
    if end_local.timetz().replace(tzinfo=None) != time.min:
        end_date += timedelta(days=1)
    if end_date <= start_date:
        end_date = start_date + timedelta(days=1)
    return start_date, end_date


def build_agenda(
    db: Session,
    calendar: dict[str, Any],
    start_day: date,
    end_day: date,
    timezone_name: str,
) -> dict[str, Any]:
    if end_day < start_day or (end_day - start_day).days > 30:
        raise AppError("invalid_payload", "Invalid agenda range", status_code=422)
    zone_name = timezone_name or calendar["timezone"]
    _zone(zone_name)
    service = EntityService(db)
    calendar_id = calendar["id"]
    items: list[dict[str, Any]] = []
    overdue: list[dict[str, Any]] = []
    undated: list[dict[str, Any]] = []

    for event in service.list_entities("events", calendar_id):
        start = _parse_instant(event.get("startAt"))
        end = _parse_instant(event.get("endAt"))
        if start is None or end is None or end <= start:
            continue
        event_zone = str(event.get("timezone") or calendar["timezone"])
        if event.get("allDay"):
            start_date, end_exclusive = _all_day_bounds(start, end, event_zone)
            if start_date > end_day or end_exclusive <= start_day:
                continue
            items.append(
                _occurrence(
                    calendar_id=calendar_id,
                    entity_id=event["id"],
                    kind="event",
                    title=event.get("title") or "",
                    description=event.get("description") or "",
                    timezone_name=event_zone,
                    all_day=True,
                    start_date=start_date,
                    end_date_exclusive=end_exclusive,
                    color=event.get("color"),
                )
            )
            continue
        if not _overlaps(start, end, start_day, end_day, zone_name):
            continue
        items.append(
            _occurrence(
                calendar_id=calendar_id,
                entity_id=event["id"],
                kind="event",
                title=event.get("title") or "",
                description=event.get("description") or "",
                timezone_name=event_zone,
                start_at=start,
                end_at=end,
                color=event.get("color"),
            )
        )

    for plan in service.list_entities("plans", calendar_id):
        start = _parse_instant(plan.get("startAt"))
        end = _parse_instant(plan.get("endAt"))
        if start is None or end is None or end <= start:
            continue
        if not _overlaps(start, end, start_day, end_day, zone_name):
            continue
        items.append(
            _occurrence(
                calendar_id=calendar_id,
                entity_id=plan["id"],
                kind="plan",
                title=plan.get("title") or "",
                description=plan.get("description") or "",
                timezone_name=str(plan.get("timezone") or calendar["timezone"]),
                start_at=start,
                end_at=end,
                color=plan.get("color"),
            )
        )

    for task in service.list_entities("tasks", calendar_id):
        due_raw = task.get("dueDate")
        due = date.fromisoformat(due_raw[:10]) if due_raw else None
        row = _occurrence(
            calendar_id=calendar_id,
            entity_id=task["id"],
            kind="task",
            title=task.get("title") or "",
            description=task.get("description") or "",
            timezone_name=calendar["timezone"],
            due_date=due,
            completed=bool(task.get("completed")),
        )
        if due is None:
            undated.append(row)
        elif due < start_day and not task.get("completed"):
            overdue.append(row)
        elif start_day <= due <= end_day:
            items.append(row)

    now = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "contract_version": 2,
        "calendar_id": calendar_id,
        "calendar_timezone": calendar["timezone"],
        "timezone": zone_name,
        "from_date": start_day.isoformat(),
        "to_date": end_day.isoformat(),
        "server_now": now,
        "items": items,
        "overdue_tasks": overdue,
        "undated_tasks": undated,
        "next_cursor": None,
        "complete": True,
        "smart_day": None,
        "fetched_at": now,
        "freshness": "live",
    }
