from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.repositories import Repositories


class TargetResolver:
    def __init__(self, session: Session) -> None:
        self.repos = Repositories(session)

    def resolve(self, selector: dict[str, Any] | None) -> dict[str, Any]:
        if not selector:
            raise AppError("validation_error", "targetSelector is required", status_code=422)
        entity_type = selector.get("entityType") or selector.get("entity_type")
        query = (selector.get("query") or "").strip().lower()
        if not entity_type or not query:
            raise AppError("clarification_required", "Need entity type and query", status_code=422)

        candidates = self._candidates(entity_type, query, selector)
        if len(candidates) == 0:
            raise AppError("not_found", "No matching targets", status_code=404)
        if len(candidates) > 1:
            raise AppError(
                "ambiguous_target",
                "Multiple targets matched",
                status_code=409,
                details={"candidates": candidates},
            )
        return candidates[0]

    def _candidates(self, entity_type: str, query: str, selector: dict[str, Any]) -> list[dict[str, Any]]:
        date_hint = selector.get("date")
        items: list[dict[str, Any]]
        if entity_type == "event":
            items = self.repos.events.list()
        elif entity_type == "plan":
            items = self.repos.plans.list()
        elif entity_type == "task":
            items = self.repos.tasks.list()
        elif entity_type == "list":
            items = self.repos.lists.list()
        else:
            raise AppError("validation_error", f"Unsupported entityType: {entity_type}", status_code=422)

        # Strip command/noise words so "удали задачу Buy milk" still matches title "Buy milk".
        noise = {
            "удали", "отмени", "убери", "измени", "перенеси", "обнови",
            "создай", "добавь", "запиши", "событие", "встречу", "митинг",
            "план", "задачу", "задача", "список", "пожалуйста",
        }
        tokens = [token for token in re.split(r"\W+", query.lower()) if token and token not in noise]
        narrowed = " ".join(tokens) if tokens else query

        scored: list[tuple[int, dict[str, Any]]] = []
        for item in items:
            title = str(item.get("title") or item.get("name") or "").lower()
            if date_hint:
                start = str(item.get("startAt") or item.get("dueDate") or "")
                if date_hint not in start:
                    continue
            title_tokens = [token for token in re.split(r"\W+", title) if token]
            if title_tokens and tokens and all(token in tokens for token in title_tokens):
                score = 100 + len(title_tokens)
            else:
                score = sum(1 for token in tokens if token and token in title)
                if narrowed and narrowed == title:
                    score = max(score, 50)
            if score <= 0:
                continue
            scored.append((score, self._sanitize(entity_type, item)))

        if not scored:
            return []
        best = max(score for score, _ in scored)
        return [item for score, item in scored if score == best]

    def _sanitize(self, entity_type: str, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "entityType": entity_type,
            "title": item.get("title") or item.get("name"),
            "date": (item.get("startAt") or item.get("dueDate") or "")[:10] or None,
            "startAt": item.get("startAt"),
            "endAt": item.get("endAt"),
            "recurrenceRuleId": item.get("recurrenceRuleId"),
        }
