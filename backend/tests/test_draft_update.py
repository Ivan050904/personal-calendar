from sqlalchemy.orm import Session

from app.application.drafts import DraftService, compute_missing_fields


def test_compute_missing_for_task():
    assert compute_missing_fields("CREATE", "task", {"title": "Toilet"}) == []
    assert "title" in compute_missing_fields("CREATE", "task", {})


def test_patch_draft_makes_ready(db_session: Session):
    drafts = DraftService(db_session)
    draft = drafts.create_from_action(
        action={
            "intent": "CREATE",
            "entityType": "task",
            "payload": {"title": ""},
            "missingFields": ["title"],
        }
    )
    assert draft["status"] == "collecting"
    updated = drafts.update_fields(
        draft["draftId"],
        payload={"title": "Сходить в туалет"},
        entity_type="task",
    )
    assert updated["status"] == "ready"
    assert updated["payload"]["title"] == "Сходить в туалет"
    assert updated["missingFields"] == []


def test_clarify_draft_promotes_to_create_when_ready(db_session: Session):
    drafts = DraftService(db_session)
    draft = drafts.create_from_action(
        action={
            "intent": "CLARIFY",
            "entityType": "event",
            "payload": {"title": "Встреча"},
            "clarification": "Нужно время",
        }
    )
    assert draft["operation"] == "CLARIFY"
    assert draft["status"] == "collecting"

    updated = drafts.update_fields(
        draft["draftId"],
        payload={
            "title": "Встреча",
            "start": "2026-09-18T16:00:00",
            "end": "2026-09-18T17:00:00",
        },
        entity_type="event",
    )
    assert updated["status"] == "ready"
    assert updated["operation"] == "CREATE"
    assert updated["missingFields"] == []

    confirmed = drafts.confirm(updated["draftId"])
    assert confirmed["status"] == "confirmed"
    assert confirmed["result"]["entityType"] == "event"
    assert confirmed["result"]["entity"]["title"] == "Встреча"
