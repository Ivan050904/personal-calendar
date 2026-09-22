# AI Structured Actions

Allowed intent:
- CREATE
- UPDATE
- DELETE

Entities:
- event
- plan
- task
- list

CREATE_EVENT: title, date, start, end/duration, timezone, recurrence, category, color, notes, reminders.

CREATE_PLAN: title, date, start, end, timezone, color, description, ordered PlanTasks. PlanTask time не поддерживается.

CREATE_TASK: title, dueDate optional, description optional. Time не поддерживается.

CREATE_LIST: title + ordered items.

UPDATE: entityType + TargetSelector/resolved target + changed fields + recurrenceScope when needed.

DELETE: entityType + TargetSelector/resolved target + recurrenceScope when needed.

Recurrence scopes:
occurrence
this_and_following
entire_series

Не создавать вторую recurrence system специально для AI.
