from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.application.entity_service import EntityService
from app.core.errors import AppError
from app.infrastructure.db.session import get_db

router = APIRouter(tags=["entities"])

COLLECTIONS = [
    "calendars",
    "events",
    "recurrenceRules",
    "eventExceptions",
    "plans",
    "planTasks",
    "tasks",
    "lists",
    "listItems",
    "categories",
    "reminders",
]


def get_service(db: Session = Depends(get_db)) -> EntityService:
    return EntityService(db)


@router.get("/calendars/local")
def local_calendar(service: EntityService = Depends(get_service)) -> dict[str, Any] | None:
    return service.get_local_calendar()


@router.get("/entities/{collection}")
def list_collection(
    collection: str,
    calendarId: str | None = None,
    service: EntityService = Depends(get_service),
) -> list[dict[str, Any]]:
    if collection not in COLLECTIONS:
        raise AppError("not_found", f"Unknown collection: {collection}", status_code=404)
    return service.list_entities(collection, calendarId)


@router.get("/entities/{collection}/{entity_id}")
def get_one(
    collection: str,
    entity_id: str,
    service: EntityService = Depends(get_service),
) -> dict[str, Any]:
    if collection not in COLLECTIONS:
        raise AppError("not_found", f"Unknown collection: {collection}", status_code=404)
    return service.get_entity(collection, entity_id)


@router.put("/entities/{collection}/{entity_id}")
def put_one(
    collection: str,
    entity_id: str,
    payload: dict[str, Any],
    service: EntityService = Depends(get_service),
) -> dict[str, Any]:
    if collection not in COLLECTIONS:
        raise AppError("not_found", f"Unknown collection: {collection}", status_code=404)
    body = dict(payload)
    body["id"] = entity_id
    return service.put_entity(collection, body)


@router.delete("/entities/{collection}/{entity_id}")
def delete_one(
    collection: str,
    entity_id: str,
    service: EntityService = Depends(get_service),
) -> dict[str, Any]:
    if collection not in COLLECTIONS:
        raise AppError("not_found", f"Unknown collection: {collection}", status_code=404)
    return service.delete_entity(collection, entity_id)
