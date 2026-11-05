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

## Calendars (D36, wave 2)
GET /api/v2/calendars — свои календари без удалённых: «Личное» первым, затем свои (`user`), затем календари приложений (`app`); внутри — по `sort_order`. Поля: `id, name, kind, color, visible, sort_order, timezone, source_client_id, revision, created_at, updated_at`.
POST /api/v2/calendars — `{name, color?, timezone?}` → 201, `kind=user`; цвет `#RRGGBB` (по умолчанию `#2563eb`), часовой пояс по умолчанию как у «Личного». Неизвестные поля (например `kind`) → 422.
PATCH /api/v2/calendars/{id} — `{name?, color?, visible?, sort_order?}`; `revision` +1. Чужой календарь → 404.
DELETE /api/v2/calendars/{id} — мягкое удаление; записи остаются в БД, но читать и писать их больше нельзя (404). «Личное» → 409.
POST /api/commands — новое необязательное поле `calendar_id`, только для `operation=create` (иначе 422): запись создаётся в этом календаре владельца; без поля — в «Личном», как раньше. Чужой или удалённый → 404.
GET /api/occurrences?calendar_id= принимает любой свой календарь (без изменений контракта). Интерфейс запрашивает каждый видимый календарь и накладывает их.

## OAuth for apps (D35, wave 3)
Все пути под `/api` (nginx отдаёт бэкенду только `/api`). Метаданные: `GET /api/.well-known/oauth-authorization-server` (issuer = `<host>/api`).
Клиентов создаёт владелец: `python backend/scripts/oauth_clients.py create --name <имя> --redirect-uri <uri> [--redirect-uri …] [--scope …] [--public]`, а также `list` и `disable <client_id>`. `redirect_uri` — https (http только для localhost), без `#`. `client_secret` печатается один раз.
Scopes: `openid`, `profile` (логин и имя), `calendars.read`, `events.read`, `events.write`.
GET /api/oauth/authorize — `response_type=code, client_id, redirect_uri, scope, state, code_challenge, code_challenge_method=S256`. Неизвестный клиент или чужой `redirect_uri` → страница ошибки без редиректа. Остальные ошибки → `redirect_uri?error=…&state=…` (`invalid_request`, `invalid_scope`, `access_denied`). Без сессии показывается форма входа (POST /api/oauth/login, тот же лимит попыток, что у входа). С сессией — экран согласия; если в запросе есть чтение, пользователь отмечает, какие календари видит приложение. Если разрешение с этими scope уже есть, код выдаётся без экрана.
POST /api/oauth/authorize — форма согласия (CSRF) → 303 на `redirect_uri?code=…&state=…`. Код одноразовый, 60 с. При `events.write` создаётся календарь приложения (`kind=app`, имя клиента). Если после отзыва он не удалён, используется прежний.
POST /api/oauth/token — `application/x-www-form-urlencoded`. Клиент: Basic или `client_id`/`client_secret` в форме (публичный — только `client_id`).
`grant_type=authorization_code` (`code, redirect_uri, code_verifier`) или `refresh_token` (`refresh_token`) → `{access_token: "pca_…", token_type: "Bearer", expires_in: 900, refresh_token: "pcr_…", scope}`.
Refresh-токен живёт 30 дней и меняется при каждом обновлении. Повтор кода или старого refresh отзывает всё разрешение.
Ошибки: `{error, error_description}` — `invalid_client` 401, `invalid_grant` / `unsupported_grant_type` 400, `slow_down` 429.
POST /api/oauth/revoke — `token` + аутентификация клиента → 200 `{}` (RFC 7009: неизвестный токен тоже 200). Отзывает всё разрешение.
GET /api/oauth/userinfo — нужен `openid` → `{sub}`; с `profile` ещё `preferred_username`, `name`.
Bearer-токен приложения открывает только `GET /api/v2/calendars`, `/api/v2/events*` и `/api/oauth/userinfo`. Всё остальное → 403 «Not available to connected apps». Просроченный или отозванный токен → 401.
GET /api/v2/grants — только сессия → `[{id, client_id, client_name, scopes, readable_calendar_ids, app_calendar_id, created_at, last_used_at}]`. DELETE /api/v2/grants/{id} → `{id, revoked: true}`, токены гаснут сразу. Чужое разрешение → 404.

## Events v2 (wave 3)
Для интерфейса (cookie) и приложений (Bearer). Приложению нужны: `calendars.read` для списка календарей (видит только отмеченные ему), `events.read` для чтения (только отмеченные календари, иначе 404), `events.write` для записи.
GET /api/v2/events?calendar_id=&from=YYYY-MM-DD&to=YYYY-MM-DD[&timezone=&cursor=&limit≤500] → `{calendar_id, items, complete, next_cursor}`. Повторы развёрнуты, как в occurrences.
GET /api/v2/events/{id} — запись события (как в `/api/entities`).
POST /api/v2/events[?calendar_id=] — тело = payload события, необязательный `Idempotency-Key: <uuid>` → 201, результат команды. Приложение пишет только в свой календарь: другой `calendar_id` → 403, удалённый календарь приложения → 403 до повторного согласия.
PATCH /api/v2/events/{id}[?occurrence_key=&scope=this|thisAndFollowing|series] — нужен `If-Match: <revision>` (без него 428, устаревший → 409 `conflict`); `Idempotency-Key` необязателен. DELETE — те же параметры → `{id, deleted: true}`. Приложение меняет только события своего календаря (иначе 403).
Пока нет (позже): `external_id`, `tasks`/`plans` v2, `freebusy`, `changes`, webhooks, участники.

## Stable errors
validation_error, clarification_required, not_found, ambiguous_target, draft_expired, draft_already_completed, ai_provider_error, transcription_error, database_error, unauthorized, forbidden, conflict, unavailable, rate_limited.

Не отдавать stack trace/secrets.
