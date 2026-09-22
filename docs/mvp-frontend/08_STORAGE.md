# Storage

## MVP

IndexedDB is the primary persistence layer.

No account required.

Do not use localStorage as the database.

Repository interfaces hide IndexedDB.

## Backup

Export to JSON.

The export must include a schemaVersion.

Example conceptual envelope:

{
  "schemaVersion": 1,
  "exportedAt": "...",
  "calendar": {...},
  "events": [...],
  "recurrenceRules": [...],
  "eventExceptions": [...],
  "plans": [...],
  "planTasks": [...],
  "tasks": [...],
  "lists": [...],
  "listItems": [...],
  "categories": [...],
  "reminders": [...]
}

Import must:
- validate schemaVersion;
- validate IDs and references;
- not partially corrupt existing data;
- report validation errors clearly.

Prefer import modes:
- replace current local dataset;
- merge, if safely implementable.

If merge is not implemented in MVP, explicitly label import as replacement and require confirmation.

## Future

ApiRepository will use same domain/application contracts.

Future migration:
local Calendar → authenticated account → API upload → server Calendar.

Stable IDs are mandatory.
