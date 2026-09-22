# AI Architecture

Text:
User → AI → Structured Action → Validation → Draft → Confirmation → Domain Service → DB.

Voice:
Microphone → backend Whisper → text → same pipeline.

## Provider
Интерфейс `AIProvider`. Реализации могут быть Grok/NVIDIA; frontend не знает провайдера. API key backend-only.

## DB boundary
AI не имеет SQL, repository, DB credentials.

Для update/delete AI создаёт TargetSelector. Backend возвращает только необходимые sanitized candidates:
id, title, date, start/end, recurrence summary.

0 кандидатов → clarification.
1 однозначный → Draft.
Несколько → пользователь выбирает.

## Important
AI не заявляет «создано», пока backend не подтвердил операцию.
