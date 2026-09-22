import { describe, expect, it } from 'vitest'
import type { Calendar, Plan, PlanTask } from '../domain/models'
import { ValidationError } from '../domain/validation'
import { LocalPlansService, planProgress } from './plans'
import type { CalendarEntityRepository, EntityRepository } from './repositories'

class MemoryRepository<T extends { id: string }> implements EntityRepository<T> {
  private readonly values = new Map<string, T>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: T) { this.values.set(entity.id, entity) }
}

class MemoryPlanRepository extends MemoryRepository<Plan> implements CalendarEntityRepository<Plan> {
  async listByCalendarId(calendarId: string) {
    return (await this.list()).filter((plan) => plan.calendarId === calendarId)
  }
}

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  name: 'Personal Calendar',
  timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
}

const draft = {
  title: 'Project kickoff',
  description: 'Prep checklist',
  startAt: '2026-09-17T09:00:00.000Z',
  endAt: '2026-09-17T11:00:00.000Z',
  color: '#0f766e',
}

function createService(now = '2026-09-17T00:00:00.000Z') {
  return new LocalPlansService(calendar, new MemoryPlanRepository(), new MemoryRepository<PlanTask>(), () => now)
}

describe('plans service', () => {
  it('creates, updates and soft-deletes a plan', async () => {
    const service = createService()
    const created = await service.createPlan(draft)

    await expect(service.listPlansInRange('2026-09-17', '2026-09-17')).resolves.toEqual([created])
    expect(created.timezone).toBe(calendar.timezone)
    expect(created.calendarId).toBe(calendar.id)

    const updated = await service.updatePlan(created.id, { ...draft, title: 'Kickoff workshop' })
    expect(updated.title).toBe('Kickoff workshop')

    await service.deletePlan(created.id)
    await expect(service.listPlansInRange('2026-09-17', '2026-09-17')).resolves.toEqual([])
  })

  it('lists plans that overlap a date range and skips deleted ones', async () => {
    const service = createService()
    const inRange = await service.createPlan(draft)
    await service.createPlan({
      ...draft,
      title: 'Later',
      startAt: '2026-09-20T09:00:00.000Z',
      endAt: '2026-09-20T10:00:00.000Z',
    })
    const spanning = await service.createPlan({
      ...draft,
      title: 'Overnight',
      startAt: '2026-09-16T22:00:00.000Z',
      endAt: '2026-09-18T02:00:00.000Z',
    })

    await expect(service.listPlansInRange('2026-09-17', '2026-09-17')).resolves.toEqual([spanning, inRange])
  })

  it('manages checklist items and progress', async () => {
    const service = createService()
    const plan = await service.createPlan(draft)

    const first = await service.addTask(plan.id, 'Write agenda')
    const second = await service.addTask(plan.id, 'Book room')
    expect(first.completed).toBe(false)
    expect(second.order).toBeGreaterThan(first.order)

    await expect(service.progress(plan.id)).resolves.toEqual({ completed: 0, total: 2, percentage: 0 })

    const toggled = await service.toggleTask(first.id)
    expect(toggled.completed).toBe(true)
    await expect(service.progress(plan.id)).resolves.toEqual({ completed: 1, total: 2, percentage: 50 })

    const renamed = await service.updateTask(second.id, 'Book conference room')
    expect(renamed.title).toBe('Book conference room')

    await service.deleteTask(second.id)
    await expect(service.listTasks(plan.id)).resolves.toEqual([toggled])
    await expect(service.progress(plan.id)).resolves.toEqual({ completed: 1, total: 1, percentage: 100 })
  })

  it('reorders checklist items', async () => {
    const service = createService()
    const plan = await service.createPlan(draft)
    const a = await service.addTask(plan.id, 'A')
    const b = await service.addTask(plan.id, 'B')
    const c = await service.addTask(plan.id, 'C')

    const reordered = await service.reorderTasks(plan.id, [c.id, a.id, b.id])
    expect(reordered.map((task) => task.id)).toEqual([c.id, a.id, b.id])
    expect(reordered.map((task) => task.order)).toEqual([0, 1, 2])
    await expect(service.listTasks(plan.id)).resolves.toEqual(reordered)
  })

  it('rejects empty checklist titles and incomplete reorder payloads', async () => {
    const service = createService()
    const plan = await service.createPlan(draft)
    const task = await service.addTask(plan.id, 'Keep')

    await expect(service.addTask(plan.id, '   ')).rejects.toBeInstanceOf(ValidationError)
    await expect(service.reorderTasks(plan.id, [])).rejects.toBeInstanceOf(ValidationError)
    await expect(service.reorderTasks(plan.id, [task.id, 'missing'])).rejects.toBeInstanceOf(ValidationError)
  })

  it('computes progress as completed over total active tasks', () => {
    expect(planProgress([
      { id: '1', planId: 'p', title: 'A', completed: true, order: 0, createdAt: '', updatedAt: '' },
      { id: '2', planId: 'p', title: 'B', completed: false, order: 1, createdAt: '', updatedAt: '' },
      { id: '3', planId: 'p', title: 'C', completed: true, order: 2, createdAt: '', updatedAt: '', deletedAt: 'x' },
    ])).toEqual({ completed: 1, total: 2, percentage: 50 })
  })
})
