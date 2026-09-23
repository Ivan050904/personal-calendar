# Recurrence Rules

## Frequencies

1. Daily (every day, or every N days via `interval`)
2. Weekly
3. Selected weekdays
4. Monthly

`interval` defaults to 1. For daily, `interval: 3` means every 3 days from the series start.

## End conditions

- Never
- Until date
- After N occurrences

## UI

Example:

Repeat:
[ Every week ]

Weekdays:
☑ Mon ☐ Tue ☑ Wed ☐ Thu ☑ Fri ☐ Sat ☐ Sun

Ends:
○ Never
○ On date
○ After [N] occurrences

For monthly:
- repeat on the event's day-of-month by default.
- Edge cases for short months must be defined by implementation tests before coding. Do not silently invent user-visible behavior; use a documented conventional policy.

## Editing

Single occurrence:
- update exception only.

This and following:
- preserve historical occurrences;
- create a new recurrence segment from selected occurrence onward.

Entire series:
- modify base recurrence.

Delete one:
- cancellation exception.

Delete entire:
- delete series.

## Occurrence generation

Do not materialize an infinite series into the database. Generate occurrences for the requested visible date range and apply exceptions.

Visible range queries must be bounded.

## Timezone

Occurrence generation must happen with timezone-aware date logic. DST transitions must not produce accidental one-hour shifts in the intended local time.

## Required tests

- daily generation
- weekly generation
- selected weekdays
- monthly generation
- until date
- occurrence count
- exception move
- exception resize
- exception cancellation
- this-and-following split
- DST boundary behavior
- month-end behavior
