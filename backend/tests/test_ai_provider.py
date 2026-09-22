import pytest

from app.ai.prompts import heuristic_propose
from app.ai.provider import MockAIProvider, OpenAICompatibleProvider
from app.ai.types import StructuredAction
from app.core.errors import AppError


@pytest.mark.asyncio
async def test_mock_provider_off_topic():
    provider = MockAIProvider()
    action = await provider.propose(user_message="Какая погода завтра?")
    assert action.intent == "OFF_TOPIC"
    assert "календарём" in (action.message or "")


@pytest.mark.asyncio
async def test_mock_provider_asks_entity_type():
    provider = MockAIProvider()
    action = await provider.propose(user_message="Завтра надо купить молоко")
    # Without explicit create verb, clarify
    assert action.intent in {"CLARIFY", "CREATE"}


def test_heuristic_event_evening_needs_time():
    action = heuristic_propose("Создай событие завтра вечером")
    assert action is not None
    assert action.intent == "CLARIFY"
    assert "start" in action.missing_fields


@pytest.mark.asyncio
async def test_openai_compatible_requires_key():
    provider = OpenAICompatibleProvider(
        name="nvidia",
        api_key="",
        base_url="https://example.invalid/v1",
        model="x",
    )
    with pytest.raises(AppError) as raised:
        await provider.propose(user_message="создай задачу купить молоко")
    assert raised.value.code == "ai_provider_error"


def test_structured_action_schema():
    action = StructuredAction(intent="CREATE", entity_type="task", payload={"title": "Milk"})
    dumped = action.model_dump(by_alias=True)
    assert dumped["entityType"] == "task"
    assert dumped["payload"]["title"] == "Milk"
