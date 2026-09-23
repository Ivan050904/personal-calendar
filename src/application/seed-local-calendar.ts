import type { Calendar, Event } from '../domain/models'
import { createId } from '../domain/ids'
import type { CalendarEntityRepository, CalendarRepository } from './repositories'
import { isoToZonedInput, zonedInputToIso } from './day-calendar'

/**
 * Ensure a local calendar exists and its timezone matches the device.
 * When the timezone changes, reinterpret existing event wall-clock times so
 * "15:00 on the form" stays 15:00 after the switch (UTC seed → real zone).
 */
export async function ensureLocalCalendar(
  calendars: CalendarRepository,
  timezone: string,
  now: () => string = () => new Date().toISOString(),
  events?: CalendarEntityRepository<Event>,
): Promise<Calendar> {
  const existing = await calendars.getLocalCalendar()
  const timestamp = now()

  if (existing === undefined) {
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

  if (existing.timezone === timezone) {
    return existing
  }

  const updated: Calendar = {
    ...existing,
    timezone,
    updatedAt: timestamp,
  }
  await calendars.put(updated)

  if (events !== undefined) {
    const listed = await events.listByCalendarId(existing.id)
    for (const event of listed) {
      if (event.deletedAt !== undefined) continue
      const fromTz = event.timezone || existing.timezone
      if (fromTz === timezone) {
        if (event.timezone !== timezone) {
          await events.put({ ...event, timezone, updatedAt: timestamp })
        }
        continue
      }
      const startAt = zonedInputToIso(isoToZonedInput(event.startAt, fromTz), timezone)
      const endAt = zonedInputToIso(isoToZonedInput(event.endAt, fromTz), timezone)
      await events.put({ ...event, startAt, endAt, timezone, updatedAt: timestamp })
    }
  }

  return updated
}
