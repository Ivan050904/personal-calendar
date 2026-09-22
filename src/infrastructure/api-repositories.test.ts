import { describe, expect, it, vi, afterEach } from 'vitest'
import { createApiRepositories, shouldUseApiRepository } from './api-repositories'

describe('api repositories', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('builds repository bag with expected collections', () => {
    const repos = createApiRepositories('http://127.0.0.1:8000/api')
    expect(repos.calendars).toBeDefined()
    expect(repos.events).toBeDefined()
    expect(repos.tasks).toBeDefined()
    expect(repos.lists).toBeDefined()
  })

  it('defaults to API/MySQL unless VITE_USE_API is explicitly false', () => {
    expect(shouldUseApiRepository()).toBe(true)
  })

  it('normalizes JSON null to undefined so active filters keep API tasks', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => ([
        {
          id: 't1',
          calendarId: 'c1',
          title: 'Помыть полы',
          dueDate: '2026-09-22',
          completed: false,
          deletedAt: null,
          createdAt: '2026-09-22T00:00:00',
          updatedAt: '2026-09-22T00:00:00',
        },
      ]),
    })))

    const repos = createApiRepositories('/api')
    const tasks = await repos.tasks.listByCalendarId('c1')
    expect(tasks).toHaveLength(1)
    expect(tasks[0]?.deletedAt).toBeUndefined()
    expect(tasks[0]?.title).toBe('Помыть полы')
  })
})
