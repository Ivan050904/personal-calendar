import { describe, expect, it } from 'vitest'
import { isoToZonedInput, LocalDayCalendarService, overlaps, zonedInputToIso } from './day-calendar'
import type { Calendar, Event, EventException, RecurrenceRule } from '../domain/models'
import type { CalendarEntityRepository, EntityRepository } from './repositories'

class MemoryRepository<T extends { id: string }> implements EntityRepository<T> {
  private readonly values = new Map<string, T>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: T) { this.values.set(entity.id, entity) }
}

class MemoryEventRepository extends MemoryRepository<Event> implements CalendarEntityRepository<Event> {
  async listByCalendarId(calendarId: string) { return (await this.list()).filter((event) => event.calendarId === calendarId) }
}

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74', name: 'Personal Calendar', timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
}

describe('day calendar service', () => {
  it('preserves the intended local time when converting a form value', () => {
    const stored = zonedInputToIso('2026-09-17T09:00', 'Asia/Vladivostok')
    expect(stored).toBe('2026-09-16T23:00:00.000Z')
    expect(isoToZonedInput(stored, 'Asia/Vladivostok')).toBe('2026-09-17T09:00')
  })

  it('creates, updates and soft-deletes an event', async () => {
    const service = new LocalDayCalendarService(calendar, new MemoryEventRepository(), new MemoryRepository<RecurrenceRule>(), new MemoryRepository<EventException>(), () => '2026-09-17T00:00:00.000Z')
    const draft = { title: 'Dentist', description: 'Bring card', startAt: '2026-09-17T09:00:00.000Z', endAt: '2026-09-17T10:00:00.000Z', color: '#2563eb' }
    const created = await service.createEvent(draft)

    await expect(service.listEvents('2026-09-17')).resolves.toEqual([created])
    const updated = await service.updateEvent(created.id, { ...draft, title: 'Dentist appointment' })
    expect(updated.title).toBe('Dentist appointment')

    await service.deleteEvent(created.id)
    await expect(service.listEvents('2026-09-17')).resolves.toEqual([])
  })

  it('moves, resizes and detects overlaps without preventing updates', async () => {
    const service = new LocalDayCalendarService(calendar, new MemoryEventRepository())
    const first = await service.createEvent({ title: 'A', description: '', startAt: '2026-09-17T09:00:00.000Z', endAt: '2026-09-17T10:00:00.000Z', color: '#000' })
    const moved = await service.moveEvent(first.id, '2026-09-18T11:00:00.000Z')
    expect(moved.endAt).toBe('2026-09-18T12:00:00.000Z')
    const resized = await service.resizeEvent(first.id, '2026-09-18T13:00:00.000Z')
    expect(resized.endAt).toBe('2026-09-18T13:00:00.000Z')
    expect(overlaps(resized, [{ ...resized, id: 'other', startAt: '2026-09-18T12:00:00.000Z', endAt: '2026-09-18T14:00:00.000Z' }])).toBe(true)
  })

  it('creates a recurring event and expands occurrences in the visible range', async () => {
    const service = new LocalDayCalendarService(
      calendar,
      new MemoryEventRepository(),
      new MemoryRepository<RecurrenceRule>(),
      new MemoryRepository<EventException>(),
      () => '2026-09-17T00:00:00.000Z',
    )
    await service.createEvent({
      title: 'Standup',
      description: '',
      startAt: '2026-09-17T09:00:00.000Z',
      endAt: '2026-09-17T09:30:00.000Z',
      color: '#2563eb',
      recurrence: { frequency: 'daily', interval: 1, weekdays: [], occurrenceCount: 3 },
    })
    const listed = await service.listEventsInRange('2026-09-17', '2026-09-20')
    expect(listed).toHaveLength(3)
    expect(listed.map((event) => event.startAt)).toEqual([
      '2026-09-17T09:00:00.000Z',
      '2026-09-18T09:00:00.000Z',
      '2026-09-19T09:00:00.000Z',
    ])
  })

  it('cancels a single occurrence without deleting the series', async () => {
    const service = new LocalDayCalendarService(
      calendar,
      new MemoryEventRepository(),
      new MemoryRepository<RecurrenceRule>(),
      new MemoryRepository<EventException>(),
      () => '2026-09-17T00:00:00.000Z',
    )
    const created = await service.createEvent({
      title: 'Standup',
      description: '',
      startAt: '2026-09-17T09:00:00.000Z',
      endAt: '2026-09-17T09:30:00.000Z',
      color: '#2563eb',
      recurrence: { frequency: 'daily', interval: 1, weekdays: [], occurrenceCount: 3 },
    })
    const secondId = `${created.id}::2026-09-18T09:00`
    await service.deleteEvent(secondId, 'this')
    const listed = await service.listEventsInRange('2026-09-17', '2026-09-20')
    expect(listed.map((event) => event.startAt)).toEqual([
      '2026-09-17T09:00:00.000Z',
      '2026-09-19T09:00:00.000Z',
    ])
  })
})
