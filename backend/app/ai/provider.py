from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.ai.prompts import SYSTEM_PROMPT, context_messages, heuristic_propose, parse_structured_action
from app.ai.types import StructuredAction
from app.core.errors import AppError


class MockAIProvider:
    name = "mock"

    async def propose(self, *, user_message: str, context: dict[str, Any] | None = None) -> StructuredAction:
        timezone = (context or {}).get("calendarTimezone")
        if not isinstance(timezone, str):
            timezone = None
        action = heuristic_propose(user_message, timezone=timezone)
        if action is None:
            return StructuredAction(intent="CLARIFY", clarification="Уточните запрос.")
        return action


class OpenAICompatibleProvider:
    """Works with NVIDIA Integrate API and Groq OpenAI-compatible endpoints."""

    def __init__(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ) -> None:
        self.name = name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def propose(self, *, user_message: str, context: dict[str, Any] | None = None) -> StructuredAction:
        if not self.api_key:
            raise AppError("ai_provider_error", "AI API key is not configured", status_code=503)

        payload = {
            "model": self.model,
            "messages": context_messages(user_message, context),
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        # Some providers support json_object; retry without it if rejected.
        variants = [
            {**payload, "response_format": {"type": "json_object"}},
            payload,
        ]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            for body_payload in variants:
                try:
                    async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                        response = await client.post(url, headers=headers, json=body_payload)
                    if response.status_code >= 500:
                        raise AppError(
                            "ai_provider_error",
                            "AI provider unavailable",
                            status_code=502,
                            details={"status": response.status_code},
                        )
                    if response.status_code >= 400:
                        # try next payload variant
                        last_error = AppError(
                            "ai_provider_error",
                            "AI provider rejected the request",
                            status_code=502,
                            details={"status": response.status_code},
                        )
                        continue
                    body = response.json()
                    message = body["choices"][0]["message"]
                    content = message.get("content") or message.get("reasoning_content")
                    if not isinstance(content, str) or not content.strip():
                        last_error = AppError(
                            "ai_provider_error",
                            "AI provider returned empty content",
                            status_code=502,
                        )
                        continue
                    return parse_structured_action(content)
                except (httpx.TimeoutException, httpx.TransportError, KeyError, ValueError) as exc:
                    last_error = exc
                    break
            if attempt < self.max_retries:
                await asyncio.sleep(0.4 * (attempt + 1))

        # Never leak provider payloads/secrets into logs via exception chaining message.
        raise AppError(
            "ai_provider_error",
            "AI provider failed after retries",
            status_code=502,
            details={"reason": type(last_error).__name__ if last_error else "unknown"},
        ) from None


def build_provider_from_settings(settings) -> MockAIProvider | OpenAICompatibleProvider:
    provider = (settings.ai_provider or "mock").lower()
    if provider == "mock" or not settings.ai_api_key:
        return MockAIProvider()
    if provider == "groq":
        return OpenAICompatibleProvider(
            name="groq",
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url or "https://api.groq.com/openai/v1",
            model=settings.ai_model or "openai/gpt-oss-20b",
        )
    # default: nvidia / openai-compatible
    return OpenAICompatibleProvider(
        name=provider or "nvidia",
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url or "https://integrate.api.nvidia.com/v1",
        model=settings.ai_model or "meta/llama-3.1-70b-instruct",
    )


__all__ = [
    "MockAIProvider",
    "OpenAICompatibleProvider",
    "build_provider_from_settings",
    "SYSTEM_PROMPT",
]
