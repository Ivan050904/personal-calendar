from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.application.entity_service import EntityService
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.folio_bridge import (
    build_agenda,
    calendar_payload,
    ensure_local_calendar,
    require_scope,
    verify_bridge_token,
)
from app.infrastructure.db.session import get_db

router = APIRouter(prefix="/integration/v1", tags=["folio-bridge"])


class ConnectBody(BaseModel):
    timezone: str = Field(min_length=1, max_length=64)


def bridge_claims(request: Request) -> dict[str, Any]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise AppError("unauthorized", "Bridge credential is required", status_code=401)
    settings = get_settings()
    return verify_bridge_token(header[7:].strip(), settings.calendar_bridge_secret)


def _calendar_or_404(db: Session) -> dict[str, Any]:
    current = EntityService(db).get_local_calendar()
    if current is None:
        raise AppError("calendar_not_found", "Connect calendar first", status_code=404)
    return calendar_payload(current)


@router.post("/connect")
def connect(body: ConnectBody, request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    claims = bridge_claims(request)
    require_scope(claims, "calendar:connect")
    return ensure_local_calendar(db, body.timezone)


@router.get("/status")
def status(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    claims = bridge_claims(request)
    require_scope(claims, "calendar:read")
    return {
        "contract_version": 2,
        "calendar": _calendar_or_404(db),
        "capabilities": {"read": True, "write": False, "history": False, "reminders": False},
    }


@router.get("/agenda")
def agenda(
    request: Request,
    from_day: date = Query(alias="from"),
    to_day: date = Query(alias="to"),
    timezone: str = Query(min_length=1),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    claims = bridge_claims(request)
    require_scope(claims, "calendar:read")
    calendar = _calendar_or_404(db)
    return build_agenda(db, calendar, from_day, to_day, timezone)
