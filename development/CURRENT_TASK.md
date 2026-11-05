# Current Task

Calendar Platform — wave 2 (several calendars): **done 2026-11-05**, waiting for the owner before wave 3 (OAuth server + API v2 for apps).

Spec: `docs/18_CALENDAR_PLATFORM.md`. Decisions: D34–D38 in `docs/17_DECISIONS.md`. Contract: `docs/04_API_CONTRACT.md` → Accounts, Calendars.

Done so far: wave 1 (accounts, login + password, owner script, registration behind a flag) and wave 2 (calendars with kind/colour/visibility, `/api/v2/calendars`, `calendar_id` on create commands, overlay of visible calendars in the current UI, Settings → «Календари»).

Known limits after wave 2: tasks and lists live only in «Личное»; an event cannot be moved to another calendar; Folio deep links resolve only the primary calendar.

Not done: migrations `d4e5f6071829`, `e5f607182930` not run on MySQL/MariaDB; nothing pushed or deployed (push to `main` auto-deploys, D20).

Next: wave 3 — OAuth 2.0 server (authorize/token/revoke/userinfo, consent screen, PKCE, scopes), app calendars, owner script for clients. Start only on the owner's command.
