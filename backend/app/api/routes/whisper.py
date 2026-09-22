from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, UploadFile

from app.core.errors import AppError
from app.whisper.service import (
    MAX_AUDIO_BYTES,
    MAX_DURATION_SECONDS,
    get_whisper_service,
    whisper_status,
)

router = APIRouter(prefix="/ai", tags=["whisper"])


@router.get("/whisper/status")
def status() -> dict[str, Any]:
    return whisper_status()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict[str, Any]:
    data = await audio.read()
    if not data:
        raise AppError("transcription_error", "Empty audio", status_code=422)
    if len(data) > MAX_AUDIO_BYTES:
        raise AppError("transcription_error", "Audio too large", status_code=413)

    try:
        service = get_whisper_service()
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            "transcription_error",
            "Whisper model failed to load",
            status_code=503,
            details={"reason": type(exc).__name__},
        ) from None

    result = service.transcribe(data, filename=audio.filename)
    return {
        "text": result.text,
        "language": result.language,
        "model": result.model,
        "device": result.device,
        "durationSeconds": result.duration_seconds,
        "latencyMs": result.latency_ms,
        "maxDurationSeconds": MAX_DURATION_SECONDS,
    }
