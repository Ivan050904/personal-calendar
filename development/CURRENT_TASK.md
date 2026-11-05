# Current Task

Calendar Platform — wave 3 (OAuth for apps + API v2 events): **done 2026-11-05**, waiting for the owner before wave 4 (sync: external_id, changes feed, webhooks).

Spec: `docs/18_CALENDAR_PLATFORM.md`. Decisions: D34–D38 in `docs/17_DECISIONS.md`. Contract: `docs/04_API_CONTRACT.md` → Accounts, Calendars, OAuth for apps, Events v2.

Done so far:
- wave 1: accounts, login + password, owner script, registration behind a flag;
- wave 2: calendars with kind/colour/visibility, overlay in the current UI;
- wave 3: OAuth server under `/api/oauth/*`, consent screen, app calendars, `/api/v2/events`, `/api/v2/grants` + Settings → «Подключённые приложения», `backend/scripts/oauth_clients.py`.

Known limits:
- tasks and lists live only in «Личное»;
- an event cannot be moved to another calendar;
- v2 has no `external_id`, tasks/plans, freebusy or invitations yet;
- the login rate limiter and the token rate limiter are in-memory (per process).

Not done:
- migrations `d4e5f6071829`, `e5f607182930`, `f60718293a41` not run on MySQL/MariaDB;
- the separate security review after wave 3 has not been run;
- nothing pushed or deployed (push to `main` auto-deploys, D20).

Next: wave 4 — sync (external_id on events, changes feed per grant with actor, signed webhooks with retries). Start only on the owner's command.
