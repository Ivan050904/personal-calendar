# Current Task

Calendar Platform — wave 4 (sync: external_id, changes feed, webhooks): **done 2026-11-06**, waiting for the owner before wave 5 (Folio migration to OAuth).

Spec: `docs/18_CALENDAR_PLATFORM.md`. Decisions: D34–D38 in `docs/17_DECISIONS.md`. Contract: `docs/04_API_CONTRACT.md` → Accounts, Calendars, OAuth for apps, Events v2, Sync.

Done so far:
- wave 1: accounts, login + password, owner script, registration behind a flag;
- wave 2: calendars with kind/colour/visibility, overlay in the current UI;
- wave 3: OAuth server under `/api/oauth/*`, consent screen, app calendars, `/api/v2/events`, `/api/v2/grants` + Settings → «Подключённые приложения», `backend/scripts/oauth_clients.py`;
- wave 4: `external_id` upsert on events, `/api/v2/changes` with `actor`, signed webhooks with retries (in-process loop).

Known limits:
- tasks and lists live only in «Личное»;
- an event cannot be moved to another calendar;
- v2 has no tasks/plans (so no `external_id` for them), freebusy or invitations yet;
- webhook delivery has a DNS-rebinding gap between the address check and the connection (accepted: only owner-registered apps);
- the login rate limiter and the token rate limiter are in-memory (per process).

Not done:
- migrations `d4e5f6071829`, `e5f607182930`, `f60718293a41`, `0718293a4b52` not run on MySQL/MariaDB;
- the separate security review after wave 3 has not been run;
- nothing pushed or deployed (push to `main` auto-deploys, D20).

Next: wave 5 — Folio migration (login/password for Folio-created accounts, Folio as an OAuth client, old bridge in parallel). Start only on the owner's command.
