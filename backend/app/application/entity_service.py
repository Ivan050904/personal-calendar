from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.repositories import Repositories


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None or key == "deletedAt"}


class EntityService:
    def __init__(self, session: Session, actor=None) -> None:
        self.session = session
        self.actor = actor
        self.repos = Repositories(session, actor)

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
        if calendar_id and self.actor:
            from app.core.calendar_actor import require_owned_calendar
            require_owned_calendar(self.session, self.actor, calendar_id)
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
        repo = self._repo(collection)
        row = self.session.get(repo.model,payload['id'])
        if self.actor:
            from app.core.calendar_actor import require_scope
            from app.application.calendar_commands import cas,add_change
            require_scope(self.actor,'calendar:write')
            repo._validate_parents(payload)
            if row is not None:
                repo._require_owned(row)
                if collection == 'tasks' and 'completed' in payload and payload['completed'] != row.completed:
                    raise AppError('revision_required','Task completion requires an authoritative command',status_code=428)
                if collection in {'events','tasks'} and row.recurrence_rule_id and payload.get('deletedAt') is None and row.deleted_at is None:
                    raise AppError('revision_required','Recurring edits require a scoped command',status_code=428)
                cas(self.session,row,payload.get('revision'))
        saved = repo.put(payload)
        if self.actor:
            self._record_parent(collection,self.session.get(repo.model,payload['id']),'patch' if row else 'create')
        self.session.commit()
        return saved

    def delete_entity(self, collection: str, entity_id: str, expected_revision: int | None = None) -> dict[str, Any]:
        repo = self._repo(collection)
        existing = repo.get(entity_id)
        if existing is None:
            raise AppError("not_found", f"{collection} item not found", status_code=404)
        if self.actor:
            from app.core.calendar_actor import require_scope
            require_scope(self.actor,'calendar:write')
            row=self.session.get(repo.model,entity_id)
            if getattr(row,'recurrence_rule_id',None):
                raise AppError('revision_required','Recurring deletion requires a scoped command',status_code=428)
            from app.application.calendar_commands import cas
            cas(self.session,self.session.get(repo.model,entity_id),expected_revision)
        repo.soft_delete(entity_id)
        if self.actor:
            self._record_parent(collection,self.session.get(repo.model,entity_id),'delete')
        self.session.commit()
        return {"id": entity_id, "deleted": True}

    def get_local_calendar(self) -> dict[str, Any] | None:
        return self.repos.calendars.get_local_calendar()

    def _record_parent(self,collection,row,operation):
        from sqlalchemy import select,update
        from app.infrastructure.db import models as m
        from app.application.calendar_commands import add_change
        if collection == 'calendars':
            return
        if hasattr(row,'calendar_id'):
            add_change(self.session,self.actor,row,{'events':'event','tasks':'task','plans':'plan'}.get(collection,collection),operation)
            return
        parents=[]
        if hasattr(row,'event_id'):
            parents=[self.session.get(m.EventModel,row.event_id)]
        elif hasattr(row,'plan_id'):
            parents=[self.session.get(m.PlanModel,row.plan_id)]
        elif hasattr(row,'list_id'):
            parents=[self.session.get(m.TaskListModel,row.list_id)]
        elif collection == 'recurrenceRules':
            parents=[*self.session.scalars(select(m.EventModel).where(m.EventModel.recurrence_rule_id == row.id)),*self.session.scalars(select(m.TaskModel).where(m.TaskModel.recurrence_rule_id == row.id))]
        for parent in parents:
            if parent is None:
                continue
            self.repos.events._require_owned(parent)
            self.session.execute(update(type(parent)).where(type(parent).id == parent.id).values(revision=type(parent).revision+1).execution_options(synchronize_session=False))
            self.session.refresh(parent)
            add_change(self.session,self.actor,parent,'event' if isinstance(parent,m.EventModel) else 'plan' if isinstance(parent,m.PlanModel) else 'task' if isinstance(parent,m.TaskModel) else 'list',operation)
