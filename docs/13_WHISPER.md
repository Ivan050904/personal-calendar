# Whisper

Requirements:
- Russian.
- max ~20 seconds.
- local transcription.
- same chat.
- audio not persisted by default.

Flow:
MediaRecorder → backend → WhisperService → text → AI.

WhisperService is an abstraction so model can change.

Do not permanently choose a model before benchmarking actual hardware. Benchmark suitable candidates such as small/medium and larger only if hardware allows.

Measure 5/10/20 sec latency, RAM/VRAM, quality on Russian calendar vocabulary, startup time.

Enforce duration/size on client and server.

On failure show error and allow retry.
