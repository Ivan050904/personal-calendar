# API Contract

Точные URL можно адаптировать к фактическому проекту, но возможности обязательны.

## Calendar
API для Event, Plan, PlanTask, Task, List, ListItem, Category, Reminder и Trash/restore по существующим правилам.

## Smart Day
Сервис/endpoint должен дать frontend достаточно данных для current/elapsed/remaining/next.

## AI
### Transcription
POST /api/ai/transcribe (или эквивалент).
Audio → Russian text. Server enforces max duration/size.

### Chat
POST /api/ai/chat (или эквивалент).
Input: message + optional active Draft context.
Output: structured intent/action/extracted fields/missing fields/clarification/TargetSelector.

### Draft
Draft имеет draftId, operation, entityType, payload, status, timestamps, expiry, target when applicable.

### Confirm
POST /api/ai/drafts/{draftId}/confirm.
Server revalidates and executes exactly once.

### Cancel
POST /api/ai/drafts/{draftId}/cancel.

## Auth (D17)
POST /api/auth/login — username/password → httpOnly session cookie.
POST /api/auth/logout — clear cookie.
GET /api/auth/me — session status (public).
All other /api routes require a valid session when AUTH_* env is set. GET /api/health stays public.

## Stable errors
validation_error, clarification_required, not_found, ambiguous_target, draft_expired, draft_already_completed, ai_provider_error, transcription_error, database_error.

Не отдавать stack trace/secrets.
