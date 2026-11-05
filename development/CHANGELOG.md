# Changelog

## Unreleased

### Calendar platform wave 6 — invitations / shared events (2026-11-06)

- `event_attendees` (Alembic `293a4b5c6d74`, checked on SQLite with upgrade, downgrade and upgrade again).
- API: `POST`/`GET /api/v2/events/{id}/attendees`, `PATCH …/attendees/me`, `GET /api/v2/invitations`, `GET /api/v2/invitations/occurrences`; new scope `sharing.invite`, not granted to clients by default.
- Rules: only the organizer edits (an invitee gets 403 on v2 and 404 on the old commands). Invite by existing active login only; inviting the same login twice is idempotent.
- Feed and webhooks: the invitee's feed gets `invited` and every organizer change; the organizer's feed gets `responded`. The invitee's app sees these only with `sharing.invite`.
- UI: invitations overlay the board (pending ones greyed with ✉); Settings → «Приглашения» with «Принять/Отклонить»; scope label added.
- `test_owner_script_validates_redirect_uris` now uses `freebusy.read` as its unknown scope, since `sharing.invite` became real.
- Two frontend tests mock the new invitations request; added tests for the invitation overlay and for the board loading when that request fails.
- Verified:
  - backend 190 passed and 1 real-AI skip (8 new); a mutation check on organizer-only edits, feed mirroring, hiding declined, the app scope, the invitee webhook and inviting yourself turns the tests red;
  - frontend 89 passed (2 new); tsc and build ok; lint 0 errors (4 existing warnings);
  - in the browser on a temporary SQLite API: one account invites another, the guest sees «✉ Ужин вдвоём» on the board, accepts in Settings, and the event shows normally. Found and fixed during this check: the Settings list showed the time in the browser's zone; it now uses the event's zone.
- Not run: the MySQL/MariaDB migration.

### Calendar platform wave 5 — Folio migration, calendar side (2026-11-06)

- Owner decision D39: API v2 first gets everything Folio uses in `/integration/v1`; old Folio records stay in «Личное», readable but not editable by apps.
- `/api/v2/tasks` and `/api/v2/plans` work like events, with `external_id` (Alembic `18293a4b5c63`, checked on SQLite with upgrade, downgrade and upgrade again). The events router became a generic `entities_v2`.
- `POST /api/v2/{events|tasks|plans}/{id}/{confirm|complete|restore}`.
- `GET /api/v2/agenda`, `/occurrences/{id}`, `/confirmations/{id}`, `/history` (filtered to the app's calendars), `/reminder-source`.
- `POST /api/v2/me/credentials` plus a «Логин и пароль» block in Settings, for accounts without a login (made through Folio, or the env owner).
- `FOLIO_BRIDGE_ENABLED` switches off the bridge JWT and `/auth/folio` (401).
- Verified:
  - backend 182 passed and 1 real-AI skip (7 new); a mutation check on the history filter, the own-calendar write rule, the bridge switch, login-once and the entity reads turns the tests red;
  - frontend 87 passed; tsc and build ok; lint 0 errors (4 existing warnings);
  - in the browser on a temporary SQLite API: the env owner without a login sees the block, sets a login and password, and signs in with them as the same account.
- The test module soft-deletes its own calendars and plans so the unscoped `test_repositories.py` keeps passing.
- Not run: MySQL/MariaDB migrations. Folio's own side is not done (handoff updated).

### Calendar platform wave 4 — sync: external ids, changes feed, webhooks (2026-11-06)

- Events get `source_client_id` + `external_id`, unique per calendar; Alembic `0718293a4b52`, checked on SQLite with upgrade, downgrade and upgrade again.
- An app's `POST /api/v2/events` with a known `external_id` updates that event (200) instead of duplicating it. An optional `If-Match` gives 409 on a stale revision. An event the user deleted is not resurrected (409). `external_id` appears in v2 event responses.
- `calendar_changes.actor` (`user` / `app:<client_id>`) and `GET /api/v2/changes`, filtered to the calendars the reader may see; the cursor is bound to the reader.
- `POST`/`DELETE /api/v2/webhooks`:
  - HMAC-SHA256 signed hints with a timestamp; changes are coalesced and the app is not notified of its own changes;
  - only https URLs to public addresses, checked before every delivery; no redirects;
  - retries back off from 30 s to 1 h for up to 24 h;
  - delivered by an in-process loop started in the app lifespan (`WEBHOOK_DISPATCH_ENABLED`, off in tests).
- Verified: backend 175 passed and 1 real-AI skip (14 new). A mutation check on the feed filter, own-change skip, upsert, actor and revoked grant turns the tests red. Frontend 87 passed; tsc and build ok; lint 0 errors (4 existing warnings). The delivery loop was smoke-checked in a started app.
- Not run: the MySQL/MariaDB migration; a real outbound HTTP delivery, since tests mock the HTTP call.

### Calendar platform wave 3 — OAuth for apps and API v2 events (2026-11-05)

- Hand-written OAuth 2.0 server (D35) under `/api/oauth/*`: authorize (login form + consent with calendar picker, CSRF, anti-framing), token (authorization_code with PKCE S256, refresh with rotation), revoke, userinfo, `/api/.well-known/oauth-authorization-server`. Tables `oauth_clients`, `oauth_grants`, `oauth_authorization_codes`, `oauth_tokens` (Alembic `f60718293a41`); all secrets stored as SHA-256.
- Code replay or rotated-refresh reuse revokes the whole grant; token endpoint rate-limited.
- Consenting with `events.write` creates the app's own calendar (`kind=app`); reconnecting after a revoke reuses it unless the user deleted it.
- `/api/v2/events` list/get/create/patch/delete (`If-Match` revision, `Idempotency-Key`). Apps read only ticked calendars and write only into their own; app tokens are refused everywhere except `/api/v2/calendars` (GET), `/api/v2/events*` and `/api/oauth/userinfo`.
- `/api/v2/grants` list/revoke; Settings → «Подключённые приложения» with «Отключить».
- Owner script `backend/scripts/oauth_clients.py` (create/list/disable).
- Verified:
  - backend 161 passed and 1 real-AI skip (40 new OAuth tests); a mutation check on PKCE, refresh reuse, the app allowlist and calendar reuse turns the tests red;
  - frontend 87 passed; tsc and build ok; lint 0 errors (4 existing warnings);
  - in the browser on a temporary SQLite API: the consent page, Allow → redirect with code and state, the app server exchanges the code, sees only the ticked calendar, its lesson shows on the board, it is refused `/api/v2/me`, and a code replay gives `invalid_grant`; Settings lists the app.
- Not run: the MySQL/MariaDB migration (no local MySQL). The post-wave security review has not been run.

### Calendar platform wave 2 — several calendars (2026-11-05)

- `calendars` gets `kind` (personal/user/app), `source_client_id`, `color`, `visible`, `sort_order`; Alembic `e5f607182930` marks each owner's default calendar `personal` (verified on SQLite with data, plus downgrade/upgrade).
- `/api/v2/calendars` list/create/patch/delete (soft); «Личное» cannot be deleted; foreign calendars → 404. Legacy `PUT /api/entities/calendars` no longer resets kind/colour/visibility.
- `POST /api/commands` accepts optional `calendar_id` on create only.
- UI (API mode): board overlays events and plans of every visible calendar, non-primary ones in their calendar colour; event form gets a «Календарь» picker when there is a choice; Settings → «Календари» (visibility, colour, rename, add, delete).
- Verified: backend 121 passed/1 real-AI skip (12 new); frontend 87 passed (4 new); build ok; lint 0 errors (4 existing warnings). Manually checked in the browser on a temporary SQLite API: create «Спорт», create an event into it (shows in its colour, stored in that calendar), hide it (disappears). MySQL/MariaDB migration not run locally.

### Calendar platform wave 1 — accounts and login (2026-11-05)

- Own accounts on `calendar_principals`: `login`, Argon2id `password_hash` (new dependency `argon2-cffi`), `display_name`, `created_at`; Alembic `d4e5f6071829` (batch mode, verified upgrade/downgrade/upgrade on empty SQLite).
- `POST /api/auth/login` checks calendar accounts first (case-insensitive login), then the env legacy login; identical 401 for unknown login and wrong password; 5 failures per login / 20 per IP in 15 min → 429.
- `/api/v2/accounts` (behind `REGISTRATION_ENABLED=false`, creates «Личное»), `/api/v2/me`, `/api/v2/me/password` (revokes other sessions), `/api/v2/me/sessions/revoke-others`; account management is session-only.
- Owner script `backend/scripts/accounts.py` (create, reset-password) prints a one-time temporary password; reset revokes all sessions.
- Folio bridge and legacy login unchanged. Verified: backend 109 passed/1 real-AI skip (14 new); frontend 83 passed; build ok; lint 0 errors (4 existing warnings). MySQL/MariaDB migration not run locally (no local MySQL).

### Calendar platform spec (2026-11-05)

- Added `docs/18_CALENDAR_PLATFORM.md`, approved by the owner: own accounts (login + password, no email), OAuth 2.0 Authorization Code + PKCE for registered apps, multiple calendars with per-app write calendars and an overlay view, sync (external IDs, changes feed, webhooks), attendees for shared events, Folio migration, waves 1–6.
- Recorded D34–D38 in `17_DECISIONS.md` (D34 supersedes D17's no-accounts/OAuth rule).
- Added `development/handoff/FOLIO_OAUTH_MIGRATION.md` for the Folio agent (start only after calendar waves 3 and 5 are live).
- No code changes; wave 1 not started.

### Calendar review closure (2026-10-10)

- Historical completion corrections preserve the next open rolling task and its stable confirmation ID.
- Splitting a count-limited series carries only remaining valid occurrences, including DST gap policy.
- Exact moved-occurrence lookup derives the date in the source IANA zone.
- Task/plan editors and task actions send their displayed base revision/original due; stale tabs receive conflicts.
- Async plan/category snapshots discard responses after effect teardown; removed compiler-incompatible week memoization and unused compatibility arguments without relaxing lint rules.
- Verified: backend95 passed/1 real-AI skip; frontend83 passed; build/typecheck/lint exit0 (four existing lint warnings). Local new calendar only; old data import and deployment deferred.

### Calendar integration local R0–R5 (2026-10-09)

- Synthetic isolated tests; owner-bound principals/sessions, scoped bridge and opaque launch exchange.
- UTC/all-day server projections, moved exceptions, stable occurrence IDs and bounded pagination.
- Atomic revision commands/receipts, rolling task confirmations, history/change/reminder source reads.
- API UI uses server projections/commands; device startup preserves source timezone; principal switch remounts private state; exact launch targets and 10/20 minute presets.
- Production rollout, legacy import and personal database migration were not performed.

### Changed (Mobile sidebar + Tasks UX)

- Mobile: hamburger opens full left sidebar drawer; bottom tabs kept (D29).
- Tasks: clearer composer (title+Add, then date/repeat); two-column buckets on wide desktop; compact row delete (D30).

### Changed (Sidebar nav polish)

- Primary nav: inline SVG icons, quieter active/hover tint (no solid accent fill), icon-only rail when collapsed, SVG chevron toggle; mobile tabs use icon-over-label.

### Changed (Wave 6 · Reminder PWA)

- Manifest + `/sw.js`; reminders prefer SW `showNotification`; settings copy documents tab vs PWA limits (D28).

### Changed (Wave 5 · Week DnD)

- Drag events across week slots via `moveEvent` (plans not draggable).

### Changed (Wave 4 · Lists / plan checklist)

- List item delete + ↑↓ reorder; plan checklist delete + reorder.

### Changed (Wave 3 · Categories)

- EventForm category select; Settings CRUD for categories.

### Changed (Wave 2 · All-day)

- EventForm «Весь день»; day/week all-day strip; AI «весь день» → allDay (D27).

### Changed (Wave 1 · Plans on week)

- Week grid shows plans as dashed blocks; click opens dock checklist for that day.

### Fixed (Wave 0 · AI speech time)

- Parse `к 9 часам`, bare `сегодня 18:30`, and clearer draft missing-field labels (время vs дата).

### Changed (Sidebar polish)

- Collapse control: panel icon + «Свернуть» label in a footer with hairline (no lonely chevron box).
- Soft top wash + collapsed brand mark «C».

### Added (Recurring tasks · D26 / ADR-015)

- Tasks can repeat daily / weekly / monthly (reuse `RecurrenceRule`); due date required.
- Completing a recurring task advances `dueDate` to the next occurrence (rolling).
- Tasks form: «Повтор» select; Today / «Сегодня» also show incomplete overdue dated tasks.
- Backend: `tasks.recurrence_rule_id` + Alembic migration.

### Fixed (AI «сегодня» + «на 20.00»)

- Parse speech times `на 20.00` / `на 20 00` (not only `в …`); keep «сегодня» as explicit date so drafts fill start/end instead of asking again.

### Fixed (AI latency)

- Production AI switched from slow NVIDIA DeepSeek (~50s, timeouts) to Groq `openai/gpt-oss-20b` via NL proxy (~1s).

### Fixed (Whisper via NL proxy)

- Beget cannot call `api.groq.com` (403); production Whisper goes through Folio AI proxy `/groq/v1` with the proxy token.

### Fixed (Remote Whisper · D23)

- Production speech uses remote Groq Whisper (`WHISPER_BACKEND=remote`) — no local torch/whisper on Beget.
- Deploy upserts Whisper remote env on every release.

### Changed (Plans + reminders · D24)

- Day dock: create plan, expand checklist, toggle/add items, delete plan; plans drawn on day timeline.
- Browser notifications poll due reminders while the tab is open.

### Changed (Week nav + every-N-days · D22)

- Week view ←/→ (and keyboard) moves by one week.
- Event form: «Раз в N дней» with user-chosen interval (stored as daily + interval).

### Changed (Week empty-cell create)

- Clicking an empty week grid cell opens the create-event form for that day and hour (same as day view hour slots).

### Fixed (Event date/time shift · D21)

- Week/month calendars refresh after save (no more stale “Physical” stuck on Saturday).
- Calendar timezone syncs to the device; existing events keep the same wall clock when the zone was wrong (e.g. UTC seed).
- AI draft times and “now” / FAB use calendar timezone helpers instead of brittle `Date` local parsing.

### Added (CI auto-deploy · D20)

- GitHub Actions workflow on push to `main`: build SPA and run `scripts/deploy_calendar.py` to Beget using secret `BEGET_SSH_PASSWORD`.
- Decision D20 recorded in `docs/17_DECISIONS.md`.

### Added (Visible hours preference · D19)

- Settings: «Часы в расписании» — contiguous range from–to (default 0–23), stored in localStorage.
- Day and week timelines hide hours outside the range; hours with events and today’s current hour stay visible; event/now tops remapped to the compressed list.
- Decision D19 recorded in `docs/17_DECISIONS.md`.

### Added (Production deploy · D18)

- Live at https://calendar.folio-one.ru (HTTPS, login gate).
- Host systemd API/SPA + Docker MariaDB; nginx via billing-nginx; `scripts/deploy_calendar.py`.
- AI on prod routes through NL FirstByte proxy (`91.186.214.4:8787`, NVIDIA / DeepSeek) — direct Groq from Beget returns 403.
- Decision D18 recorded in `docs/17_DECISIONS.md`.

### Added (Single-user auth · D17)

- Login page as first screen in API mode; session cookie after `POST /api/auth/login`.
- Backend protects API when `AUTH_USERNAME` / `AUTH_PASSWORD` / `AUTH_SESSION_SECRET` are set; logout in Settings.
- Decision D17 recorded; `docs/15_SECURITY.md` and API contract updated.

### Changed (Assistant draft recurrence · D16)

- Draft card shows date/time and recurrence summary («Без повтора» / weekly days) before confirm.
- «Изменить форму» includes Повтор + weekdays for create-event; PATCH can clear recurrence.
- Speech parse: «повторником» → weekly Tue; «название X» strips cue word from title.
- Decision D16 recorded in `docs/17_DECISIONS.md`.

### Changed (Assistant as primary section · D15)

- «Ассистент» in left sidebar / bottom tabs as its own screen (not a calendar overlay).
- Removed toolbar «Ассистент» button and drawer; chat history kept while switching sections.
- Decision D15 recorded in `docs/17_DECISIONS.md`.

### Changed (Left sidebar nav · D14)

- Desktop: primary nav moved to sticky left sidebar; calendar header starts higher.
- Sidebar collapse via bottom chevron (‹ / ›); preference saved in localStorage.
- Mobile ≤600px: bottom tabs unchanged (D11); collapse control hidden.
- Decision D14 recorded in `docs/17_DECISIONS.md`.

### Changed (Pink accent + flat sections · D13)

- App-wide dusty rose accent and warm neutrals (replaces navy/blue-gray tokens).
- Tasks / Lists / Trash: flat layout — line composer, divider rows, no nested cards or section eyebrow.
- Decision D13 recorded in `docs/17_DECISIONS.md`.

### Changed (Tasks / Lists / Trash craft · D12)

- Tasks: composer separated from list; buckets «Без даты» / «Сегодня» (+ focus date); TaskRow with due chip and secondary delete.
- Lists / Trash / Today dock reuse the same row and panel craft (D10 tokens).
- Decision D12 recorded in `docs/17_DECISIONS.md`.

### Changed (Mobile adaptation · D11)

- Bottom tab bar (≤600px) with safe-area; scrollable calendar toolbar; FAB for new event.
- Day: horizontal swipe only when |dx| > |dy|; drag/resize off on coarse pointer.
- Week: sticky time column + touch scroll; month larger hit targets.
- Assistant fullscreen sheet with close; event form sticky Save/Cancel.

### Changed (Frontend UI overhaul · D10)

- Primary nav: Calendar / Tasks / Lists / Trash / Settings; startup on Today day view.
- Smart Day as calendar sub-view «Сейчас»; Assistant as keep-mounted drawer from calendar toolbar.
- Slate/ink visual system; day now-line + dimmed past; unified week/month/chat craft.
- Event form progressive disclosure; scope dialog single primary; RU draft/trash labels; delete confirm.
- Search hits navigate to entity; active nav uses `aria-current="page"`.

### Changed (MySQL SSOT)

- Board defaults to FastAPI/MySQL (`VITE_USE_API=true`). IndexedDB only if explicitly `false`.
- Removed AI confirm → IndexedDB dual-write (`apply-ai-draft-local`).
- Decision D9 recorded in `docs/17_DECISIONS.md`.

### Fixed (logic audit)

- `get_local_calendar` prefers `Personal Calendar`, else earliest `createdAt`.
- Confirm idempotency flag `result.idempotent` (server-side).
- CLARIFY drafts promote to CREATE when required fields are filled.
- Event time without explicit day asks for date (change spec); clock bounds use calendar timezone.
- Ambiguous target errors list candidate titles in the assistant chat.
- TargetResolver ignores command words in the query.

### Added

- Waves 0–15 phase-2 implementation on top of the existing frontend MVP.
- Wave 0 audit: React/Vite/TS + IndexedDB frontend green; MariaDB local for MySQL-compatible storage.
- Wave 1: FastAPI foundation (`backend/`), config, Alembic, `/api/health`, stable errors.
- Wave 2: MySQL entity tables + SQLAlchemy repositories (Calendar/Event/Plan/Task/List/…).
- Wave 3: CRUD `/api/entities/*` + frontend `ApiRepository` (`VITE_USE_API`).
- Wave 4: Smart Day screen «Сейчас» + `/api/smart-day`.
- Wave 5: Plan progress `completed/total/percentage` (UI + `/api/plans/{id}/progress`).
- Waves 6–8: AIProvider (mock/OpenAI-compatible), behavior heuristics, draft engine (`ai_drafts`).
- Waves 9–10: CREATE/UPDATE/DELETE execution + TargetSelector resolution.
- Wave 11: Assistant UI (`AiChatPanel`) with draft confirm/cancel/voice shell.
- Wave 12: `/api/ai/transcribe` + local `openai/whisper` from GitHub; benchmark on RTX 3050 → model `small`.
- Wave 13: AI rate limit middleware; secrets stay in `.env` / `secrets/` (gitignored).
- Wave 14: real Groq smoke (`openai/gpt-oss-20b`); E2E path Frontend→API→MySQL via `VITE_USE_API`.
- Wave 15: final audit docs/changelog; frontend 58 tests + backend 29+smoke green.

### Notes

- Frontend MVP docs archived under `docs/mvp-frontend/`.
- Docker not used (per MVP spec).
- NVIDIA key also present in `secrets/key.txt`; default provider configured to Groq after model availability check.

## Package baseline (from calendar_final_cursor_package)

- Finalized Smart Day + AI + backend specification.
- Backend: FastAPI + MySQL.
- Docker explicitly removed from MVP requirements.
- 16-wave roadmap + AI/Draft/Whisper/security specs.
