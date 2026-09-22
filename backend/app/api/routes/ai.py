from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.provider import MockAIProvider, build_provider_from_settings
from app.ai.prompts import OFF_TOPIC_MESSAGE, enrich_action_from_message
from app.application.drafts import DraftService
from app.core.config import get_settings
from app.core.errors import AppError
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories import Repositories

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    draft_id: str | None = None
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    provider: str
    action: dict[str, Any]
    draft: dict[str, Any] | None = None


def get_draft_service(db: Session = Depends(get_db)) -> DraftService:
    return DraftService(db)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    drafts: DraftService = Depends(get_draft_service),
    db: Session = Depends(get_db),
) -> ChatResponse:
    settings = get_settings()
    provider = build_provider_from_settings(settings)
    context: dict[str, Any] | None = None
    if body.draft_id:
        context = drafts.get(body.draft_id)

    local_calendar = Repositories(db).calendars.get_local_calendar()
    calendar_tz = (local_calendar or {}).get("timezone")
    propose_context = dict(context or {})
    if calendar_tz:
        propose_context["calendarTimezone"] = calendar_tz

    try:
        action = await provider.propose(user_message=body.message, context=propose_context or None)
    except AppError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "ai_provider_error",
            "AI proposal failed",
            status_code=502,
            details={"reason": type(exc).__name__},
        ) from None

    action = enrich_action_from_message(action, body.message, timezone=calendar_tz)
    action_dict = action.model_dump(by_alias=True)
    draft_payload = None
    if action.intent != "OFF_TOPIC":
        draft_payload = drafts.create_from_action(
            action=action_dict,
            conversation_id=body.conversation_id or (context or {}).get("conversationId"),
        )
    elif not action.message:
        action_dict["message"] = OFF_TOPIC_MESSAGE

    return ChatResponse(provider=provider.name, action=action_dict, draft=draft_payload)


class DraftUpdateRequest(BaseModel):
    payload: dict[str, Any] | None = None
    entity_type: str | None = Field(default=None, alias="entityType")
    recurrence_scope: str | None = Field(default=None, alias="recurrenceScope")

    model_config = {"populate_by_name": True}


@router.patch("/drafts/{draft_id}")
def update_draft(
    draft_id: str,
    body: DraftUpdateRequest,
    drafts: DraftService = Depends(get_draft_service),
) -> dict[str, Any]:
    return drafts.update_fields(
        draft_id,
        payload=body.payload,
        entity_type=body.entity_type,
        recurrence_scope=body.recurrence_scope,
    )


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, drafts: DraftService = Depends(get_draft_service)) -> dict[str, Any]:
    return drafts.get(draft_id)


@router.post("/drafts/{draft_id}/confirm")
def confirm_draft(draft_id: str, drafts: DraftService = Depends(get_draft_service)) -> dict[str, Any]:
    return drafts.confirm(draft_id)


@router.post("/drafts/{draft_id}/cancel")
def cancel_draft(draft_id: str, drafts: DraftService = Depends(get_draft_service)) -> dict[str, Any]:
    return drafts.cancel(draft_id)


@router.get("/provider")
def provider_info() -> dict[str, Any]:
    settings = get_settings()
    provider = build_provider_from_settings(settings)
    return {
        "provider": provider.name,
        "configured": bool(settings.ai_api_key) and not isinstance(provider, MockAIProvider),
        "model": settings.ai_model or None,
    }
