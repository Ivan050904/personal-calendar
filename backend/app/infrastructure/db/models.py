from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.session import Base


def utcnow() -> datetime:
    return datetime.utcnow()


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class CalendarModel(Base, TimestampMixin):
    __tablename__ = "calendars"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)


class EventModel(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    recurrence_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class RecurrenceRuleModel(Base, TimestampMixin):
    __tablename__ = "recurrence_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weekdays: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    until_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    occurrence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class EventExceptionModel(Base, TimestampMixin):
    __tablename__ = "event_exceptions"
    __table_args__ = (UniqueConstraint("event_id", "occurrence_key", name="uq_event_occurrence"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.id"), nullable=False, index=True)
    recurrence_rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    occurrence_key: Mapped[str] = mapped_column(String(64), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    override_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    override_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class PlanModel(Base, TimestampMixin):
    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)


class PlanTaskModel(Base, TimestampMixin):
    __tablename__ = "plan_tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("plans.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TaskModel(Base, TimestampMixin):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class TaskListModel(Base, TimestampMixin):
    __tablename__ = "lists"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)


class TaskListItemModel(Base, TimestampMixin):
    __tablename__ = "list_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    list_id: Mapped[str] = mapped_column(String(64), ForeignKey("lists.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CategoryModel(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class ReminderModel(Base, TimestampMixin):
    __tablename__ = "reminders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), ForeignKey("events.id"), nullable=False, index=True)
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False)


class SettingModel(Base, TimestampMixin):
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class DraftModel(Base):
    __tablename__ = "ai_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    target: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    missing_fields: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="collecting")
    clarification: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence_scope: Mapped[str | None] = mapped_column(String(32), nullable=True)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
