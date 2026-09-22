from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.repositories import Repositories


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None or key == "deletedAt"}


class EntityService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repos = Repositories(session)

    def _repo(self, name: str):
        mapping = {
            "calendars": self.repos.calendars,
            "events": self.repos.events,
            "recurrenceRules": self.repos.recurrence_rules,
            "eventExceptions": self.repos.event_exceptions,
            "plans": self.repos.plans,
            "planTasks": self.repos.plan_tasks,
            "tasks": self.repos.tasks,
            "lists": self.repos.lists,
            "listItems": self.repos.list_items,
            "categories": self.repos.categories,
            "reminders": self.repos.reminders,
        }
        if name not in mapping:
            raise AppError("not_found", f"Unknown collection: {name}", status_code=404)
        return mapping[name]

    def list_entities(self, collection: str, calendar_id: str | None = None) -> list[dict[str, Any]]:
        repo = self._repo(collection)
        if calendar_id and hasattr(repo, "list_by_calendar_id"):
            return repo.list_by_calendar_id(calendar_id)
        return repo.list()

    def get_entity(self, collection: str, entity_id: str) -> dict[str, Any]:
        entity = self._repo(collection).get(entity_id)
        if entity is None:
            raise AppError("not_found", f"{collection} item not found", status_code=404)
        return entity

    def put_entity(self, collection: str, payload: dict[str, Any]) -> dict[str, Any]:
        if "id" not in payload:
            raise AppError("validation_error", "id is required", status_code=422)
        saved = self._repo(collection).put(_strip_none(payload))
        self.session.commit()
        return saved

    def delete_entity(self, collection: str, entity_id: str) -> dict[str, Any]:
        repo = self._repo(collection)
        existing = repo.get(entity_id)
        if existing is None:
            raise AppError("not_found", f"{collection} item not found", status_code=404)
        repo.soft_delete(entity_id)
        self.session.commit()
        return {"id": entity_id, "deleted": True}

    def get_local_calendar(self) -> dict[str, Any] | None:
        return self.repos.calendars.get_local_calendar()
