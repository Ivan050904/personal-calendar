# Current Task

Calendar Platform — wave 1 (accounts and login). **Not started**: waiting for the owner's go-ahead.

Spec: `docs/18_CALENDAR_PLATFORM.md` (§3, §11 wave 1). Decisions: D34–D38 in `docs/17_DECISIONS.md`.

Previous task (Calendar/Folio integration R0–R5, 2026-10-10) is complete and committed on `codex/calendar-integration` (ba4bb8d). Its production rollout, push/deploy and legacy import were not performed and remain outside this task.

Wave 1 scope: login + password accounts (Argon2id, new dependency `argon2-cffi`), sessions on existing `calendar_sessions`, «Личное» created with the account, owner scripts (create account, reset password), `POST /api/v2/accounts` behind `REGISTRATION_ENABLED=false`, login rate limit. Existing Folio bridge and legacy login keep working. Run the wave 1 test plan and regression check, update CHANGELOG, stop before wave 2.
