import type { Calendar } from '../domain/models'
import { createId } from '../domain/ids'
import type { CalendarRepository } from './repositories'

export async function ensureLocalCalendar(
  calendars: CalendarRepository,
  timezone: string,
  now: () => string = () => new Date().toISOString(),
): Promise<Calendar> {
  const existing = await calendars.getLocalCalendar()
  if (existing !== undefined) {
    return existing
  }

  const timestamp = now()
  const calendar: Calendar = {
    id: createId(),
    name: 'Personal Calendar',
    timezone,
    createdAt: timestamp,
    updatedAt: timestamp,
  }
  await calendars.put(calendar)
  return calendar
}
