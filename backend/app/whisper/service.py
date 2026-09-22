from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from app.core.config import get_settings
from app.core.errors import AppError

MAX_AUDIO_BYTES = 3 * 1024 * 1024
MAX_DURATION_SECONDS = 20.0


@dataclass
class TranscriptionResult:
    text: str
    language: str | None
    model: str
    device: str
    duration_seconds: float | None
    latency_ms: int


class WhisperService(Protocol):
    def transcribe(self, audio_bytes: bytes, *, filename: str | None = None) -> TranscriptionResult: ...


class LocalWhisperService:
    """Local openai-whisper transcription (GitHub: openai/whisper)."""

    def __init__(self, model_name: str, device: str | None = None) -> None:
        import torch
        import whisper

        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._model = whisper.load_model(model_name, device=self.device)

    def transcribe(self, audio_bytes: bytes, *, filename: str | None = None) -> TranscriptionResult:
        if not audio_bytes:
            raise AppError("transcription_error", "Empty audio", status_code=422)
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise AppError("transcription_error", "Audio too large", status_code=413)

        suffix = Path(filename or "audio.webm").suffix or ".webm"
        started = time.perf_counter()
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            # Keep audio off disk after transcription; file is deleted in finally.
            result = self._model.transcribe(
                tmp_path,
                language="ru",
                fp16=self.device.startswith("cuda"),
                task="transcribe",
            )
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "transcription_error",
                "Whisper failed to transcribe audio",
                status_code=500,
                details={"reason": type(exc).__name__},
            ) from None
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        text = str(result.get("text") or "").strip()
        if not text:
            raise AppError("transcription_error", "Empty transcription", status_code=422)

        duration = result.get("duration")
        if duration is not None and float(duration) > MAX_DURATION_SECONDS + 0.5:
            raise AppError(
                "transcription_error",
                f"Audio longer than {int(MAX_DURATION_SECONDS)} seconds",
                status_code=413,
                details={"durationSeconds": float(duration)},
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        return TranscriptionResult(
            text=text,
            language=result.get("language"),
            model=self.model_name,
            device=self.device,
            duration_seconds=float(duration) if duration is not None else None,
            latency_ms=latency_ms,
        )


@lru_cache
def get_whisper_service() -> LocalWhisperService:
    settings = get_settings()
    model_name = (settings.whisper_model or "small").strip() or "small"
    return LocalWhisperService(model_name)


def whisper_status() -> dict[str, Any]:
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        device_name = torch.cuda.get_device_name(0) if cuda else "cpu"
    except Exception:  # noqa: BLE001
        cuda = False
        device_name = "unavailable"

    settings = get_settings()
    return {
        "installed": True,
        "model": settings.whisper_model or "small",
        "cuda": cuda,
        "device": device_name,
        "maxDurationSeconds": MAX_DURATION_SECONDS,
        "maxBytes": MAX_AUDIO_BYTES,
    }
