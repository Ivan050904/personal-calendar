import { expect, it, vi, afterEach } from 'vitest'
import type { Calendar } from '../domain/models'
import { createApiRepositories } from './api-repositories'

afterEach(() => vi.unstubAllGlobals())
it('API calendar reads the server occurrence and never expands raw entities', async () => {
  const fetch = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ items: [{ id: 'e::2026-10-08T09:00', entity_id: 'e', calendar_id: 'c', kind: 'event', title: 'Projected', description: '', timezone: 'UTC', all_day: false, start_at: '2026-10-08T09:00:00Z', end_at: '2026-10-08T10:00:00Z', revision: 2, color: '#000', location: null }], complete: true, next_cursor: null }) }))
  vi.stubGlobal('fetch', fetch)
  const { ApiDayCalendarService } = await import('./api-calendar-services')
  const calendar: Calendar = { id: 'c', name: 'Own', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const services = new ApiDayCalendarService(calendar)
  const items = await services.listEvents('2026-10-08')
  expect(items[0]?.id).toBe('e::2026-10-08T09:00')
  expect(items[0]?.revision).toBe(2)
  expect(fetch).toHaveBeenCalledTimes(1)
})
it('task completion sends authoritative complete command with original due', async () => {
  const requests: Array<Record<string, unknown>> = []
  const row = { id: 't', calendar_id: 'c', kind: 'task', title: 'Task', description: '', timezone: 'UTC', revision: 4, due_date: '2026-10-01', completed: false, recurrence: null, created_at: '', updated_at: '', deleted_at: null }
  vi.stubGlobal('fetch', async (path: string, init?: RequestInit) => ({ ok: true, status: 200, json: async () => {
    if (path.endsWith('/commands')) { requests.push(JSON.parse(String(init?.body))); return { entity: { ...row, due_date: '2026-10-09' }, confirmation: null } }
    return row
  } }))
  const { ApiTasksService } = await import('./api-calendar-services')
  const calendar: Calendar = { id: 'c', name: 'Own', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const repos = createApiRepositories()
  const service = new ApiTasksService(calendar, repos.tasks, repos.recurrenceRules)
  expect((await service.toggleCompleted('t', { revision: 4, dueDate: '2026-10-01', completed: false })).dueDate).toBe('2026-10-09')
  expect(requests[0]).toMatchObject({ operation: 'complete', expected_revision: 4, occurrence_key: '2026-10-01' })
})

it.each(['task', 'plan'] as const)('rejects a stale %s draft instead of rebasing it before save', async (kind) => {
  let title = 'Saved in another tab'
  const row = { id: 'item', calendar_id: 'c', kind, title, description: '', timezone: 'UTC', revision: 5, due_date: '2026-10-02', completed: false, recurrence: null, start_at: '2026-10-02T09:00:00Z', end_at: '2026-10-02T10:00:00Z', all_day: false, color: '#000', created_at: '', updated_at: '', deleted_at: null }
  vi.stubGlobal('fetch', async (path: string, init?: RequestInit) => {
    if (!path.endsWith('/commands')) return new Response(JSON.stringify(row))
    const body = JSON.parse(String(init?.body))
    if (body.expected_revision !== 5) return new Response(JSON.stringify({ error: { message: 'Revision changed' } }), { status: 409 })
    title = body.payload.title
    return new Response(JSON.stringify({ entity: { ...row, title }, confirmation: null }))
  })
  const { ApiTasksService, ApiPlansService } = await import('./api-calendar-services')
  const calendar: Calendar = { id: 'c', name: 'Own', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const repos = createApiRepositories()
  const draft = { title: 'Stale draft', expectedRevision: 4, dueDate: '2026-10-01', startAt: row.start_at, endAt: row.end_at, color: '#000' }
  const save = kind === 'task'
    ? new ApiTasksService(calendar, repos.tasks, repos.recurrenceRules).updateTask('item', draft)
    : new ApiPlansService(calendar, repos.plans, repos.planTasks).updatePlan('item', draft)
  await expect(save).rejects.toThrow()
  expect(title).toBe('Saved in another tab')
})

it('cannot complete the next rolling task from a stale displayed occurrence', async () => {
  let completed = false
  const row = { id: 't', calendar_id: 'c', kind: 'task', title: 'Daily', description: '', timezone: 'UTC', revision: 5, due_date: '2026-10-02', completed: false, recurrence: { frequency: 'daily', interval: 1 }, created_at: '', updated_at: '', deleted_at: null }
  vi.stubGlobal('fetch', async (path: string, init?: RequestInit) => {
    if (!path.endsWith('/commands')) return new Response(JSON.stringify(row))
    const body = JSON.parse(String(init?.body))
    if (body.expected_revision !== 5 || body.occurrence_key !== '2026-10-02') return new Response(JSON.stringify({ error: { message: 'Revision changed' } }), { status: 409 })
    completed = true
    return new Response(JSON.stringify({ entity: { ...row, completed }, confirmation: null }))
  })
  const { ApiTasksService } = await import('./api-calendar-services')
  const calendar: Calendar = { id: 'c', name: 'Own', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const repos = createApiRepositories()
  const service = new ApiTasksService(calendar, repos.tasks, repos.recurrenceRules)
  await expect(service.toggleCompleted('t', { revision: 4, dueDate: '2026-10-01', completed: false })).rejects.toThrow()
  expect(completed).toBe(false)
})
