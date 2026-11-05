from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.calendar_time import zone


class RecurrenceRead(BaseModel):
    model_config = ConfigDict(extra='forbid')
    frequency: Literal['daily','weekly','weekdays','monthly']
    interval: int = Field(default=1,ge=1)
    weekdays: list[int] | None = None
    day_of_month: int | None = Field(default=None,ge=1,le=31)
    until_date: date | None = None
    occurrence_count: int | None = Field(default=None,ge=1)
    dst_gap_policy: Literal['skip'] = 'skip'
    dst_fold_policy: Literal['earlier'] = 'earlier'

    @field_validator('weekdays')
    @classmethod
    def weekdays_valid(cls,values):
        if values is not None and (len(set(values)) != len(values) or any(type(v) is not int or v < 1 or v > 7 for v in values)):
            raise ValueError('Weekdays are ISO 1..7')
        return values


class CalendarEntityPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None,min_length=1,max_length=255)
    description: str | None = Field(default=None,max_length=10000)
    timezone: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    start_date: date | None = None
    end_date_exclusive: date | None = None
    due_date: date | None = None
    completed: bool | None = None
    location: str | None = Field(default=None,max_length=255)
    color: str | None = Field(default=None,max_length=32)
    recurrence: RecurrenceRead | None = None
    status: Literal['occurred','not_occurred','revoked'] | None = None
    happened_date: date | None = None
    happened_at: datetime | None = None
    expected_confirmation_revision: int | None = Field(default=None,ge=1)

    @field_validator('start_at','end_at','happened_at')
    @classmethod
    def aware(cls,value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError('Explicit datetime offset required')
        return value

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,value):
        if value:
            zone(value)
        return value

    @field_validator('title')
    @classmethod
    def title_text(cls,value):
        if value is not None and not value.strip():
            raise ValueError('Title is required')
        return value


class CalendarWriteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    command_id: UUID
    kind: Literal['event','task','plan']
    operation: Literal['create','patch','delete','restore','complete','confirm']
    entity_id: str | None = Field(default=None,min_length=1,max_length=64)
    occurrence_key: str | None = Field(default=None,max_length=100)
    scope: Literal['this','thisAndFollowing','series'] | None = None
    expected_revision: int | None = Field(default=None,ge=1)
    calendar_id: str | None = Field(default=None,min_length=1,max_length=64)  # create only; default «Личное»
    payload: CalendarEntityPayload

    @model_validator(mode='after')
    def contract(self):
        if self.calendar_id is not None and self.operation != 'create':
            raise ValueError('calendar_id is only accepted on create')
        if self.operation == 'create':
            if self.entity_id is not None or not self.payload.title or not self.payload.timezone:
                raise ValueError('Creation requires title/timezone and no existing id')
        elif self.entity_id is None or self.expected_revision is None:
            raise ValueError('Mutation requires entity id/revision')
        if self.operation == 'complete' and self.kind != 'task':
            raise ValueError('Only tasks complete')
        if self.operation == 'confirm' and (self.payload.status is None or self.payload.happened_date is None):
            raise ValueError('Confirmation requires status and happened_date')
        return self
