import { describe, expect, it } from 'vitest'
import type { Calendar, Category, Event, Plan, Task, TaskList } from '../domain/models'
import type { CalendarEntityRepository } from './repositories'
import { filterEventsByCategory, LocalCategoriesService, searchEntities } from './categories'

class MemoryCategoryRepository implements CalendarEntityRepository<Category> {
  private readonly values = new Map<string, Category>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: Category) { this.values.set(entity.id, entity) }
  async listByCalendarId(calendarId: string) { return (await this.list()).filter((item) => item.calendarId === calendarId) }
}

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74', name: 'Personal', timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
}

describe('categories and search', () => {
  it('creates, renames and soft-deletes categories', async () => {
    const service = new LocalCategoriesService(calendar, new MemoryCategoryRepository(), () => '2026-09-17T00:00:00.000Z')
    const created = await service.create({ name: 'Work' })
    expect(created.name).toBe('Work')
    await service.rename(created.id, 'Office')
    await expect(service.list()).resolves.toEqual([expect.objectContaining({ name: 'Office' })])
    await service.softDelete(created.id)
    await expect(service.list()).resolves.toEqual([])
  })

  it('filters events by category and searches across entity titles', () => {
    const events: Event[] = [
      {
        id: 'e1', calendarId: calendar.id, title: 'Dentist', description: '', startAt: '2026-09-17T09:00:00.000Z',
        endAt: '2026-09-17T10:00:00.000Z', timezone: 'UTC', allDay: false, color: '#000', categoryId: 'c1',
        createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
      },
      {
        id: 'e2', calendarId: calendar.id, title: 'Run', description: '', startAt: '2026-09-17T11:00:00.000Z',
        endAt: '2026-09-17T12:00:00.000Z', timezone: 'UTC', allDay: false, color: '#000',
        createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
      },
    ]
    expect(filterEventsByCategory(events, 'c1')).toHaveLength(1)
    const plans: Plan[] = [{
      id: 'p1', calendarId: calendar.id, title: 'Trip plan', startAt: '2026-09-17T09:00:00.000Z',
      endAt: '2026-09-17T18:00:00.000Z', timezone: 'UTC', color: '#000',
      createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
    }]
    const tasks: Task[] = [{
      id: 't1', calendarId: calendar.id, title: 'Buy tickets', completed: false,
      createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
    }]
    const lists: TaskList[] = [{
      id: 'l1', calendarId: calendar.id, title: 'Shopping',
      createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
    }]
    expect(searchEntities('tick', { events, plans, tasks, lists }).map((hit) => hit.type)).toEqual(['task'])
    expect(searchEntities('plan', { events, plans, tasks, lists }).map((hit) => hit.id)).toEqual(['p1'])
  })
})
