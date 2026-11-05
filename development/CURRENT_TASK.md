# Current Task

Calendar Platform — wave 5 (Folio migration, calendar side): **done 2026-11-06**. Waiting for the owner before wave 6 (invitations / shared events).

Spec: `docs/18_CALENDAR_PLATFORM.md`. Decisions: D34–D38 in `docs/17_DECISIONS.md`. Contract: `docs/04_API_CONTRACT.md` → Accounts, Calendars, OAuth for apps, Events v2, Sync.

Done so far:
- wave 1: accounts, login + password, owner script, registration behind a flag;
- wave 2: calendars with kind/colour/visibility, overlay in the current UI;
- wave 3: OAuth server under `/api/oauth/*`, consent screen, app calendars, `/api/v2/events`, `/api/v2/grants` + Settings → «Подключённые приложения», `backend/scripts/oauth_clients.py`;
- wave 4: `external_id` upsert on events, `/api/v2/changes` with `actor`, signed webhooks with retries (in-process loop);
- wave 5 (D39): v2 parity with `/integration/v1` (tasks, plans, confirm/complete/restore, agenda, history, reminders), `/api/v2/me/credentials` + Settings block, `FOLIO_BRIDGE_ENABLED` switch.

Known limits:
- tasks and lists live only in «Личное»;
- an event cannot be moved to another calendar;
- v2 has no freebusy or invitations yet;
- old Folio records stay in «Личное», read-only for apps (D39);
- the UI does not prompt for a login on its own: the block lives in Settings;
- the bridge stays on until Folio has moved: Folio's side is the handoff `development/handoff/FOLIO_OAUTH_MIGRATION.md`;
- webhook delivery has a DNS-rebinding gap between the address check and the connection (accepted: only owner-registered apps);
- the login rate limiter and the token rate limiter are in-memory (per process).

Not done:
- migrations `d4e5f6071829`, `e5f607182930`, `f60718293a41`, `0718293a4b52`, `18293a4b5c63` not run on MySQL/MariaDB;
- the separate security review after wave 3 has not been run;
- nothing pushed or deployed (push to `main` auto-deploys, D20).

Next: wave 6 — invitations (attendees by login, pending/accepted/declined, shown to the invitee). Start only on the owner's command.
