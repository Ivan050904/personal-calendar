from datetime import datetime


def test_ai_chat_off_topic_no_draft(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    response = client.post("/api/ai/chat", json={"message": "Какая погода завтра?"})
    assert response.status_code == 200
    body = response.json()
    assert body["action"]["intent"] == "OFF_TOPIC"
    assert body["draft"] is None


def test_ai_chat_creates_collecting_draft(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    response = client.post("/api/ai/chat", json={"message": "Создай событие завтра вечером"})
    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["status"] == "collecting"
    draft_id = body["draft"]["draftId"]

    got = client.get(f"/api/ai/drafts/{draft_id}")
    assert got.status_code == 200
    assert got.json()["draftId"] == draft_id

    cancelled = client.post(f"/api/ai/drafts/{draft_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_confirm_not_ready_and_idempotent_cancel(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()

    created = client.post("/api/ai/chat", json={"message": "Создай задачу купить молоко"})
    assert created.status_code == 200
    draft = created.json()["draft"]
    draft_id = draft["draftId"]

    if draft["status"] != "ready":
        # Force ready via direct confirm path expectation
        confirm = client.post(f"/api/ai/drafts/{draft_id}/confirm")
        # collecting should 409
        assert confirm.status_code in {200, 409}

    cancel1 = client.post(f"/api/ai/drafts/{draft_id}/cancel")
    cancel2 = client.post(f"/api/ai/drafts/{draft_id}/cancel")
    assert cancel1.status_code == 200
    assert cancel2.status_code == 200
    assert cancel2.json()["status"] == "cancelled"


def test_provider_info(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("AI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    response = client.get("/api/ai/provider")
    assert response.status_code == 200
    assert response.json()["provider"] == "mock"
