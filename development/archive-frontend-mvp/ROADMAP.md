# Development Roadmap

The agent works one wave at a time.

## Wave 0 — Repository bootstrap
Project setup, chosen stack, tooling, lint/typecheck/test/build, directory conventions, AGENTS integration.

## Wave 1 — Domain and persistence
Models, validation, IDs, repository interfaces, IndexedDB adapter, seed/default calendar/categories.

## Wave 2 — Day calendar
Today startup, day timeline, event rendering, create/edit/delete, click-to-create.

## Wave 3 — Week calendar
Week grid, navigation, multi-day event positioning, overlap layout.

## Wave 4 — Month calendar
Month grid, navigation, event summaries, day opening.

## Wave 5 — Event interaction
Drag, resize, move between days, overlap warnings, mobile-safe interactions.

## Wave 6 — Recurrence
Daily, weekly, selected weekdays, monthly, end conditions, occurrence generation, exceptions, edit/delete scopes.

## Wave 7 — Plans
Plan creation/editing, checklist, reorder, progress, calendar block.

## Wave 8 — Tasks
Undated/dated tasks, today task area, move task between dates.

## Wave 9 — Lists
User lists and list items, ordering, completion.

## Wave 10 — Categories/search/filter
Categories, per-event colors, global search, calendar filtering.

## Wave 11 — Reminders
Multiple reminders, browser notification permission/settings, scheduling limitations.

## Wave 12 — Trash
30-day trash, restore, purge.

## Wave 13 — Backup
Schema-versioned export/import and validation.

## Wave 14 — Mobile and responsive polish
Responsive layouts, touch behavior, swipe day navigation, accessibility.

## Wave 15 — UX polish
Empty states, loading/error states, performance, keyboard shortcuts where useful, final visual consistency.

## Wave 16 — Future integration readiness
Review repository/API boundaries, stable IDs, migration/export path, documentation. Do not implement server sync unless separately requested.
