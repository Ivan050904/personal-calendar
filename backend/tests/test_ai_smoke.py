"""Optional real-provider smoke. Skips unless AI key is configured in backend/.env."""

from pathlib import Path

import pytest
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import AppError


class SmokeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    ai_api_key: str = ""
    ai_base_url: str = ""
    ai_model: str = ""
    ai_provider: str = "mock"


@pytest.mark.asyncio
async def test_real_provider_smoke_when_configured():
    settings = SmokeSettings()
    if not settings.ai_api_key or (settings.ai_provider or "mock").lower() == "mock":
        pytest.skip("Real AI key/provider not configured for smoke")

    from app.ai.provider import OpenAICompatibleProvider

    provider = OpenAICompatibleProvider(
        name=settings.ai_provider,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url or "https://api.groq.com/openai/v1",
        model=settings.ai_model or "openai/gpt-oss-20b",
    )
    try:
        action = await provider.propose(user_message="Create a task buy milk")
    except AppError as exc:
        pytest.skip(f"Real provider unavailable: {exc.code}")

    assert action.intent in {"CREATE", "CLARIFY", "OFF_TOPIC"}
    assert "intent" in action.model_dump(by_alias=True)
