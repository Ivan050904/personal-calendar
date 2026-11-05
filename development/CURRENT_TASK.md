# Current Task

Calendar Platform — wave 1 (accounts and login): **done 2026-11-05**, waiting for the owner before wave 2 (multiple calendars).

Spec: `docs/18_CALENDAR_PLATFORM.md`. Decisions: D34–D38 in `docs/17_DECISIONS.md`. Contract: `docs/04_API_CONTRACT.md` → Accounts.

Done in wave 1: login + password accounts (Argon2id), sessions on `calendar_sessions`, «Личное» created with the account, owner script `backend/scripts/accounts.py` (create, reset-password), `POST /api/v2/accounts` behind `REGISTRATION_ENABLED=false`, login rate limit, password change and «sign out other devices». Folio bridge and legacy login keep working.

Not done: no UI for account settings/registration (UI redesign is a separate task); migration `d4e5f6071829` not run on MySQL/MariaDB; nothing pushed or deployed (push to `main` auto-deploys, D20).

Next: wave 2 — multiple calendars (CRUD, colour, visibility, overlay in the current UI). Start only on the owner's command.
