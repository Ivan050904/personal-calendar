import 'fake-indexeddb/auto'
import { afterEach, describe, expect, it } from 'vitest'
import { ensureLocalCalendar } from '../application/seed-local-calendar'
import type { Task } from '../domain/models'
import { createIndexedDbRepositories, openCalendarDatabase } from './indexed-db-repositories'

const databases: IDBDatabase[] = []

afterEach(async () => {
  await Promise.all(databases.splice(0).map((database) => new Promise<void>((resolve, reject) => {
    const name = database.name
    database.close()
    const request = indexedDB.deleteDatabase(name)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })))
})

async function repositoriesForTest() {
  const name = `calendar-test-${crypto.randomUUID()}`
  const database = await openCalendarDatabase(name)
  databases.push(database)
  return createIndexedDbRepositories(database)
}

describe('IndexedDB repositories', () => {
  it('persists entities and filters calendar-scoped entities', async () => {
    const repositories = await repositoriesForTest()
    const firstCalendar = '1d76fb58-104a-4ffd-834a-e0cb9644af74'
    const task: Task = {
      id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34',
      calendarId: firstCalendar,
      title: 'Read specifications',
      completed: false,
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    }
    await repositories.tasks.put(task)

    await expect(repositories.tasks.get(task.id)).resolves.toEqual(task)
    await expect(repositories.tasks.listByCalendarId(firstCalendar)).resolves.toEqual([task])
    await expect(repositories.tasks.listByCalendarId('another-calendar')).resolves.toEqual([])
  })

  it('creates one local calendar without categories', async () => {
    const repositories = await repositoriesForTest()

    const calendar = await ensureLocalCalendar(
      repositories.calendars,
      'Asia/Vladivostok',
      () => '2026-09-17T00:00:00.000Z',
    )
    const repeated = await ensureLocalCalendar(repositories.calendars, 'Asia/Tokyo')

    expect(calendar.name).toBe('Personal Calendar')
    expect(repeated).toEqual(calendar)
    await expect(repositories.categories.list()).resolves.toEqual([])
  })
})
