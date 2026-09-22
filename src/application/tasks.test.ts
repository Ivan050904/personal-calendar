import { describe, expect, it } from 'vitest'
import type { Calendar, Task } from '../domain/models'
import { ValidationError } from '../domain/validation'
import type { CalendarEntityRepository } from './repositories'
import { LocalTasksService } from './tasks'

class MemoryTaskRepository implements CalendarEntityRepository<Task> {
  private readonly values = new Map<string, Task>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: Task) { this.values.set(entity.id, entity) }
  async listByCalendarId(calendarId: string) {
    return (await this.list()).filter((task) => task.calendarId === calendarId)
  }
}

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  name: 'Personal Calendar',
  timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
}

describe('local tasks service', () => {
  it('creates, updates and soft-deletes a task', async () => {
    const repository = new MemoryTaskRepository()
    const service = new LocalTasksService(calendar, repository, () => '2026-09-17T00:00:00.000Z')

    const created = await service.createTask({ title: 'Buy milk', description: '2%', dueDate: '2026-09-18' })
    expect(created).toMatchObject({
      calendarId: calendar.id,
      title: 'Buy milk',
      description: '2%',
      dueDate: '2026-09-18',
      completed: false,
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    })
    expect(created.deletedAt).toBeUndefined()

    const updated = await service.updateTask(created.id, {
      title: 'Buy oat milk',
      description: '1L',
      dueDate: '2026-09-19',
    })
    expect(updated.title).toBe('Buy oat milk')
    expect(updated.description).toBe('1L')
    expect(updated.dueDate).toBe('2026-09-19')
    expect(updated.completed).toBe(false)

    await service.deleteTask(created.id)
    await expect(service.listTasksForDate('2026-09-19')).resolves.toEqual([])
    const stored = await repository.get(created.id)
    expect(stored?.deletedAt).toBe('2026-09-17T00:00:00.000Z')
  })

  it('lists undated tasks and tasks for a date', async () => {
    const service = new LocalTasksService(calendar, new MemoryTaskRepository(), () => '2026-09-17T00:00:00.000Z')

    const undated = await service.createTask({ title: 'Inbox' })
    const dated = await service.createTask({ title: 'Submit report', dueDate: '2026-09-18' })
    await service.createTask({ title: 'Other day', dueDate: '2026-09-19' })

    await expect(service.listUndatedTasks()).resolves.toEqual([undated])
    await expect(service.listTasksForDate('2026-09-18')).resolves.toEqual([dated])
    await expect(service.listTasksForDate('2026-09-20')).resolves.toEqual([])
  })

  it('moves a dated task to another date', async () => {
    const service = new LocalTasksService(calendar, new MemoryTaskRepository(), () => '2026-09-17T00:00:00.000Z')
    const created = await service.createTask({ title: 'Call bank', dueDate: '2026-09-18' })

    const moved = await service.moveTask(created.id, '2026-09-20')
    expect(moved.dueDate).toBe('2026-09-20')
    await expect(service.listTasksForDate('2026-09-18')).resolves.toEqual([])
    await expect(service.listTasksForDate('2026-09-20')).resolves.toEqual([moved])
  })

  it('rejects moving an undated task', async () => {
    const service = new LocalTasksService(calendar, new MemoryTaskRepository(), () => '2026-09-17T00:00:00.000Z')
    const created = await service.createTask({ title: 'Someday' })
    await expect(service.moveTask(created.id, '2026-09-20')).rejects.toThrow('Task has no due date')
  })

  it('toggles completed without changing other fields', async () => {
    const service = new LocalTasksService(calendar, new MemoryTaskRepository(), () => '2026-09-17T00:00:00.000Z')
    const created = await service.createTask({ title: 'Water plants', dueDate: '2026-09-18' })

    const completed = await service.toggleCompleted(created.id)
    expect(completed.completed).toBe(true)
    expect(completed.dueDate).toBe('2026-09-18')
    expect(completed.title).toBe('Water plants')

    const reopened = await service.toggleCompleted(created.id)
    expect(reopened.completed).toBe(false)
  })

  it('requires a non-empty title', async () => {
    const service = new LocalTasksService(calendar, new MemoryTaskRepository(), () => '2026-09-17T00:00:00.000Z')
    await expect(service.createTask({ title: '   ' })).rejects.toThrow(ValidationError)
  })
})
