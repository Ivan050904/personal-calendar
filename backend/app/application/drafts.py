from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.executor import DomainExecutor
from app.application.target_resolver import TargetResolver
from app.core.errors import AppError
from app.infrastructure.db.models import DraftModel
from app.infrastructure.repositories import _iso


DRAFT_TTL_MINUTES = 30
READY_STATUSES = {"collecting", "ready"}


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def compute_missing_fields(operation: str, entity_type: str | None, payload: dict[str, Any]) -> list[str]:
    if operation == "DELETE":
        return []
    missing: list[str] = []
    if not entity_type:
        missing.append("entityType")
        return missing
    if not _has_text(payload.get("title")):
        missing.append("title")
    if entity_type == "event":
        if not (payload.get("start") or payload.get("startAt")):
            missing.append("start")
        if not (payload.get("end") or payload.get("endAt") or payload.get("durationMinutes")):
            missing.append("end")
    elif entity_type == "plan":
        if not (payload.get("start") or payload.get("startAt")):
            missing.append("start")
        if not (payload.get("end") or payload.get("endAt")):
            missing.append("end")
    return missing


class DraftService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_from_action(
        self,
        *,
        action: dict[str, Any],
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        intent = action.get("intent")
        if intent == "OFF_TOPIC":
            raise AppError("validation_error", "Off-topic requests cannot become drafts", status_code=422)
        if intent == "CLARIFY":
            entity_type = action.get("entityType") or action.get("entity_type")
            payload = action.get("payload") or {}
            missing = compute_missing_fields("CREATE", entity_type, payload) or ["entityType"]
            status = "collecting"
        elif intent in {"CREATE", "UPDATE", "DELETE"}:
            entity_type = action.get("entityType") or action.get("entity_type")
            payload = action.get("payload") or {}
            missing = compute_missing_fields(str(intent), entity_type, payload)
            status = "collecting" if missing else "ready"
        else:
            raise AppError("validation_error", "Unsupported intent for draft", status_code=422)

        now = datetime.utcnow()
        draft = DraftModel(
            id=str(uuid4()),
            conversation_id=conversation_id or str(uuid4()),
            operation=str(intent),
            entity_type=action.get("entityType") or action.get("entity_type"),
            payload=action.get("payload") or {},
            target=action.get("targetSelector") or action.get("target_selector"),
            missing_fields=missing,
            status=status,
            clarification=action.get("clarification"),
            message=action.get("message"),
            recurrence_scope=action.get("recurrenceScope") or action.get("recurrence_scope"),
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(minutes=DRAFT_TTL_MINUTES),
        )
        self.session.add(draft)
        self.session.commit()
        self.session.refresh(draft)
        return self.to_dict(draft)

    def update_fields(
        self,
        draft_id: str,
        *,
        payload: dict[str, Any] | None = None,
        entity_type: str | None = None,
        recurrence_scope: str | None = None,
    ) -> dict[str, Any]:
        draft = self._require(draft_id)
        self._ensure_active(draft)
        if draft.status in {"confirmed", "cancelled"}:
            raise AppError("validation_error", "Draft can no longer be edited", status_code=409)

        if entity_type is not None:
            draft.entity_type = entity_type
        if payload is not None:
            merged = dict(draft.payload or {})
            for key, value in payload.items():
                if value is None and key == "recurrence":
                    merged.pop("recurrence", None)
                elif value is not None:
                    merged[key] = value
            # Allow clearing optional fields with empty string → None for dueDate
            for key, value in list(merged.items()):
                if isinstance(value, str) and value.strip() == "" and key in {"dueDate", "description", "end", "endAt"}:
                    merged[key] = None
            draft.payload = merged
        if recurrence_scope is not None:
            draft.recurrence_scope = recurrence_scope or None

        # CLARIFY drafts become CREATE once required fields are filled (confirm cannot execute CLARIFY).
        effective_operation = "CREATE" if draft.operation == "CLARIFY" else draft.operation
        missing = compute_missing_fields(effective_operation, draft.entity_type, draft.payload or {})
        draft.missing_fields = missing
        draft.status = "collecting" if missing else "ready"
        if not missing:
            draft.clarification = None
            if draft.operation == "CLARIFY":
                draft.operation = "CREATE"
        draft.updated_at = datetime.utcnow()
        self.session.commit()
        return self.to_dict(draft)

    def get(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        return self.to_dict(draft)

    def cancel(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        if draft.status in {"confirmed", "cancelled"}:
            return self.to_dict(draft)
        draft.status = "cancelled"
        draft.updated_at = datetime.utcnow()
        self.session.commit()
        return self.to_dict(draft)

    def confirm(self, draft_id: str) -> dict[str, Any]:
        draft = self._require(draft_id)
        self._ensure_active(draft)
        if draft.status == "confirmed":
            payload = self.to_dict(draft)
            result = dict(payload.get("result") or {})
            result["idempotent"] = True
            payload["result"] = result
            return payload  # idempotent
        if draft.status != "ready":
            raise AppError(
                "validation_error",
                "Draft is not ready for confirmation",
                status_code=409,
                details={"status": draft.status, "missingFields": draft.missing_fields},
            )
        if draft.operation == "CLARIFY":
            # Safety net: ready clarify drafts are create proposals.
            draft.operation = "CREATE"
        executor = DomainExecutor(self.session)
        draft_dict = self.to_dict(draft)
        if draft.operation in {"UPDATE", "DELETE"} and not (draft_dict.get("target") or {}).get("id"):
            resolver = TargetResolver(self.session)
            resolved = resolver.resolve(draft_dict.get("target"))
            draft.target = resolved
            draft_dict["target"] = resolved
            self.session.flush()
        result = executor.execute(draft_dict)
        draft.status = "confirmed"
        draft.updated_at = datetime.utcnow()
        draft.result = {"accepted": True, "executed": True, **result}
        self.session.commit()
        return self.to_dict(draft)

    def expire_stale(self) -> int:
        now = datetime.utcnow()
        rows = self.session.scalars(
            select(DraftModel)
            .where(DraftModel.status.in_(tuple(READY_STATUSES)))
            .where(DraftModel.expires_at < now)
        ).all()
        for row in rows:
            row.status = "expired"
            row.updated_at = now
        if rows:
            self.session.commit()
        return len(rows)

    def _require(self, draft_id: str) -> DraftModel:
        draft = self.session.get(DraftModel, draft_id)
        if draft is None:
            raise AppError("not_found", "Draft not found", status_code=404)
        if draft.status in READY_STATUSES and draft.expires_at and draft.expires_at < datetime.utcnow():
            draft.status = "expired"
            draft.updated_at = datetime.utcnow()
            self.session.commit()
        return draft

    def _ensure_active(self, draft: DraftModel) -> None:
        if draft.status == "expired":
            raise AppError("draft_expired", "Draft expired", status_code=409)
        if draft.status == "cancelled":
            raise AppError("validation_error", "Draft was cancelled", status_code=409)

    def to_dict(self, draft: DraftModel) -> dict[str, Any]:
        return {
            "draftId": draft.id,
            "conversationId": draft.conversation_id,
            "operation": draft.operation,
            "entityType": draft.entity_type,
            "payload": draft.payload or {},
            "target": draft.target,
            "missingFields": draft.missing_fields or [],
            "status": draft.status,
            "clarification": draft.clarification,
            "message": draft.message,
            "recurrenceScope": draft.recurrence_scope,
            "result": draft.result,
            "createdAt": _iso(draft.created_at),
            "updatedAt": _iso(draft.updated_at),
            "expiresAt": _iso(draft.expires_at),
        }
