from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.infrastructure.repositories import Repositories


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def test_get_local_calendar_prefers_personal_name(repos: Repositories, db_session: Session):
    older = "1970-01-01T00:00:00"
    newer = "2026-09-18T12:00:00"
    repos.calendars.put(
        {
            "id": "cal-noise-old",
            "name": "Noise",
            "timezone": "UTC",
            "createdAt": older,
            "updatedAt": older,
        }
    )
    repos.calendars.put(
        {
            "id": "cal-personal",
            "name": "Personal Calendar",
            "timezone": "Asia/Vladivostok",
            "createdAt": newer,
            "updatedAt": newer,
        }
    )
    db_session.commit()
    local = repos.calendars.get_local_calendar()
    assert local is not None
    assert local["id"] == "cal-personal"


def test_calendar_and_event_roundtrip(repos: Repositories, db_session: Session):
    now = _now()
    calendar = repos.calendars.put(
        {
            "id": "cal-1",
            "name": "Local",
            "timezone": "Asia/Vladivostok",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()

    start = datetime.utcnow().replace(microsecond=0)
    end = start + timedelta(hours=1)
    event = repos.events.put(
        {
            "id": "evt-1",
            "calendarId": calendar["id"],
            "title": "Standup",
            "description": "",
            "startAt": start.isoformat(),
            "endAt": end.isoformat(),
            "timezone": "Asia/Vladivostok",
            "allDay": False,
            "color": "#0d9488",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()

    assert repos.calendars.get("cal-1")["id"] == "cal-1"
    local = repos.calendars.get_local_calendar()
    assert local is not None
    assert local["id"] in {item["id"] for item in repos.calendars.list()}
    assert repos.events.get("evt-1")["title"] == "Standup"
    listed = repos.events.list_by_calendar_id("cal-1")
    assert len(listed) == 1
    assert listed[0]["id"] == event["id"]


def test_task_due_date_is_date_only(repos: Repositories, db_session: Session):
    now = _now()
    repos.calendars.put(
        {
            "id": "cal-2",
            "name": "Local",
            "timezone": "UTC",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    task = repos.tasks.put(
        {
            "id": "task-1",
            "calendarId": "cal-2",
            "title": "Buy milk",
            "dueDate": "2026-09-20",
            "completed": False,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()
    loaded = repos.tasks.get("task-1")
    assert loaded is not None
    assert loaded["dueDate"] == "2026-09-20"
    assert task["dueDate"] == "2026-09-20"


def test_soft_delete_hides_from_list(repos: Repositories, db_session: Session):
    now = _now()
    repos.calendars.put(
        {
            "id": "cal-3",
            "name": "Local",
            "timezone": "UTC",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.plans.put(
        {
            "id": "plan-1",
            "calendarId": "cal-3",
            "title": "Sprint",
            "startAt": now,
            "endAt": (datetime.utcnow() + timedelta(hours=2)).replace(microsecond=0).isoformat(),
            "timezone": "UTC",
            "color": "#333",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()
    assert len(repos.plans.list()) == 1
    assert repos.plans.soft_delete("plan-1")
    db_session.commit()
    assert repos.plans.get("plan-1") is None
    assert repos.plans.list() == []


def test_plan_task_and_list_item(repos: Repositories, db_session: Session):
    now = _now()
    repos.calendars.put(
        {
            "id": "cal-4",
            "name": "Local",
            "timezone": "UTC",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.plans.put(
        {
            "id": "plan-2",
            "calendarId": "cal-4",
            "title": "Launch",
            "startAt": now,
            "endAt": (datetime.utcnow() + timedelta(hours=3)).replace(microsecond=0).isoformat(),
            "timezone": "UTC",
            "color": "#111",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.plan_tasks.put(
        {
            "id": "pt-1",
            "planId": "plan-2",
            "title": "Write docs",
            "completed": False,
            "order": 1,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.lists.put(
        {
            "id": "list-1",
            "calendarId": "cal-4",
            "title": "Groceries",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    repos.list_items.put(
        {
            "id": "li-1",
            "listId": "list-1",
            "title": "Eggs",
            "completed": False,
            "order": 0,
            "createdAt": now,
            "updatedAt": now,
        }
    )
    db_session.commit()
    assert len(repos.plan_tasks.list_by_plan_id("plan-2")) == 1
    assert repos.list_items.list_by_list_id("list-1")[0]["title"] == "Eggs"
