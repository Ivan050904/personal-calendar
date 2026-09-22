from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db import models as m

TModel = TypeVar("TModel")


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return value.isoformat()


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _parse_date(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


class SqlEntityRepository(Generic[TModel]):
    model: type[TModel]
    include_deleted: bool = False

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, entity_id: str) -> dict[str, Any] | None:
        row = self.session.get(self.model, entity_id)
        if row is None:
            return None
        if not self.include_deleted and getattr(row, "deleted_at", None) is not None:
            return None
        return self.to_dict(row)

    def list(self) -> list[dict[str, Any]]:
        stmt = select(self.model)
        if not self.include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        rows = self.session.scalars(stmt).all()
        return [self.to_dict(row) for row in rows]

    def put(self, entity: dict[str, Any]) -> dict[str, Any]:
        row = self.session.get(self.model, entity["id"])
        if row is None:
            row = self.from_dict(entity)
            self.session.add(row)
        else:
            self.apply_dict(row, entity)
        self.session.flush()
        return self.to_dict(row)

    def soft_delete(self, entity_id: str, deleted_at: datetime | None = None) -> bool:
        row = self.session.get(self.model, entity_id)
        if row is None:
            return False
        row.deleted_at = deleted_at or datetime.utcnow()
        row.updated_at = datetime.utcnow()
        self.session.flush()
        return True

    def to_dict(self, row: TModel) -> dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError

    def from_dict(self, entity: dict[str, Any]) -> TModel:  # pragma: no cover - abstract
        raise NotImplementedError

    def apply_dict(self, row: TModel, entity: dict[str, Any]) -> None:
        fresh = self.from_dict(entity)
        for column in row.__table__.columns:  # type: ignore[attr-defined]
            setattr(row, column.name, getattr(fresh, column.name))


class CalendarRepository(SqlEntityRepository[m.CalendarModel]):
    model = m.CalendarModel

    def get_local_calendar(self) -> dict[str, Any] | None:
        items = self.list()
        if not items:
            return None

        def created_key(item: dict[str, Any]) -> str:
            return str(item.get("createdAt") or item.get("id") or "")

        # Prefer the newest seeded Personal Calendar; otherwise earliest for stability.
        personal = [item for item in items if str(item.get("name") or "") == "Personal Calendar"]
        if personal:
            personal.sort(key=created_key, reverse=True)
            return personal[0]
        items.sort(key=created_key)
        return items[0]

    def to_dict(self, row: m.CalendarModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "timezone": row.timezone,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.CalendarModel:
        return m.CalendarModel(
            id=entity["id"],
            name=entity["name"],
            timezone=entity["timezone"],
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class CalendarScopedRepository(SqlEntityRepository[TModel], Generic[TModel]):
    def list_by_calendar_id(self, calendar_id: str) -> list[dict[str, Any]]:
        stmt = select(self.model).where(self.model.calendar_id == calendar_id)  # type: ignore[attr-defined]
        if not self.include_deleted and hasattr(self.model, "deleted_at"):
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return [self.to_dict(row) for row in self.session.scalars(stmt).all()]


class EventRepository(CalendarScopedRepository[m.EventModel]):
    model = m.EventModel

    def to_dict(self, row: m.EventModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "calendarId": row.calendar_id,
            "title": row.title,
            "description": row.description,
            "startAt": _iso(row.start_at),
            "endAt": _iso(row.end_at),
            "timezone": row.timezone,
            "allDay": row.all_day,
            "categoryId": row.category_id,
            "color": row.color,
            "recurrenceRuleId": row.recurrence_rule_id,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.EventModel:
        return m.EventModel(
            id=entity["id"],
            calendar_id=entity["calendarId"],
            title=entity["title"],
            description=entity.get("description") or "",
            start_at=_parse_dt(entity["startAt"]),
            end_at=_parse_dt(entity["endAt"]),
            timezone=entity["timezone"],
            all_day=bool(entity.get("allDay", False)),
            category_id=entity.get("categoryId"),
            color=entity["color"],
            recurrence_rule_id=entity.get("recurrenceRuleId"),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class RecurrenceRuleRepository(SqlEntityRepository[m.RecurrenceRuleModel]):
    model = m.RecurrenceRuleModel

    def to_dict(self, row: m.RecurrenceRuleModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "frequency": row.frequency,
            "interval": row.interval,
            "weekdays": list(row.weekdays or []),
            "dayOfMonth": row.day_of_month,
            "untilDate": _iso(row.until_date),
            "occurrenceCount": row.occurrence_count,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.RecurrenceRuleModel:
        return m.RecurrenceRuleModel(
            id=entity["id"],
            frequency=entity["frequency"],
            interval=int(entity.get("interval", 1)),
            weekdays=list(entity.get("weekdays") or []),
            day_of_month=entity.get("dayOfMonth"),
            until_date=_parse_date(entity.get("untilDate")),
            occurrence_count=entity.get("occurrenceCount"),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class EventExceptionRepository(SqlEntityRepository[m.EventExceptionModel]):
    model = m.EventExceptionModel

    def to_dict(self, row: m.EventExceptionModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "eventId": row.event_id,
            "recurrenceRuleId": row.recurrence_rule_id,
            "occurrenceKey": row.occurrence_key,
            "type": row.type,
            "overrideStartAt": _iso(row.override_start_at),
            "overrideEndAt": _iso(row.override_end_at),
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.EventExceptionModel:
        return m.EventExceptionModel(
            id=entity["id"],
            event_id=entity["eventId"],
            recurrence_rule_id=entity["recurrenceRuleId"],
            occurrence_key=entity["occurrenceKey"],
            type=entity["type"],
            override_start_at=_parse_dt(entity.get("overrideStartAt")),
            override_end_at=_parse_dt(entity.get("overrideEndAt")),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class PlanRepository(CalendarScopedRepository[m.PlanModel]):
    model = m.PlanModel

    def to_dict(self, row: m.PlanModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "calendarId": row.calendar_id,
            "title": row.title,
            "description": row.description,
            "startAt": _iso(row.start_at),
            "endAt": _iso(row.end_at),
            "timezone": row.timezone,
            "color": row.color,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.PlanModel:
        return m.PlanModel(
            id=entity["id"],
            calendar_id=entity["calendarId"],
            title=entity["title"],
            description=entity.get("description"),
            start_at=_parse_dt(entity["startAt"]),
            end_at=_parse_dt(entity["endAt"]),
            timezone=entity["timezone"],
            color=entity["color"],
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class PlanTaskRepository(SqlEntityRepository[m.PlanTaskModel]):
    model = m.PlanTaskModel

    def list_by_plan_id(self, plan_id: str) -> list[dict[str, Any]]:
        stmt = select(m.PlanTaskModel).where(m.PlanTaskModel.plan_id == plan_id)
        if not self.include_deleted:
            stmt = stmt.where(m.PlanTaskModel.deleted_at.is_(None))
        return [self.to_dict(row) for row in self.session.scalars(stmt).all()]

    def to_dict(self, row: m.PlanTaskModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "planId": row.plan_id,
            "title": row.title,
            "completed": row.completed,
            "order": row.order,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.PlanTaskModel:
        return m.PlanTaskModel(
            id=entity["id"],
            plan_id=entity["planId"],
            title=entity["title"],
            completed=bool(entity.get("completed", False)),
            order=int(entity.get("order", 0)),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class TaskRepository(CalendarScopedRepository[m.TaskModel]):
    model = m.TaskModel

    def to_dict(self, row: m.TaskModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "calendarId": row.calendar_id,
            "title": row.title,
            "description": row.description,
            "dueDate": _iso(row.due_date),
            "completed": row.completed,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.TaskModel:
        return m.TaskModel(
            id=entity["id"],
            calendar_id=entity["calendarId"],
            title=entity["title"],
            description=entity.get("description"),
            due_date=_parse_date(entity.get("dueDate")),
            completed=bool(entity.get("completed", False)),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class ListRepository(CalendarScopedRepository[m.TaskListModel]):
    model = m.TaskListModel

    def to_dict(self, row: m.TaskListModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "calendarId": row.calendar_id,
            "title": row.title,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.TaskListModel:
        return m.TaskListModel(
            id=entity["id"],
            calendar_id=entity["calendarId"],
            title=entity["title"],
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class ListItemRepository(SqlEntityRepository[m.TaskListItemModel]):
    model = m.TaskListItemModel

    def list_by_list_id(self, list_id: str) -> list[dict[str, Any]]:
        stmt = select(m.TaskListItemModel).where(m.TaskListItemModel.list_id == list_id)
        if not self.include_deleted:
            stmt = stmt.where(m.TaskListItemModel.deleted_at.is_(None))
        return [self.to_dict(row) for row in self.session.scalars(stmt).all()]

    def to_dict(self, row: m.TaskListItemModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "listId": row.list_id,
            "title": row.title,
            "completed": row.completed,
            "order": row.order,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.TaskListItemModel:
        return m.TaskListItemModel(
            id=entity["id"],
            list_id=entity["listId"],
            title=entity["title"],
            completed=bool(entity.get("completed", False)),
            order=int(entity.get("order", 0)),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class CategoryRepository(CalendarScopedRepository[m.CategoryModel]):
    model = m.CategoryModel

    def to_dict(self, row: m.CategoryModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "calendarId": row.calendar_id,
            "name": row.name,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.CategoryModel:
        return m.CategoryModel(
            id=entity["id"],
            calendar_id=entity["calendarId"],
            name=entity["name"],
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class ReminderRepository(SqlEntityRepository[m.ReminderModel]):
    model = m.ReminderModel

    def list_by_event_id(self, event_id: str) -> list[dict[str, Any]]:
        stmt = select(m.ReminderModel).where(m.ReminderModel.event_id == event_id)
        if not self.include_deleted:
            stmt = stmt.where(m.ReminderModel.deleted_at.is_(None))
        return [self.to_dict(row) for row in self.session.scalars(stmt).all()]

    def to_dict(self, row: m.ReminderModel) -> dict[str, Any]:
        return {
            "id": row.id,
            "eventId": row.event_id,
            "offsetMinutes": row.offset_minutes,
            "createdAt": _iso(row.created_at),
            "updatedAt": _iso(row.updated_at),
            "deletedAt": _iso(row.deleted_at),
        }

    def from_dict(self, entity: dict[str, Any]) -> m.ReminderModel:
        return m.ReminderModel(
            id=entity["id"],
            event_id=entity["eventId"],
            offset_minutes=int(entity["offsetMinutes"]),
            created_at=_parse_dt(entity["createdAt"]) or datetime.utcnow(),
            updated_at=_parse_dt(entity["updatedAt"]) or datetime.utcnow(),
            deleted_at=_parse_dt(entity.get("deletedAt")),
        )


class Repositories:
    def __init__(self, session: Session) -> None:
        self.calendars = CalendarRepository(session)
        self.events = EventRepository(session)
        self.recurrence_rules = RecurrenceRuleRepository(session)
        self.event_exceptions = EventExceptionRepository(session)
        self.plans = PlanRepository(session)
        self.plan_tasks = PlanTaskRepository(session)
        self.tasks = TaskRepository(session)
        self.lists = ListRepository(session)
        self.list_items = ListItemRepository(session)
        self.categories = CategoryRepository(session)
        self.reminders = ReminderRepository(session)
