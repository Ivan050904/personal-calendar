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
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utcnow, onupdate=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class CalendarPrincipalModel(Base):
    __tablename__ = "calendar_principals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    folio_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    legacy_alias: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    login: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True, default=utcnow)


class CalendarModel(Base, TimestampMixin):
    __tablename__ = "calendars"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("calendar_principals.id"), nullable=True, index=True)
    default_owner: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    # D36: personal («Личное», one per account) | app (one per connected app, wave 3) | user
    kind: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    source_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#0f766e")
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class EventModel(Base, TimestampMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendars.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date_exclusive: Mapped[date | None] = mapped_column(Date, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    recurrence_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # D37: the app's own id for this event; (calendar, client, external_id) is unique.
    source_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (UniqueConstraint('calendar_id', 'source_client_id', 'external_id', name='uq_events_external_id'),)


class RecurrenceRuleModel(Base, TimestampMixin):
    __tablename__ = "recurrence_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("calendar_principals.id"), nullable=True, index=True)
    dst_gap_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="skip")
    dst_fold_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="early")
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
    override_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
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
    # D37: the app's own id (wave 5); (calendar, client, external_id) is unique.
    source_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (UniqueConstraint('calendar_id', 'source_client_id', 'external_id', name='uq_plans_external_id'),)


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
    recurrence_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # D37: the app's own id (wave 5); (calendar, client, external_id) is unique.
    source_client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    __table_args__ = (UniqueConstraint('calendar_id', 'source_client_id', 'external_id', name='uq_tasks_external_id'),)


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
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_time: Mapped[str | None] = mapped_column(String(5), nullable=True)


class SettingModel(Base, TimestampMixin):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("owner_id", "key", name="uq_owner_setting"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("calendar_principals.id"), nullable=True, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class DraftModel(Base):
    __tablename__ = "ai_drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("calendar_principals.id"), nullable=True, index=True)
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


class CalendarSessionModel(Base):
    __tablename__ = "calendar_sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    principal_id: Mapped[str] = mapped_column(String(64), ForeignKey("calendar_principals.id"), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class CalendarWriteReceiptModel(Base):
    __tablename__ = 'calendar_write_receipts'
    owner_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendar_principals.id'), primary_key=True)
    command_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    body_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)


class CalendarConfirmationModel(Base):
    __tablename__ = 'calendar_confirmations'
    __table_args__ = (UniqueConstraint('owner_id', 'entity_id', 'occurrence_ref', name='uq_calendar_fact_occurrence'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendar_principals.id'), nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendars.id'), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    occurrence_ref: Mapped[str] = mapped_column(String(100), nullable=False, default='')
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    happened_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    happened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    time_zone: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    audit: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    previous_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class CalendarChangeModel(Base):
    __tablename__ = 'calendar_changes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendar_principals.id'), nullable=False, index=True)
    calendar_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendars.id'), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'user' or 'app:<client_id>' (D37); NULL on rows written before wave 4 means 'user'.
    actor: Mapped[str | None] = mapped_column(String(80), nullable=True)


# --- OAuth 2.0 for connected apps (D35, wave 3). Secrets, codes and tokens are stored only as SHA-256.

class OAuthClientModel(Base):
    __tablename__ = 'oauth_clients'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    secret_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_type: Mapped[str] = mapped_column(String(16), nullable=False)  # confidential | public
    redirect_uris: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    allowed_scopes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)


class OAuthGrantModel(Base):
    __tablename__ = 'oauth_grants'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), ForeignKey('calendar_principals.id'), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey('oauth_clients.id'), nullable=False, index=True)
    scopes: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    readable_calendar_ids: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    app_calendar_id: Mapped[str | None] = mapped_column(String(64), ForeignKey('calendars.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class OAuthAuthorizationCodeModel(Base):
    __tablename__ = 'oauth_authorization_codes'
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey('oauth_grants.id'), nullable=False, index=True)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(2048), nullable=False)
    code_challenge: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)


class OAuthTokenModel(Base):
    __tablename__ = 'oauth_tokens'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey('oauth_grants.id'), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(8), nullable=False)  # access | refresh
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)


class WebhookSubscriptionModel(Base):
    """D37: a hint 'there are changes' to an app's URL; the feed stays the source of truth.

    `secret` is kept as is: the server must sign with it, so a hash would not do."""
    __tablename__ = 'webhook_subscriptions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey('oauth_grants.id'), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    first_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utcnow)
