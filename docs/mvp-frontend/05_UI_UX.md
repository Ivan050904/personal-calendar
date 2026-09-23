# UI/UX

## General

Simple modern calendar. Both light and dark themes.

Do not overload the interface.

Primary navigation:
- Calendar
- Tasks
- Lists
- Trash
- Settings

Calendar sub-navigation:
- Day
- Week
- Month

## Startup

Open Today by default.

## Day

Classic calendar:
- time column on the left;
- events/plans on the right;
- timed items positioned according to real start/end;
- untimed dated tasks appear in a separate "Tasks for today" area below/alongside the timeline;
- click empty time area opens create form with date/time prefilled.

## Week

Classic grid:
- days across top;
- time on left;
- events/plans positioned in day columns;
- real duration represented visually.

## Month

Classic month grid:
- Monday first;
- show event summaries/indicators;
- click a date opens that day;
- avoid overcrowding; details are available through interaction.

## Drag and drop

Desktop:
- drag event to change start;
- resize to change end;
- drag across day columns to change date.

Mobile:
- touch-friendly manipulation;
- day navigation by horizontal swipe;
- avoid accidental drag when tapping.

For recurring events, direct manipulation of one occurrence affects only that occurrence.

## Forms

Event form:
- title
- date
- start
- end
- recurrence
- recurrence weekdays where relevant
- recurrence end
- category
- color
- notes
- reminders
- save/cancel

Plan form:
- title
- date
- start
- end
- color
- checklist with add/reorder/delete task

Task form:
- title
- optional date
- optional recurrence (never / daily / weekly / monthly) when a date is set; recurrence requires a due date
- save

Recurring tasks show a short repeat label on the row (e.g. «каждый месяц»).

List form:
- list title
- add/reorder/check items

## Quick input

MVP must always have reliable standard forms.

Optional quick natural-language input can parse simple phrases such as:
"завтра в 15:00 стоматолог".

Parser must never silently create a wrong event. If confidence/parse is insufficient, show the parsed form for confirmation or fall back to manual fields.

## Accessibility

Keyboard navigation, visible focus, semantic controls, sufficient contrast, labels for form fields, touch targets suitable for mobile.

## Theme

Light/dark mode must not change data semantics.
