from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import httpx

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


class RemoteWhisperService:
    """OpenAI-compatible audio transcription (Groq / NVIDIA proxy / self-hosted)."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_bytes: bytes, *, filename: str | None = None) -> TranscriptionResult:
        if not audio_bytes:
            raise AppError("transcription_error", "Empty audio", status_code=422)
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise AppError("transcription_error", "Audio too large", status_code=413)
        if not self.api_key:
            raise AppError("transcription_error", "Whisper API key is not configured", status_code=503)

        name = filename or "audio.webm"
        started = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                files={"file": (name, audio_bytes, _content_type(name))},
                data={"model": self.model, "language": "ru", "response_format": "json"},
                timeout=60.0,
            )
        except httpx.HTTPError as exc:
            raise AppError(
                "transcription_error",
                "Whisper remote request failed",
                status_code=503,
                details={"reason": type(exc).__name__},
            ) from None

        if response.status_code >= 400:
            raise AppError(
                "transcription_error",
                "Whisper remote provider error",
                status_code=502,
                details={"status": response.status_code, "body": response.text[:300]},
            )

        payload = response.json()
        text = str(payload.get("text") or "").strip()
        if not text:
            raise AppError("transcription_error", "Empty transcription", status_code=422)

        latency_ms = int((time.perf_counter() - started) * 1000)
        return TranscriptionResult(
            text=text,
            language=payload.get("language") or "ru",
            model=self.model,
            device="remote",
            duration_seconds=None,
            latency_ms=latency_ms,
        )


def _content_type(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".wav":
        return "audio/wav"
    if suffix in {".mp3", ".mpeg"}:
        return "audio/mpeg"
    if suffix == ".ogg":
        return "audio/ogg"
    if suffix == ".m4a":
        return "audio/mp4"
    return "audio/webm"


def _local_whisper_importable() -> bool:
    try:
        import whisper  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def resolve_whisper_backend(settings: Any | None = None) -> str:
    cfg = settings or get_settings()
    app_env = (getattr(cfg, "app_env", "") or "").strip().lower()
    # Beget / production: never load local torch/openai-whisper.
    if app_env == "production":
        return "remote"
    raw = (getattr(cfg, "whisper_backend", None) or "auto").strip().lower()
    if raw in {"remote", "http", "openai", "groq"}:
        return "remote"
    if raw == "local":
        return "local"
    # auto (dev): local if package present, else remote.
    if _local_whisper_importable():
        return "local"
    return "remote"


def _remote_credentials(settings: Any) -> tuple[str, str, str]:
    base = (settings.whisper_api_base_url or settings.groq_base_url or "").strip()
    key = (settings.whisper_api_key or settings.groq_api_key or settings.ai_api_key or "").strip()
    model = (settings.whisper_remote_model or "whisper-large-v3-turbo").strip()
    return base, key, model


@lru_cache
def get_whisper_service() -> LocalWhisperService | RemoteWhisperService:
    settings = get_settings()
    backend = resolve_whisper_backend(settings)
    if backend == "remote":
        base, key, model = _remote_credentials(settings)
        if not base or not key:
            raise AppError(
                "transcription_error",
                "Whisper remote backend is not configured",
                status_code=503,
            )
        return RemoteWhisperService(base_url=base, api_key=key, model=model)

    model_name = (settings.whisper_model or "small").strip() or "small"
    return LocalWhisperService(model_name)


def whisper_status() -> dict[str, Any]:
    settings = get_settings()
    backend = resolve_whisper_backend(settings)
    local_ok = _local_whisper_importable()
    base, key, remote_model = _remote_credentials(settings)
    remote_ok = bool(base and key)

    cuda = False
    device_name = "cpu"
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        device_name = torch.cuda.get_device_name(0) if cuda else "cpu"
    except Exception:  # noqa: BLE001
        device_name = "unavailable" if backend == "local" else "remote"

    return {
        "installed": (backend == "local" and local_ok) or (backend == "remote" and remote_ok),
        "backend": backend,
        "model": settings.whisper_model or "small" if backend == "local" else remote_model,
        "cuda": cuda if backend == "local" else False,
        "device": device_name if backend == "local" else "remote",
        "localAvailable": local_ok,
        "remoteConfigured": remote_ok,
        "maxDurationSeconds": MAX_DURATION_SECONDS,
        "maxBytes": MAX_AUDIO_BYTES,
    }
