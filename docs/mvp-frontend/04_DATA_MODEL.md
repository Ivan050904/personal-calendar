# Data Model

The canonical model is:

Calendar
├── Event
│   ├── RecurrenceRule (optional)
│   ├── EventException (0..n)
│   └── Reminder (0..n)
├── Plan
│   └── PlanTask (0..n)
├── Task
├── TaskList
│   └── TaskListItem (0..n)
└── Category

Deleted objects are represented through trash metadata/soft deletion.

## Calendar

- id: UUID
- name
- timezone
- createdAt
- updatedAt

## Event

- id: UUID
- calendarId
- title
- description
- startAt
- endAt
- timezone
- allDay
- categoryId?
- color
- recurrenceRuleId?
- createdAt
- updatedAt
- deletedAt?

Invariant: endAt > startAt for timed events.

## RecurrenceRule

- id
- frequency: daily | weekly | weekdays | monthly
- interval (default 1)
- weekdays[] for weekly/selected weekdays
- dayOfMonth for monthly
- untilDate?
- occurrenceCount?
- createdAt
- updatedAt

Do not invent complex RRULE syntax unless required. Internal representation may later map to an API format.

## EventException

- id
- eventId / recurrenceRuleId
- occurrenceKey
- type: modified | cancelled
- overrideStartAt?
- overrideEndAt?
- override fields as required by the implementation
- createdAt
- updatedAt

`occurrenceKey` must identify the original occurrence deterministically.

## Plan

- id
- calendarId
- title
- description?
- startAt
- endAt
- timezone
- color
- createdAt
- updatedAt
- deletedAt?

## PlanTask

- id
- planId
- title
- completed
- order
- createdAt
- updatedAt
- deletedAt?

## Task

- id
- calendarId
- title
- description?
- dueDate?
- recurrenceRuleId?
- completed
- createdAt
- updatedAt
- deletedAt?

No time in MVP.

Invariant: if `recurrenceRuleId` is set, `dueDate` is required. Recurrence rules are shared with events (`RecurrenceRule`); task completion uses rolling due-date semantics (ADR-015), not EventException materialization.

## TaskList

- id
- calendarId
- title
- createdAt
- updatedAt
- deletedAt?

## TaskListItem

- id
- listId
- title
- completed
- order
- createdAt
- updatedAt
- deletedAt?

## Category

- id
- calendarId
- name
- createdAt
- updatedAt
- deletedAt?

## Reminder

- id
- eventId
- offsetMinutes
- createdAt
- updatedAt

## Trash

Trash metadata must preserve:
- original entity type;
- original entity id;
- deletedAt;
- purgeAt;
- enough information to restore the object and its relationships.

The implementation may use one IndexedDB store for trash metadata or soft-delete indexes, but restoration semantics must be reliable.
