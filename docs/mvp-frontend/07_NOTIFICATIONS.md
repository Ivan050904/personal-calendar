# Notifications

Events may have multiple reminders.

Supported offsets:
- 5 min
- 15 min
- 30 min
- 60 min
- 1440 min

Browser notification permission is requested only when needed and never assumed to be granted.

Settings:
- notifications enabled/disabled.

The system must handle denied permission gracefully.

Reminder scheduling must account for:
- timezone;
- browser lifecycle limitations;
- recurring event occurrences;
- cancelled/modified occurrences.

Do not claim guaranteed delivery from a normal browser tab. MVP should implement the best reliable browser/PWA mechanism available in the chosen stack and document limitations.

Reminder data is persisted independently from transient UI state.
