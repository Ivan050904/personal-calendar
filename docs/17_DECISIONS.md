# Decisions

D1 — MySQL 8.x instead of PostgreSQL: sufficient for one-user CRUD/API workload and simpler local setup.

D2 — No Docker in MVP: local MySQL is enough; Docker may be introduced later by deployment needs.

D3 — AI never directly mutates DB: structured proposal + backend validation + user confirmation.

D4 — Every create/update/delete requires explicit confirmation.

D5 — AI is not a calendar Q&A/search assistant in MVP.

D6 — Backend TargetSelector is allowed for safe update/delete target resolution; this is controlled application logic, not DB access for the model.

D7 — One logical action per Draft; multi-action is not silently executed.

D8 — Whisper model is selected after local benchmark.

D9 — MySQL via FastAPI is the single source of truth for board data. IndexedDB remains only as an explicit opt-out (`VITE_USE_API=false`) for legacy local-only runs; AI confirm writes MySQL and the UI refreshes from the API. Dual-write into IndexedDB is removed.

D10 — Frontend visual world «время под давлением»: cool slate/ink tokens (Source Serif 4 + Source Sans 3 + IBM Plex Mono), now-line and dimmed past hours on day view. Primary nav: Calendar / Tasks / Lists / Trash / Settings (Assistant later moved to top-level — see D15); Smart Day nested under Calendar; startup opens Today day view.

D11 — Mobile (≤600px): sticky bottom tabs with safe-area remain for quick section switches; calendar toolbar scrolls horizontally; «Новое событие» is a FAB; day drag/resize disabled on coarse pointer (swipe day change kept); week uses sticky time column + horizontal scroll. Full labeled sidebar opens as a left drawer via the top hamburger (D29). (Assistant sheet under Calendar superseded by D15.)

D12 — Tasks / Lists / Trash craft aligned to D10 slate/ink: composer card for create (task form fields unchanged: title + optional date + save); task list always shows «Без даты» and «Сегодня», plus a third section when composer date ≠ today; shared TaskRow (checkbox, title, due chip, secondary delete); Lists/Trash reuse the same row/section/composer pattern. No new domain fields.

D13 — App-wide accent shifts from navy slate to dusty rose (`#b44a6a` light / `#e8a0b4` dark) with warm neutrals (no cool blue-gray chrome). Tasks / Lists / Trash are flat: no nested cards or «РАЗДЕЛ» eyebrow; single-line composer; list rows use hairline dividers only. Typography fonts from D10 kept.

D14 — Desktop (>600px): primary nav lives in a sticky left sidebar (Calendar / Tasks / Lists / Trash / Settings / Assistant), not as a top tab row. Sidebar can collapse via a bottom chevron control (preference in localStorage); collapsed rail is ~52px. Mobile drawer: D29.

D15 — Assistant is a top-level primary section (sidebar / bottom tabs), not a calendar drawer overlay. Chat stays mounted while switching sections so conversation history is preserved; confirm still refreshes board data via `onApplied`.

D16 — Assistant draft card (per `01_CHANGE_SPEC`): compact summary always shows date/time and recurrence («Без повтора» / weekly days); «Изменить форму» opens editable fields including create-event recurrence (frequency + weekdays). PATCH may clear `payload.recurrence` with null. No new domain fields.

D17 — Single-user gate for API mode (required before public deploy): login page → `POST /api/auth/login` with username/password from backend env (`AUTH_USERNAME`, `AUTH_PASSWORD`, `AUTH_SESSION_SECRET`); httpOnly signed session cookie; all `/api/*` except `/health` and `/auth/login` require a valid session. IndexedDB opt-out (`VITE_USE_API=false`) stays local-unauthenticated. No multi-user accounts, OAuth, or password reset in MVP.

D18 — Production host `calendar.folio-one.ru` on `168.113.169.26` (moved off Beget `155.212.132.213`, 2026-11-09): SPA + FastAPI on host systemd (`personal-calendar-web` :8061, `personal-calendar-api` :8060), MariaDB in Docker (`calendar-mariadb` :3307), edge nginx is the host file `/etc/nginx/sites-enabled/calendar.folio-one.ru.conf`. Redeploy with `scripts/deploy_calendar.py`. App itself is not containerized (D2); Docker used only for DB.

D19 — Visible day/week hours are a local preference (localStorage), not a domain field: contiguous range `startHour`–`endHour` (default 0–23). Day and week timelines omit hours outside the range. Hours that contain events (or today’s “now” hour) stay visible so layout and event blocks remain correct; absolute tops are remapped to the compressed hour list. Settings UI edits the range; no server sync in MVP.

D20 — Production auto-deploy: push to `main` (or manual `workflow_dispatch`) runs GitHub Actions `.github/workflows/deploy.yml` — `npm ci` + `npm run build` then `scripts/deploy_calendar.py` over SSH to `168.113.169.26` (`calendar.folio-one.ru`). SSH key lives in repo secret `RITM_SSH_KEY` (never in git). Server `.env` and the host nginx site are preserved across redeploys (D18).

D21 — Calendar timezone follows the device IANA zone on boot (`ensureLocalCalendar`). If the stored calendar zone differs, event wall-clock times are reinterpreted so the same local clock face is kept. Week/month views reload on `boardRevision` after create/update/delete. AI draft datetime fields use `zonedInputToIso` / `isoToZonedInput` (not `Date` local parsing). Now-line and “new event at now” use calendar timezone hours.

D22 — Week view date arrows / keyboard jump by 7 days (not 1). Event form exposes every-N-days as frequency daily + user interval (>=2); domain already supported interval for daily generation.

D23 — Production Whisper is remote via Folio AI proxy Groq path (http://91.186.214.4:8787/groq/v1). Beget IPs get 403 from api.groq.com directly; never install local torch/openai-whisper on Beget. WHISPER_BACKEND=remote; WHISPER_API_KEY uses the proxy token (same as AI_API_KEY). Local GPU Whisper remains optional for development.

D24 — Plans become first-class in day dock: create plan, expand checklist, toggle/add items; plans also render on the day timeline. Browser reminders poll due offsets while the tab is open and notifications are enabled.

D25 — Production AI chat uses Folio AI proxy Groq path (http://91.186.214.4:8787/groq/v1, model openai/gpt-oss-20b) because NVIDIA DeepSeek reasoning models exceed the API timeout from Beget (~50s). Whisper already uses the same proxy Groq path (D23).

D26 — Recurring tasks (ADR-015): Task may reference RecurrenceRule; create form offers daily/weekly/monthly when a due date is set; complete advances due date; Today / «Сегодня» also lists incomplete overdue dated tasks. Timed repeats remain Events.

D27 — All-day events: EventForm toggle «Весь день» stores allDay=true with local-day 00:00–23:59 bounds; day/week show a dedicated all-day strip; Smart Day ignores all-day (unchanged). AI phrases «весь день» / «на весь день» set allDay via enrich.

D28 — Reminder PWA MVP: register /sw.js + web manifest; due reminders prefer ServiceWorkerRegistration.showNotification while the app poll runs. Background delivery is best-effort (desktop Chrome/PWA); not Google-parity on iOS Safari.

D29 — Mobile navigation drawer: ≤600px shows a top app bar hamburger that opens the full labeled left sidebar as an overlay drawer (backdrop + Escape close). Bottom tabs (D11) stay for thumb-reach. Desktop collapse toggle stays desktop-only.

D30 — Tasks section layout: composer is two rows (title+Add, then date shortcuts/date/repeat); desktop ≥900px shows task buckets in two columns; TaskRow groups meta chips and uses compact icon delete. Domain fields unchanged (D12/D26).

D31 — Calendar/Folio integration v2 (2026-10-09, local authorized R0–R5): supersedes D17 global single-user gate with explicit CalendarPrincipal ownership, owner-bound revocable sessions and dedicated scoped bridge JWT (iss/aud/purpose/time claims, TTL60s, skew30s). Legacy login requires explicit enabled flag and verified principal ID. Unconfigured auth never grants access. Legacy data remains unassigned pending optional import; this clone does not infer an owner.

D32 — Supersedes D21 device-write bootstrap: opening a different device/display zone preserves calendar timezone and all event instants, with zero write requests. Server UTC-aware wire, date-only all-day exclusive bounds, bounded recurrence projection; ISO weekdays1..7. Monthly day31 clamps; DST gaps skip without consuming count, folds select earlier instant. Original occurrence identity survives moves.

D33 — Extends D24/D28: source calendar owns commands, revisions, receipts and voluntary confirmation facts. PC API task completion uses server commands; elapsed events create no facts. Rolling completion stores original due before advancing beyond happened_date; stale undo cannot roll back later completion. Folio owns background delivery preferences; browser reminders remain best effort. Existing presets preserved, 10/20 added.

D34 — Calendar platform (2026-11-05, spec `18_CALENDAR_PLATFORM.md`): the calendar is a standalone service with its own accounts — login + password (Argon2id, `argon2-cffi`), no email at all (no verification, no mail reset; owner resets passwords and creates accounts by script). Registration endpoint exists behind `REGISTRATION_ENABLED=false` until anti-abuse protection is specified. Supersedes D17 «No multi-user accounts, OAuth» and replaces the Folio-derived identity of D31.

D35 — Apps connect only via OAuth 2.0 Authorization Code + PKCE (S256), registered clients only (owner script), consent screen per account, hashed rotating tokens (access 15 min, refresh 30 days with reuse detection). Server is hand-written in the project (authlib has no FastAPI server integration). Folio shared service token and HMAC bridge (D31) run in parallel until Folio migration completes, then are removed.

D36 — An account has many calendars: «Личное», one app calendar per connected app with write scope, and user-created ones; each has a colour and visibility and the UI overlays all visible calendars. An app writes only into its own app calendar and reads only calendars the user ticked on consent.

D37 — Sync: `(source_client_id, external_id)` unique per calendar; the per-grant changes feed with `actor` is the source of truth; webhooks are HMAC-signed notifications only. Existing Idempotency-Key and revision conflicts stay.

D38 — Shared events (couples app): attendees by login with pending/accepted/declined in the organizer's calendar; only the organizer edits. Co-owned calendars are deferred.

D39 — Folio migration path (owner, 2026-11-06): before moving Folio off the bridge, API v2 gets everything Folio uses in `/integration/v1` (tasks, plans, confirm/complete/restore, agenda, occurrences, confirmations, history, reminder source) under the D36 app rules. Folio's existing records stay in «Личное»: Folio reads them if the user ticks «Личное» on consent and never edits them. New Folio records go to its own «Folio» calendar. Rejected alternatives: keeping Folio on v1 with OAuth identity, which breaks D36 write isolation; moving old «Личное» records into «Folio», which is impossible to tell apart from the user's own records. Bridge switch: `FOLIO_BRIDGE_ENABLED`.
