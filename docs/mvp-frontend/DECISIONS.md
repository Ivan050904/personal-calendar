# Architectural Decisions

## ADR-001 — IndexedDB for local MVP
Chosen because the app needs structured offline persistence and must later migrate to a server-backed repository.

## ADR-002 — Repository abstraction
Domain/application code must not depend directly on IndexedDB or HTTP.

## ADR-003 — Calendar entity
A Calendar exists even without an account to make future account binding straightforward.

## ADR-004 — Recurrence
A recurring event is an Event plus RecurrenceRule. Individual changes are EventExceptions.

## ADR-005 — Regular activities are events
No separate Habit entity in MVP. Timed repeating life activities use recurring events.

## ADR-015 — Date-only recurring chores are tasks
Completion-based, date-only repeating chores (e.g. meter readings) are Tasks with an optional `recurrenceRuleId` reusing `RecurrenceRule`. They never occupy timeline hours. Completing a recurring task advances `dueDate` to the next occurrence and leaves `completed=false` (rolling due date). When no next occurrence remains (`untilDate` / exhausted `occurrenceCount`), the task stays on the last due date with `completed=true`. Undated tasks cannot have recurrence.

## ADR-006 — Tasks vs plan tasks
Standalone Task and PlanTask are separate concepts. PlanTask belongs to a Plan and has no own time in MVP.

## ADR-007 — Event colors
Color is stored independently from Category and can be selected per event.

## ADR-008 — Soft deletion
Deleted objects remain restorable for 30 days.

## ADR-009 — Timezone
Timed data must preserve intended timezone/local time semantics.

## ADR-010 — No mandatory completion for events
Events are records of planned activities. Completion is not a required workflow.

## ADR-011 — Forms first
Standard forms are the reliable creation method. Natural-language quick input is optional and must confirm ambiguous parsing.

## ADR-012 — Monthly recurrence month-end policy
When a monthly rule uses `dayOfMonth` that does not exist in a target month (for example 31 in February), the occurrence is clamped to the last valid day of that month. Occurrences are never skipped solely because the month is shorter.

## ADR-013 — Browser reminder delivery limits
Reminder offsets are persisted and fire times can be computed, but a normal browser tab cannot guarantee delivery. MVP requests notification permission only when enabling notifications, handles denial gracefully, and documents lifecycle limits in Settings.

## ADR-014 — Backup import is replace-only in MVP
JSON export includes `schemaVersion`. Import validates the envelope and replaces the local dataset after explicit user confirmation. Merge import is out of MVP scope.
