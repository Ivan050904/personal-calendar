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
POST /api/v2/me/credentials (wave 5, §8.2/§8.5) — `{login, password}`, только сессия → `{id, login, display_name}`. Для аккаунта без логина: созданного через Folio или старого входа из env. Аккаунт и данные те же, дальше вход обычный. Логин уже задан или занят → 409; формат логина или пароля → 422. В настройках интерфейса для таких аккаунтов есть блок «Логин и пароль».
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
Bearer-токен приложения открывает только `GET /api/v2/calendars`, `/api/v2/events*`, `/api/v2/tasks*`, `/api/v2/plans*`, GET `/api/v2/agenda`, `/api/v2/occurrences/*`, `/api/v2/confirmations/*`, `/api/v2/history`, `/api/v2/reminder-source`, `/api/v2/changes`, `/api/v2/webhooks*` и `/api/oauth/userinfo`. `/integration/v1` и всё остальное для приложения закрыто. Всё остальное → 403 «Not available to connected apps». Просроченный или отозванный токен → 401.
GET /api/v2/grants — только сессия → `[{id, client_id, client_name, scopes, readable_calendar_ids, app_calendar_id, created_at, last_used_at}]`. DELETE /api/v2/grants/{id} → `{id, revoked: true}`, токены гаснут сразу. Чужое разрешение → 404.

## Events v2 (wave 3)
Для интерфейса (cookie) и приложений (Bearer). Приложению нужны: `calendars.read` для списка календарей (видит только отмеченные ему), `events.read` для чтения (только отмеченные календари, иначе 404), `events.write` для записи.
GET /api/v2/events?calendar_id=&from=YYYY-MM-DD&to=YYYY-MM-DD[&timezone=&cursor=&limit≤500] → `{calendar_id, items, complete, next_cursor}`. Повторы развёрнуты, как в occurrences.
GET /api/v2/events/{id} — запись события (как в `/api/entities`).
POST /api/v2/events[?calendar_id=] — тело = payload события, необязательный `Idempotency-Key: <uuid>` → 201, результат команды. Приложение пишет только в свой календарь: другой `calendar_id` → 403, удалённый календарь приложения → 403 до повторного согласия.
PATCH /api/v2/events/{id}[?occurrence_key=&scope=this|thisAndFollowing|series] — нужен `If-Match: <revision>` (без него 428, устаревший → 409 `conflict`); `Idempotency-Key` необязателен. DELETE — те же параметры → `{id, deleted: true}`. Приложение меняет только события своего календаря (иначе 403).
В ответах v2 у события есть поле `external_id` (`null`, если его не задавали).
**external_id (D37, wave 4).** Приложение может передать в теле POST поле `external_id`: строку 1–255 символов, свой ID события, например «урок №123». Интерфейс календаря его не задаёт (→ 422).
Пара (календарь приложения, приложение, `external_id`) уникальна. Повторный POST с тем же `external_id` обновляет найденное событие и отвечает 200, а не создаёт новое (201). `If-Match` при этом необязателен: если передан, устаревшая ревизия → 409.
Если пользователь удалил это событие, повторный POST → 409 `conflict` с `details: {entity_id, deleted: true}`: событие не воскрешается.
Повтор с тем же `Idempotency-Key` возвращает исходный результат.

**Tasks и plans (wave 5)** — те же правила, что у событий:
- `GET/POST /api/v2/tasks`, `GET/PATCH/DELETE /api/v2/tasks/{id}`;
- то же для `/api/v2/plans`;
- `external_id` с той же логикой (повторный POST обновляет, удалённое не воскрешает).

Список `GET /api/v2/tasks?calendar_id=&from=&to=` отдаёт задачи на эти дни, просроченные и без даты; выполненные в него не попадают.

**Действия (wave 5).** `POST /api/v2/{events|tasks|plans}/{id}/{confirm|complete|restore}`. Тело — payload, как у `/integration/v1/commands`. Нужен `If-Match`; необязательны `Idempotency-Key`, `occurrence_key`, `scope`.
- `confirm` — «было/не было»: `{status: occurred|not_occurred|revoked, happened_date}`;
- `complete` — выполнить задачу, только tasks;
- `restore` — вернуть удалённое.

Приложение может делать это только со своими записями (иначе 403).

**Чтение (wave 5).**
- `GET /api/v2/agenda?calendar_id=&from=&to=` — как `/integration/v1/agenda` (`items`, `overdue_tasks`, `undated_tasks`, `smart_day` …), у элементов есть `external_id`.
- `GET /api/v2/occurrences/{entity_id}?occurrence_key=`.
- `GET /api/v2/confirmations/{entity_id}?occurrence_key=` → `{confirmation}`.
- `GET /api/v2/history?from=&to=&cursor=&limit≤100` — отметки «было/не было».
- `GET /api/v2/reminder-source?calendar_id=&from=&to=` (1–7 дней).

Приложению для чтения нужен `events.read`, и оно видит только доступные ему календари. Запись в чужом календаре → 404; история фильтруется по этим календарям. Интерфейсу (cookie) для истории нужен `calendar:history`.

Пока нет (позже): `freebusy`, участники.

## Sync (D37, wave 4)
GET /api/v2/changes?cursor=&limit≤500 → `{items, next_cursor, complete, server_now}`.
Запись ленты: `{id, calendar_id, entity_id, kind: event|task|plan, operation, revision, deleted, actor, changed_at}`. `actor` = `"user"` (интерфейс календаря и мост Folio) или `"app:<client_id>"`: по нему приложение отсеивает собственные правки.
Приложению нужен `events.read`. Оно видит только изменения в доступных ему календарях: отмеченных на экране согласия и своём. Интерфейс (cookie) видит весь аккаунт.
Без `cursor` лента идёт с начала. `next_cursor` выдаётся всегда, его надо сохранить и передать в следующий раз; `complete: false` значит, что есть ещё страницы. Курсор привязан к читателю: чужой или испорченный → 409 `cursor_invalid`.
POST /api/v2/webhooks — только приложение, нужен `events.read`. Тело `{url}`: https, без логина/пароля в URL и без `#`, иначе 422. Ответ 201 `{id, url, secret: "pcw_…", created_at}`, `secret` показывается один раз. Не больше 5 на подключение (→ 409). Интерфейс → 403.
DELETE /api/v2/webhooks/{id} → `{id, deleted: true}`; чужой → 404.
Уведомление: `POST <url>`, JSON `{type: "changes", webhook_id, change_cursor}`. Заголовки: `X-Calendar-Timestamp: <unix-секунды>` и `X-Calendar-Signature: sha256=<hex HMAC-SHA256(secret, "<timestamp>." + тело)>`. Получатель проверяет подпись и свежесть отметки времени, отвечает 2xx, а за данными идёт в ленту со своего сохранённого курсора. `change_cursor` — позиция ленты после этих изменений.
Свои правки приложения не вызывают уведомлений. Много изменений подряд дают одно уведомление.
Неудача (не 2xx, таймаут 5 с, редирект, адрес не публичный) → повторы через 30 с, 1, 5, 15, 30 мин, затем раз в час, до 24 часов. После этого уведомление снимается; подписка остаётся, лента хранит всё.
Отзыв подключения останавливает уведомления.

## Folio bridge switch (wave 5, §8.4)
`FOLIO_BRIDGE_ENABLED` (по умолчанию `true`). При `false`:
- запросы со старым JWT моста (`/api/integration/v1/*` и любые другие) → 401;
- `GET /api/auth/folio` → 401.

OAuth-токены, сессии и вход по логину продолжают работать. Выключать, когда в Folio не осталось пользователей на старой схеме. (Сервисный токен `FOLIO_SERVICE_TOKEN` в коде уже не проверяется.)

## Stable errors
validation_error, clarification_required, not_found, ambiguous_target, draft_expired, draft_already_completed, ai_provider_error, transcription_error, database_error, unauthorized, forbidden, conflict, unavailable, rate_limited.

Не отдавать stack trace/secrets.
