# Changelog

## Unreleased

### Added

- React + TypeScript + Vite bootstrap using npm.
- Strict TypeScript project configuration, ESLint and Vitest.
- Layered `src/` directory conventions and a minimal project-health test.
- Production build and local development scripts.
- Domain entity types, validation and stable UUID generation.
- Repository contracts and an IndexedDB adapter with calendar-scoped queries.
- Local-calendar seeding without preset categories, plus IndexedDB integration tests.
- Day calendar with a 24-hour timeline, persisted event rendering and click-to-create.
- Standard event form with create, edit and soft-delete actions.
- Timezone-safe conversion between event-form values and stored timestamps.
- Monday-first Week view with previous/next week navigation.
- Multi-day event segments and overlap-aware column layout.
- Monday-first Month view with month navigation, event summaries and day opening.
- Day-event drag to another hour, touch-safe resize control and overlap warning.
- Recurring events with daily, weekly, selected-weekday and monthly rules.
- Recurrence endings: never, until-date and occurrence-count.
- Bounded occurrence generation with modified/cancelled exceptions and this-and-following split.
- Month-end clamp policy for monthly recurrence (ADR-012) and DST-safe local wall times.
- User lists with ordered checklist items, completion toggles and soft-delete.
- Plans with create/edit/soft-delete, checklist tasks, reorder, progress and date-range listing.
- Local tasks service: create/update/soft-delete, undated and date lists, move between dates, toggle completed.
- Categories with rename/soft-delete, calendar category filter and cross-entity search.
- Event reminders with supported offsets, due-window helper and browser delivery limits (ADR-013).
- Trash helpers for 30-day purge metadata, restore and soft-delete collection.
- Schema-versioned JSON backup export and replace-only import with confirmation (ADR-014).
- App shell navigation for Calendar / Tasks / Lists / Trash / Settings.
- Mobile swipe day navigation, light/dark theme toggle, empty states and keyboard shortcuts.
