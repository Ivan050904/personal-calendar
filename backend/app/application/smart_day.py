from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(part.title() for part in parts[1:])


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class TimedBlock(CamelModel):
    kind: Literal["event", "plan"]
    id: str
    title: str
    start_at: str
    end_at: str
    color: str


class SmartDaySnapshot(CamelModel):
    now: str
    status: Literal["busy", "free"]
    label: str
    current: TimedBlock | None
    next: TimedBlock | None
    elapsed_ms: int | None
    remaining_ms: int | None
    overlaps: list[TimedBlock]


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def build_smart_day_snapshot(
    events: list[dict[str, Any]],
    plans: list[dict[str, Any]],
    now_iso: str,
) -> SmartDaySnapshot:
    now = _parse(now_iso)
    blocks: list[TimedBlock] = []

    for event in events:
        if event.get("deletedAt") or event.get("allDay"):
            continue
        blocks.append(
            TimedBlock(
                kind="event",
                id=event["id"],
                title=event["title"],
                start_at=event["startAt"],
                end_at=event["endAt"],
                color=event["color"],
            )
        )

    for plan in plans:
        if plan.get("deletedAt"):
            continue
        blocks.append(
            TimedBlock(
                kind="plan",
                id=plan["id"],
                title=plan["title"],
                start_at=plan["startAt"],
                end_at=plan["endAt"],
                color=plan["color"],
            )
        )

    blocks.sort(key=lambda item: (item.start_at, item.end_at))
    overlaps = [
        block
        for block in blocks
        if _parse(block.start_at) <= now < _parse(block.end_at)
    ]
    current = overlaps[0] if overlaps else None
    future = [block for block in blocks if _parse(block.start_at) > now]
    next_block = sorted(future, key=lambda item: item.start_at)[0] if future else None

    if current is None:
        return SmartDaySnapshot(
            now=now_iso,
            status="free",
            label="Сейчас свободно",
            current=None,
            next=next_block,
            elapsed_ms=None,
            remaining_ms=None,
            overlaps=[],
        )

    start = _parse(current.start_at)
    end = _parse(current.end_at)
    elapsed = max(0, int((now - start).total_seconds() * 1000))
    remaining = max(0, int((end - now).total_seconds() * 1000))
    return SmartDaySnapshot(
        now=now_iso,
        status="busy",
        label=current.title,
        current=current,
        next=next_block,
        elapsed_ms=elapsed,
        remaining_ms=remaining,
        overlaps=overlaps,
    )


def plan_progress(tasks: list[dict[str, Any]]) -> dict[str, int]:
    active = [task for task in tasks if not task.get("deletedAt")]
    completed = sum(1 for task in active if task.get("completed"))
    total = len(active)
    percentage = 0 if total == 0 else round((completed / total) * 100)
    return {"completed": completed, "total": total, "percentage": percentage}
