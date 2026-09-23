from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.repositories import Repositories


def _now() -> datetime:
    return datetime.utcnow().replace(microsecond=0)


def _iso(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat() + "Z"


def _to_utc_naive(value: str | datetime, calendar_tz: str | None) -> datetime:
    """Normalize event bounds to naive UTC.

    - Strings with Z/offset are converted to UTC.
    - Naive strings (AI wall-clock) are interpreted in the calendar timezone.
    """
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if calendar_tz:
            try:
                parsed = parsed.replace(tzinfo=ZoneInfo(calendar_tz))
            except Exception:
                parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


class DomainExecutor:
    """Applies confirmed draft operations to persistence."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repos = Repositories(session)

    def execute(self, draft: dict[str, Any]) -> dict[str, Any]:
        operation = draft.get("operation")
        entity_type = draft.get("entityType")
        payload = draft.get("payload") or {}

        if operation == "CREATE":
            return self._create(entity_type, payload)
        if operation == "UPDATE":
            return self._update(entity_type, draft.get("target"), payload, draft.get("recurrenceScope"))
        if operation == "DELETE":
            return self._delete(entity_type, draft.get("target"), draft.get("recurrenceScope"))
        raise AppError("validation_error", f"Unsupported operation: {operation}", status_code=422)

    def _update(
        self,
        entity_type: str | None,
        target: dict[str, Any] | None,
        payload: dict[str, Any],
        recurrence_scope: str | None,
    ) -> dict[str, Any]:
        if not target or not target.get("id"):
            raise AppError("clarification_required", "Resolved target is required", status_code=422)
        if entity_type == "event" and target.get("recurrenceRuleId") and not recurrence_scope:
            raise AppError(
                "clarification_required",
                "Recurrence scope is required",
                status_code=422,
                details={"allowed": ["occurrence", "this_and_following", "entire_series"]},
            )
        entity_id = target["id"]
        if entity_type == "event":
            existing = self.repos.events.get(entity_id)
            if not existing:
                raise AppError("not_found", "Event not found", status_code=404)
            merged = {**existing, **{k: v for k, v in {
                "title": payload.get("title"),
                "description": payload.get("description"),
                "startAt": payload.get("start") or payload.get("startAt"),
                "endAt": payload.get("end") or payload.get("endAt"),
                "color": payload.get("color"),
            }.items() if v is not None}, "updatedAt": _iso(_now())}
            saved = self.repos.events.put(merged)
            return {"entityType": "event", "entity": saved, "recurrenceScope": recurrence_scope}
        if entity_type == "task":
            existing = self.repos.tasks.get(entity_id)
            if not existing:
                raise AppError("not_found", "Task not found", status_code=404)
            merged = {**existing, **{k: v for k, v in {
                "title": payload.get("title"),
                "description": payload.get("description"),
                "dueDate": payload.get("dueDate"),
                "completed": payload.get("completed"),
            }.items() if v is not None}, "updatedAt": _iso(_now())}
            return {"entityType": "task", "entity": self.repos.tasks.put(merged)}
        if entity_type == "plan":
            existing = self.repos.plans.get(entity_id)
            if not existing:
                raise AppError("not_found", "Plan not found", status_code=404)
            merged = {**existing, **{k: v for k, v in {
                "title": payload.get("title"),
                "description": payload.get("description"),
                "startAt": payload.get("start") or payload.get("startAt"),
                "endAt": payload.get("end") or payload.get("endAt"),
                "color": payload.get("color"),
            }.items() if v is not None}, "updatedAt": _iso(_now())}
            return {"entityType": "plan", "entity": self.repos.plans.put(merged)}
        if entity_type == "list":
            existing = self.repos.lists.get(entity_id)
            if not existing:
                raise AppError("not_found", "List not found", status_code=404)
            merged = {**existing, **{k: v for k, v in {
                "title": payload.get("title"),
            }.items() if v is not None}, "updatedAt": _iso(_now())}
            return {"entityType": "list", "entity": self.repos.lists.put(merged)}
        raise AppError("validation_error", "Unsupported entityType for UPDATE", status_code=422)

    def _delete(
        self,
        entity_type: str | None,
        target: dict[str, Any] | None,
        recurrence_scope: str | None,
    ) -> dict[str, Any]:
        if not target or not target.get("id"):
            raise AppError("clarification_required", "Resolved target is required", status_code=422)
        if entity_type == "event" and target.get("recurrenceRuleId") and not recurrence_scope:
            raise AppError("clarification_required", "Recurrence scope is required", status_code=422)
        entity_id = target["id"]
        repo = {
            "event": self.repos.events,
            "plan": self.repos.plans,
            "task": self.repos.tasks,
            "list": self.repos.lists,
        }.get(entity_type or "")
        if repo is None:
            raise AppError("validation_error", "Unsupported entityType for DELETE", status_code=422)
        if not repo.soft_delete(entity_id):
            raise AppError("not_found", f"{entity_type} not found", status_code=404)
        return {"entityType": entity_type, "deletedId": entity_id, "recurrenceScope": recurrence_scope}

    def _create(self, entity_type: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        if entity_type == "event":
            return {"entityType": "event", "entity": self._create_event(payload)}
        if entity_type == "plan":
            return {"entityType": "plan", "entity": self._create_plan(payload)}
        if entity_type == "task":
            return {"entityType": "task", "entity": self._create_task(payload)}
        if entity_type == "list":
            return {"entityType": "list", "entity": self._create_list(payload)}
        raise AppError("validation_error", "entityType is required for CREATE", status_code=422)

    def _calendar_id(self, payload: dict[str, Any]) -> str:
        if payload.get("calendarId"):
            return str(payload["calendarId"])
        local = self.repos.calendars.get_local_calendar()
        if local:
            return local["id"]
        now = _now()
        created = self.repos.calendars.put(
            {
                "id": str(uuid4()),
                "name": "Personal Calendar",
                "timezone": payload.get("timezone") or "UTC",
                "createdAt": _iso(now),
                "updatedAt": _iso(now),
            }
        )
        return created["id"]

    def _create_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        start = payload.get("start") or payload.get("startAt")
        end = payload.get("end") or payload.get("endAt")
        if not title or not start:
            raise AppError("validation_error", "Event requires title and start", status_code=422)
        calendar_tz = payload.get("timezone") or "UTC"
        start_dt = _to_utc_naive(str(start), calendar_tz)
        if end:
            end_dt = _to_utc_naive(str(end), calendar_tz)
        elif payload.get("durationMinutes"):
            end_dt = start_dt + timedelta(minutes=int(payload["durationMinutes"]))
        else:
            end_dt = start_dt + timedelta(hours=1)
        if end_dt <= start_dt:
            raise AppError("validation_error", "end must be after start", status_code=422)
        now = _now()
        recurrence_rule_id = payload.get("recurrenceRuleId")
        recurrence = payload.get("recurrence")
        if not recurrence_rule_id and isinstance(recurrence, dict) and recurrence.get("frequency"):
            recurrence_rule_id = str(uuid4())
            self.repos.recurrence_rules.put(
                {
                    "id": recurrence_rule_id,
                    "frequency": recurrence["frequency"],
                    "interval": int(recurrence.get("interval") or 1),
                    "weekdays": list(recurrence.get("weekdays") or []),
                    "dayOfMonth": recurrence.get("dayOfMonth"),
                    "untilDate": recurrence.get("untilDate"),
                    "occurrenceCount": recurrence.get("occurrenceCount"),
                    "createdAt": _iso(now),
                    "updatedAt": _iso(now),
                }
            )
        return self.repos.events.put(
            {
                "id": str(uuid4()),
                "calendarId": self._calendar_id(payload),
                "title": title,
                "description": payload.get("description") or payload.get("notes") or "",
                "startAt": _iso(start_dt),
                "endAt": _iso(end_dt),
                "timezone": calendar_tz,
                "allDay": bool(payload.get("allDay", False)),
                "categoryId": payload.get("categoryId"),
                "color": payload.get("color") or "#0f766e",
                "recurrenceRuleId": recurrence_rule_id,
                "createdAt": _iso(now),
                "updatedAt": _iso(now),
            }
        )

    def _create_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        start = payload.get("start") or payload.get("startAt")
        end = payload.get("end") or payload.get("endAt")
        if not title or not start or not end:
            raise AppError("validation_error", "Plan requires title, start and end", status_code=422)
        now = _now()
        calendar_tz = payload.get("timezone") or "UTC"
        plan = self.repos.plans.put(
            {
                "id": str(uuid4()),
                "calendarId": self._calendar_id(payload),
                "title": title,
                "description": payload.get("description"),
                "startAt": _iso(_to_utc_naive(str(start), calendar_tz)),
                "endAt": _iso(_to_utc_naive(str(end), calendar_tz)),
                "timezone": calendar_tz,
                "color": payload.get("color") or "#0f766e",
                "createdAt": _iso(now),
                "updatedAt": _iso(now),
            }
        )
        for index, item in enumerate(payload.get("tasks") or payload.get("planTasks") or []):
            title_item = item if isinstance(item, str) else item.get("title")
            if not title_item:
                continue
            self.repos.plan_tasks.put(
                {
                    "id": str(uuid4()),
                    "planId": plan["id"],
                    "title": str(title_item).strip(),
                    "completed": False,
                    "order": index,
                    "createdAt": _iso(now),
                    "updatedAt": _iso(now),
                }
            )
        return plan

    def _create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        if not title:
            raise AppError("validation_error", "Task requires title", status_code=422)
        now = _now()
        return self.repos.tasks.put(
            {
                "id": str(uuid4()),
                "calendarId": self._calendar_id(payload),
                "title": title,
                "description": payload.get("description"),
                "dueDate": payload.get("dueDate"),
                "recurrenceRuleId": payload.get("recurrenceRuleId"),
                "completed": False,
                "createdAt": _iso(now),
                "updatedAt": _iso(now),
            }
        )

    def _create_list(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = (payload.get("title") or "").strip()
        if not title:
            raise AppError("validation_error", "List requires title", status_code=422)
        now = _now()
        task_list = self.repos.lists.put(
            {
                "id": str(uuid4()),
                "calendarId": self._calendar_id(payload),
                "title": title,
                "createdAt": _iso(now),
                "updatedAt": _iso(now),
            }
        )
        for index, item in enumerate(payload.get("items") or []):
            title_item = item if isinstance(item, str) else item.get("title")
            if not title_item:
                continue
            self.repos.list_items.put(
                {
                    "id": str(uuid4()),
                    "listId": task_list["id"],
                    "title": str(title_item).strip(),
                    "completed": False,
                    "order": index,
                    "createdAt": _iso(now),
                    "updatedAt": _iso(now),
                }
            )
        return task_list
