# Current Task

Calendar integration with Folio — local provider implementation complete, 2026-10-10.

Four Important review findings fixed with regression tests: historical rolling completion correction, count-limited series split, moved occurrence exact lookup in source zone, and read-base revision/due preservation in task/plan drafts/actions. Fresh verification: backend95 passed/1 skipped (real AI smoke requires credentials); frontend83 passed; production build/typecheck exit0; lint exit0 with four existing warnings. Folio coordinator owns its final acceptance report. No production push/deploy or legacy import. Stop after handoff.

Authorized by user on 2026-10-08: "газ календарь делать".

Requirements and explicit new public contracts:
- C:/Users/Пользователь/Desktop/Folio2/docs/superpowers/specs/2026-10-08-calendar-integration-design.md
- C:/Users/Пользователь/Desktop/Folio2/docs/superpowers/plans/2026-10-08-calendar-provider-implementation.md
- C:/Users/Пользователь/Desktop/Folio2/docs/superpowers/plans/2026-10-08-calendar-integration.md

First isolate test storage, then owner/auth/time/projections, commands/history, and UI parity. Update docs/17_DECISIONS.md for D17/D21/D24/D28 changes before behavior changes. Existing personal data ownership is never guessed or assigned to synthetic test users. Shared router registration and linear Alembic revisions are coordinated by root.

Local development is authorized across the planned waves. Production rollout, push/main auto-deploy, personal DB migration and real Telegram delivery are not part of this task. After the final report update CHANGELOG and stop.
