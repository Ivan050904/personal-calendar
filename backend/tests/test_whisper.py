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
    assert body["installed"] is True
    assert body["model"]


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


def test_transcribe_real_whisper_on_short_wav(client, tmp_path):
    wav_path = tmp_path / "silent.wav"
    _make_silent_wav(wav_path, seconds=1.0)
    audio = wav_path.read_bytes()
    response = client.post(
        "/api/ai/transcribe",
        files={"audio": ("silent.wav", audio, "audio/wav")},
    )
    # Silent audio may yield empty transcription (422) or a short text — both mean model ran.
    assert response.status_code in {200, 422}
    body = response.json()
    if response.status_code == 200:
        assert isinstance(body["text"], str)
        assert body["model"]
        assert "latencyMs" in body
    else:
        assert body["error"]["code"] == "transcription_error"
