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

## Accounts (D34, wave 1)
POST /api/auth/login — тот же контракт `{username, password}`: сначала ищется аккаунт календаря по логину (без учёта регистра); если такого логина нет — прежний вход из env (D31, если включён). 5 неудачных попыток на логин или 20 на IP за 15 минут → 429 `rate_limited`.
GET /api/auth/me — `username` = логин аккаунта, если он есть.
POST /api/v2/accounts — `{login, password, display_name?, timezone?}` → 201 `{id, login, display_name}` + session cookie; создаёт календарь «Личное». Пока `REGISTRATION_ENABLED=false` → 503 `unavailable`. Логин занят → 409 `conflict`; логин не `[a-z0-9_.-]{3,32}` или пароль не 8–256 → 422.
GET /api/v2/me — `{id, login, display_name}`.
POST /api/v2/me/password — `{current_password, new_password}`; только сессия (не токен приложения → 403); неверный текущий → 401; отзывает все сессии, кроме текущей.
POST /api/v2/me/sessions/revoke-others — только сессия → `{revoked: N}`.
Владелец: `python backend/scripts/accounts.py create <login> [--name] [--timezone]` и `reset-password <login>` печатают одноразовый временный пароль; сброс отзывает все сессии.

## Stable errors
validation_error, clarification_required, not_found, ambiguous_target, draft_expired, draft_already_completed, ai_provider_error, transcription_error, database_error, unauthorized, forbidden, conflict, unavailable, rate_limited.

Не отдавать stack trace/secrets.
