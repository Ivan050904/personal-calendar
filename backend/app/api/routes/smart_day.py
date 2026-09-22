from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.application.smart_day import SmartDaySnapshot, build_smart_day_snapshot, plan_progress
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories import Repositories

router = APIRouter(tags=["smart-day"])


@router.get("/smart-day", response_model=SmartDaySnapshot)
def smart_day(
    now: str | None = Query(default=None),
    calendarId: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> SmartDaySnapshot:
    repos = Repositories(db)
    now_iso = now or datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    events = repos.events.list_by_calendar_id(calendarId) if calendarId else repos.events.list()
    plans = repos.plans.list_by_calendar_id(calendarId) if calendarId else repos.plans.list()
    # Filter to items overlapping the local calendar day of `now` is done loosely:
    # client usually passes today's events; here we include all active timed items.
    return build_smart_day_snapshot(events, plans, now_iso)


@router.get("/plans/{plan_id}/progress")
def get_plan_progress(plan_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    repos = Repositories(db)
    tasks = repos.plan_tasks.list_by_plan_id(plan_id)
    return plan_progress(tasks)
