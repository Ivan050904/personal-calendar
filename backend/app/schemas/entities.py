from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class CalendarDTO(CamelModel):
    id: str
    name: str
    timezone: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class EventDTO(CamelModel):
    id: str
    calendar_id: str
    title: str
    description: str = ""
    start_at: str
    end_at: str
    timezone: str
    all_day: bool = False
    category_id: str | None = None
    color: str
    recurrence_rule_id: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class RecurrenceRuleDTO(CamelModel):
    id: str
    frequency: str
    interval: int = 1
    weekdays: list[int] = Field(default_factory=list)
    day_of_month: int | None = None
    until_date: str | None = None
    occurrence_count: int | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class EventExceptionDTO(CamelModel):
    id: str
    event_id: str
    recurrence_rule_id: str
    occurrence_key: str
    type: Literal["modified", "cancelled"]
    override_start_at: str | None = None
    override_end_at: str | None = None
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class PlanDTO(CamelModel):
    id: str
    calendar_id: str
    title: str
    description: str | None = None
    start_at: str
    end_at: str
    timezone: str
    color: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class PlanTaskDTO(CamelModel):
    id: str
    plan_id: str
    title: str
    completed: bool = False
    order: int = 0
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class TaskDTO(CamelModel):
    id: str
    calendar_id: str
    title: str
    description: str | None = None
    due_date: str | None = None
    recurrence_rule_id: str | None = None
    completed: bool = False
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class TaskListDTO(CamelModel):
    id: str
    calendar_id: str
    title: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class TaskListItemDTO(CamelModel):
    id: str
    list_id: str
    title: str
    completed: bool = False
    order: int = 0
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class CategoryDTO(CamelModel):
    id: str
    calendar_id: str
    name: str
    created_at: str
    updated_at: str
    deleted_at: str | None = None


class ReminderDTO(CamelModel):
    id: str
    event_id: str
    offset_minutes: int
    created_at: str
    updated_at: str
    deleted_at: str | None = None


EntityDict = dict[str, Any]
