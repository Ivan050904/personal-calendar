# Architecture

## Principle

Domain/application logic не должна зависеть напрямую от IndexedDB или HTTP.

Основная схема:

UI
→ Application services/use cases
→ Domain
→ Repository interfaces
→ Infrastructure adapter

MVP:
UI → Application → Repository → IndexedDB

Future:
UI → Application → Repository → HTTP API → unified server DB

## Recommended layers

### Presentation
React components, pages, calendar views, forms, interactions.

### Application
Use cases:
- CreateEvent
- UpdateEvent
- DeleteEvent
- RestoreFromTrash
- MoveEvent
- ResizeEvent
- CreatePlan
- ManagePlanTasks
- CreateTask
- MoveTask
- ManageLists
- Search
- Filter
- CreateReminder
- ExportData
- ImportData
- NavigateCalendar

### Domain
Pure models and rules:
- Event
- RecurrenceRule
- EventException
- Plan
- PlanTask
- Task
- TaskList
- TaskListItem
- Category
- Reminder
- TrashItem
- Calendar

### Infrastructure
- IndexedDB repository
- notification adapter
- import/export adapter
- future API repository

## Calendar aggregate

A Calendar entity is used even without an account.

Future:
User → Calendar → entities

MVP:
Local device → one local Calendar

This is deliberate so account integration later is a persistence/authentication concern, not a rewrite of domain logic.

## IDs

Use stable unique IDs generated client-side. Do not rely on database auto-increment IDs, because local-to-server migration and offline work need stable identifiers.

## Soft deletion

Entities use deletedAt / trash metadata rather than immediate destructive deletion.

## Dates

Store absolute date-time information in a form that preserves the intended timezone. Date-only values such as task dueDate must not be accidentally shifted by UTC conversion.

## Persistence

Use IndexedDB for MVP. A repository abstraction must hide IndexedDB implementation details from the application/domain.

Do not use localStorage as the primary database.

## Future synchronization

Design repositories so a future ApiRepository can implement the same application-facing contracts.

Future sync must preserve IDs and timestamps and eventually support conflict handling. Do not implement speculative sync logic in MVP.

## State

UI state and persisted domain state must be separated. Avoid putting the whole domain directly into arbitrary component state.

## Testing

Domain recurrence/date logic should be heavily unit tested independently of UI and browser storage.
