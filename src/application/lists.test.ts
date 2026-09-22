import { describe, expect, it } from 'vitest'
import type { Calendar, TaskList, TaskListItem } from '../domain/models'
import { ValidationError } from '../domain/validation'
import { LocalListsService } from './lists'
import type { CalendarEntityRepository, EntityRepository } from './repositories'

class MemoryRepository<T extends { id: string }> implements EntityRepository<T> {
  private readonly values = new Map<string, T>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: T) { this.values.set(entity.id, entity) }
}

class MemoryListRepository extends MemoryRepository<TaskList> implements CalendarEntityRepository<TaskList> {
  async listByCalendarId(calendarId: string) {
    return (await this.list()).filter((list) => list.calendarId === calendarId)
  }
}

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  name: 'Personal Calendar',
  timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
}

function createService(
  lists = new MemoryListRepository(),
  items = new MemoryRepository<TaskListItem>(),
  now = () => '2026-09-17T00:00:00.000Z',
) {
  return { service: new LocalListsService(calendar, lists, items, now), lists, items }
}

describe('LocalListsService', () => {
  it('creates, renames and soft-deletes a list', async () => {
    const { service } = createService()
    const created = await service.create({ title: '  Groceries  ' })
    expect(created.title).toBe('Groceries')
    expect(created.calendarId).toBe(calendar.id)

    const renamed = await service.rename(created.id, 'Shopping')
    expect(renamed.title).toBe('Shopping')

    await service.softDelete(created.id)
    await expect(service.listAll()).resolves.toEqual([])
  })

  it('adds, updates, toggles and soft-deletes list items in order', async () => {
    const { service } = createService()
    const list = await service.create({ title: 'Packing' })
    const first = await service.addItem(list.id, { title: 'Socks' })
    const second = await service.addItem(list.id, { title: 'Toothbrush' })
    expect(first.order).toBe(0)
    expect(second.order).toBe(1)
    expect(first.completed).toBe(false)

    const updated = await service.updateItem(first.id, { title: 'Wool socks' })
    expect(updated.title).toBe('Wool socks')

    const toggled = await service.toggleItem(first.id)
    expect(toggled.completed).toBe(true)

    await service.deleteItem(second.id)
    const listed = await service.listAll()
    expect(listed).toHaveLength(1)
    expect(listed[0].items.map((item) => item.title)).toEqual(['Wool socks'])
    expect(listed[0].items[0].completed).toBe(true)
  })

  it('reorders list items and returns them ordered from listAll', async () => {
    const { service } = createService()
    const list = await service.create({ title: 'Errands' })
    const a = await service.addItem(list.id, { title: 'Bank' })
    const b = await service.addItem(list.id, { title: 'Post office' })
    const c = await service.addItem(list.id, { title: 'Pharmacy' })

    await service.reorderItems(list.id, [c.id, a.id, b.id])
    const listed = await service.listAll()
    expect(listed[0].items.map((item) => item.title)).toEqual(['Pharmacy', 'Bank', 'Post office'])
    expect(listed[0].items.map((item) => item.order)).toEqual([0, 1, 2])
  })

  it('rejects empty titles and incomplete reorder payloads', async () => {
    const { service } = createService()
    await expect(service.create({ title: '   ' })).rejects.toBeInstanceOf(ValidationError)

    const list = await service.create({ title: 'Todo' })
    const item = await service.addItem(list.id, { title: 'One' })
    await expect(service.addItem(list.id, { title: '' })).rejects.toBeInstanceOf(ValidationError)
    await expect(service.reorderItems(list.id, [])).rejects.toBeInstanceOf(ValidationError)
    await expect(service.reorderItems(list.id, [item.id, item.id])).rejects.toBeInstanceOf(ValidationError)
  })

  it('hides soft-deleted lists from listAll', async () => {
    const { service } = createService()
    const keep = await service.create({ title: 'Keep' })
    await service.addItem(keep.id, { title: 'Item' })
    const gone = await service.create({ title: 'Gone' })
    await service.addItem(gone.id, { title: 'Hidden' })
    await service.softDelete(gone.id)

    const listed = await service.listAll()
    expect(listed.map((entry) => entry.list.title)).toEqual(['Keep'])
    expect(listed[0].items).toHaveLength(1)
  })
})
