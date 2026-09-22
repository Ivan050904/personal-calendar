from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


Intent = Literal["CREATE", "UPDATE", "DELETE", "CLARIFY", "OFF_TOPIC"]
EntityType = Literal["event", "plan", "task", "list"]
RecurrenceScope = Literal["occurrence", "this_and_following", "entire_series"]


class TargetSelector(CamelModel):
    entity_type: EntityType
    query: str
    date: str | None = None
    time_hint: str | None = None


class StructuredAction(CamelModel):
    intent: Intent
    entity_type: EntityType | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    target_selector: TargetSelector | None = None
    recurrence_scope: RecurrenceScope | None = None
    missing_fields: list[str] = Field(default_factory=list)
    clarification: str | None = None
    message: str | None = None


class AIProvider(Protocol):
    name: str

    async def propose(self, *, user_message: str, context: dict[str, Any] | None = None) -> StructuredAction:
        """Return a structured calendar action proposal. Never mutates DB."""
