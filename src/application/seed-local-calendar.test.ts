import { describe, expect, it, vi } from 'vitest'
import { ensureLocalCalendar } from './seed-local-calendar'
import type { Calendar, Event } from '../domain/models'
import type { CalendarEntityRepository, CalendarRepository } from './repositories'

class MemoryCalendarRepo implements CalendarRepository {
  private value: Calendar | undefined
  async get() { return this.value }
  async list() { return this.value ? [this.value] : [] }
  async put(entity: Calendar) { this.value = entity }
  async getLocalCalendar() { return this.value }
}

class MemoryEventRepo implements CalendarEntityRepository<Event> {
  private readonly values = new Map<string, Event>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: Event) { this.values.set(entity.id, entity) }
  async listByCalendarId(calendarId: string) {
    return [...this.values.values()].filter((event) => event.calendarId === calendarId)
  }
}

describe('ensureLocalCalendar timezone sync', () => {
  it('preserves authoritative zone and instants when another device opens the calendar', async () => {
    const calendars = new MemoryCalendarRepo()
    const events = new MemoryEventRepo()
    const calendar = await ensureLocalCalendar(calendars, 'UTC', () => '2026-09-25T00:00:00.000Z')
    await events.put({
      id: 'e1',
      calendarId: calendar.id,
      title: 'Physical',
      description: '',
      startAt: '2026-09-25T15:00:00.000Z',
      endAt: '2026-09-25T16:00:00.000Z',
      timezone: 'UTC',
      allDay: false,
      color: '#000',
      createdAt: '2026-09-25T00:00:00.000Z',
      updatedAt: '2026-09-25T00:00:00.000Z',
    })

    const calendarPut = vi.spyOn(calendars, 'put')
    const eventPut = vi.spyOn(events, 'put')
    const synced = await ensureLocalCalendar(
      calendars,
      'Asia/Vladivostok',
      () => '2026-09-25T01:00:00.000Z',
      events,
    )
    expect(synced.timezone).toBe('UTC')
    expect(calendarPut).not.toHaveBeenCalled()
    expect(eventPut).not.toHaveBeenCalled()

    const event = await events.get('e1')
    expect(event?.timezone).toBe('UTC')
    expect(event?.startAt).toBe('2026-09-25T15:00:00.000Z')
    expect(event?.endAt).toBe('2026-09-25T16:00:00.000Z')
  })
})
