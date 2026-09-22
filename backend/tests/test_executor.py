from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.application.drafts import DraftService
from app.application.executor import DomainExecutor
from app.infrastructure.repositories import Repositories


def test_execute_create_task(db_session: Session):
    repos = Repositories(db_session)
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    repos.calendars.put(
        {
            "id": "cal-exec",
            "name": "Local",
            "timezone": "UTC",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()

    executor = DomainExecutor(db_session)
    result = executor.execute(
        {
            "operation": "CREATE",
            "entityType": "task",
            "payload": {"title": "Buy milk", "dueDate": "2026-09-20", "calendarId": "cal-exec"},
        }
    )
    db_session.commit()
    assert result["entityType"] == "task"
    assert result["entity"]["title"] == "Buy milk"
    assert repos.tasks.get(result["entity"]["id"])["dueDate"] == "2026-09-20"


def test_confirm_ready_task_draft_executes(db_session: Session):
    repos = Repositories(db_session)
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    repos.calendars.put(
        {
            "id": "cal-exec-2",
            "name": "Local",
            "timezone": "UTC",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()

    drafts = DraftService(db_session)
    draft = drafts.create_from_action(
        action={
            "intent": "CREATE",
            "entityType": "task",
            "payload": {"title": "Write tests", "calendarId": "cal-exec-2"},
            "missingFields": [],
        }
    )
    assert draft["status"] == "ready"
    confirmed = drafts.confirm(draft["draftId"])
    assert confirmed["status"] == "confirmed"
    assert confirmed["result"]["executed"] is True
    # idempotent
    again = drafts.confirm(draft["draftId"])
    assert again["status"] == "confirmed"
    assert again["result"]["idempotent"] is True
    assert len(repos.tasks.list_by_calendar_id("cal-exec-2")) == 1
