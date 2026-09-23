from pathlib import Path

import numpy as np
import soundfile as sf


def _make_silent_wav(path: Path, seconds: float = 1.0, sr: int = 16000) -> None:
    samples = np.zeros(int(sr * seconds), dtype=np.float32)
    sf.write(path, samples, sr)


def test_whisper_status(client):
    response = client.get("/api/ai/whisper/status")
    assert response.status_code == 200
    body = response.json()
    assert "installed" in body
    assert body["model"]
    assert body["backend"] in {"local", "remote"}


def test_transcribe_rejects_empty(client):
    response = client.post(
        "/api/ai/transcribe",
        files={"audio": ("empty.webm", b"", "audio/webm")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "transcription_error"


def test_transcribe_rejects_oversized(client):
    huge = b"x" * (3 * 1024 * 1024 + 10)
    response = client.post(
        "/api/ai/transcribe",
        files={"audio": ("big.webm", huge, "audio/webm")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "transcription_error"


def test_remote_whisper_transcribes(client, monkeypatch):
    from app.whisper import service as whisper_mod

    class FakeResponse:
        status_code = 200
        text = '{"text":"создай событие завтра"}'

        def json(self):
            return {"text": "создай событие завтра", "language": "ru"}

    def fake_post(*_args, **_kwargs):
        return FakeResponse()

    monkeypatch.setenv("WHISPER_BACKEND", "remote")
    monkeypatch.setenv("WHISPER_API_BASE_URL", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("WHISPER_API_KEY", "test-key")
    monkeypatch.setenv("WHISPER_REMOTE_MODEL", "whisper-large-v3-turbo")
    from app.core.config import get_settings

    get_settings.cache_clear()
    whisper_mod.get_whisper_service.cache_clear()
    monkeypatch.setattr(whisper_mod.httpx, "post", fake_post)

    response = client.post(
        "/api/ai/transcribe",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "создай событие завтра"
    assert body["device"] == "remote"
    get_settings.cache_clear()
    whisper_mod.get_whisper_service.cache_clear()


def test_production_forces_remote_backend(monkeypatch):
    from app.whisper import service as whisper_mod
    from app.core.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WHISPER_BACKEND", "local")
    get_settings.cache_clear()
    whisper_mod.get_whisper_service.cache_clear()
    assert whisper_mod.resolve_whisper_backend() == "remote"
    get_settings.cache_clear()
    whisper_mod.get_whisper_service.cache_clear()


def test_transcribe_real_whisper_on_short_wav(client, tmp_path):
    wav_path = tmp_path / "silent.wav"
    _make_silent_wav(wav_path, seconds=1.0)
    audio = wav_path.read_bytes()
    response = client.post(
        "/api/ai/transcribe",
        files={"audio": ("silent.wav", audio, "audio/wav")},
    )
    # Local model may be missing in CI → 503; silent clip → 422; success → 200.
    assert response.status_code in {200, 422, 503}
    body = response.json()
    if response.status_code == 200:
        assert isinstance(body["text"], str)
        assert body["model"]
        assert "latencyMs" in body
    else:
        assert body["error"]["code"] == "transcription_error"
