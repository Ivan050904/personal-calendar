# Future API Contract

This document describes compatibility goals, not an MVP server implementation.

The future server owns the authoritative account/calendar data.

Candidate resources:
- calendars
- events
- recurrence-rules
- event-exceptions
- plans
- plan-tasks
- tasks
- lists
- list-items
- categories
- reminders
- trash metadata

All resources use stable IDs.

API layer must not leak transport details into domain logic.

Future sync needs:
- createdAt
- updatedAt
- deletedAt/tombstone
- stable IDs
- version/revision or equivalent conflict metadata.

Conflict resolution policy is intentionally NOT finalized in MVP. Agent must not invent one. Before implementing sync, create a dedicated design decision.
