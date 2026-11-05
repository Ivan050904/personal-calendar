import type { Calendar, Event } from '../domain/models'
import { createId } from '../domain/ids'
import type { CalendarEntityRepository, CalendarRepository } from './repositories'

/** Opening on another device never rewrites the authoritative timezone or instants. */
export async function ensureLocalCalendar(
  calendars: CalendarRepository,
  timezone: string,
  now: () => string = () => new Date().toISOString(),
  _events?: CalendarEntityRepository<Event>,
): Promise<Calendar> {
  void _events // Retained positional argument for existing callers; opening never writes events.
  const existing = await calendars.getLocalCalendar()
  if (existing !== undefined) return existing
  const timestamp = now()
  const calendar: Calendar = { id: createId(), name: 'Personal Calendar', timezone, createdAt: timestamp, updatedAt: timestamp }
  await calendars.put(calendar)
  return calendar
}
