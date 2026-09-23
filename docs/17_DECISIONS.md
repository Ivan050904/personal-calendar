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

D11 — Mobile (≤600px): primary nav becomes sticky bottom tabs with safe-area; calendar toolbar scrolls horizontally; «Новое событие» is a FAB; day drag/resize disabled on coarse pointer (swipe day change kept); week uses sticky time column + horizontal scroll. (Assistant sheet under Calendar superseded by D15.)

D12 — Tasks / Lists / Trash craft aligned to D10 slate/ink: composer card for create (task form fields unchanged: title + optional date + save); task list always shows «Без даты» and «Сегодня», plus a third section when composer date ≠ today; shared TaskRow (checkbox, title, due chip, secondary delete); Lists/Trash reuse the same row/section/composer pattern. No new domain fields.

D13 — App-wide accent shifts from navy slate to dusty rose (`#b44a6a` light / `#e8a0b4` dark) with warm neutrals (no cool blue-gray chrome). Tasks / Lists / Trash are flat: no nested cards or «РАЗДЕЛ» eyebrow; single-line composer; list rows use hairline dividers only. Typography fonts from D10 kept.

D14 — Desktop (>600px): primary nav lives in a sticky left sidebar (Calendar / Tasks / Lists / Trash / Settings), not as a top tab row. Sidebar can collapse via a bottom chevron control (preference in localStorage); collapsed rail is ~52px. Mobile (≤600px) keeps D11 bottom tabs (toggle hidden).

D15 — Assistant is a top-level primary section (sidebar / bottom tabs), not a calendar drawer overlay. Chat stays mounted while switching sections so conversation history is preserved; confirm still refreshes board data via `onApplied`.

D16 — Assistant draft card (per `01_CHANGE_SPEC`): compact summary always shows date/time and recurrence («Без повтора» / weekly days); «Изменить форму» opens editable fields including create-event recurrence (frequency + weekdays). PATCH may clear `payload.recurrence` with null. No new domain fields.

D17 — Single-user gate for API mode (required before public deploy): login page → `POST /api/auth/login` with username/password from backend env (`AUTH_USERNAME`, `AUTH_PASSWORD`, `AUTH_SESSION_SECRET`); httpOnly signed session cookie; all `/api/*` except `/health` and `/auth/login` require a valid session. IndexedDB opt-out (`VITE_USE_API=false`) stays local-unauthenticated. No multi-user accounts, OAuth, or password reset in MVP.

D18 — Production host `calendar.folio-one.ru` on Beget VPS `155.212.132.213`: SPA + FastAPI on host systemd (`personal-calendar-web` :8061, `personal-calendar-api` :8060), MariaDB in Docker (`calendar-mariadb` :3307), edge nginx via existing `billing-nginx` + Let's Encrypt. Redeploy with `scripts/deploy_calendar.py`. App itself is not containerized (D2); Docker used only for DB and shared edge proxy.

D19 — Visible day/week hours are a local preference (localStorage), not a domain field: contiguous range `startHour`–`endHour` (default 0–23). Day and week timelines omit hours outside the range. Hours that contain events (or today’s “now” hour) stay visible so layout and event blocks remain correct; absolute tops are remapped to the compressed hour list. Settings UI edits the range; no server sync in MVP.

D20 — Production auto-deploy: push to `main` (or manual `workflow_dispatch`) runs GitHub Actions `.github/workflows/deploy.yml` — `npm ci` + `npm run build` then `scripts/deploy_calendar.py` over SSH to Beget (`calendar.folio-one.ru`). SSH password lives in repo secret `BEGET_SSH_PASSWORD` (never in git). Server `.env` is preserved across redeploys (D18).

D21 — Calendar timezone follows the device IANA zone on boot (`ensureLocalCalendar`). If the stored calendar zone differs, event wall-clock times are reinterpreted so the same local clock face is kept. Week/month views reload on `boardRevision` after create/update/delete. AI draft datetime fields use `zonedInputToIso` / `isoToZonedInput` (not `Date` local parsing). Now-line and “new event at now” use calendar timezone hours.

D22 — Week view date arrows / keyboard jump by 7 days (not 1). Event form exposes every-N-days as frequency daily + user interval (>=2); domain already supported interval for daily generation.

D23 — Production Whisper is remote via Folio AI proxy Groq path (http://91.186.214.4:8787/groq/v1). Beget IPs get 403 from api.groq.com directly; never install local torch/openai-whisper on Beget. WHISPER_BACKEND=remote; WHISPER_API_KEY uses the proxy token (same as AI_API_KEY). Local GPU Whisper remains optional for development.

D24 — Plans become first-class in day dock: create plan, expand checklist, toggle/add items; plans also render on the day timeline. Browser reminders poll due offsets while the tab is open and notifications are enabled.

