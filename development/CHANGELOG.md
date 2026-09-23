# Changelog

## Unreleased

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
