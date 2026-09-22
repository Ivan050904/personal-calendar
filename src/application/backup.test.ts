import { describe, expect, it } from 'vitest'
import type { Calendar, Event } from '../domain/models'
import type { CalendarEntity } from '../domain/models'
import type { CalendarEntityRepository, CalendarRepository, EntityRepository, Repositories } from './repositories'
import { BACKUP_SCHEMA_VERSION, exportBackup, importBackupReplace, validateBackup } from './backup'

class MemoryRepo<T extends { id: string }> implements EntityRepository<T> {
  private readonly values = new Map<string, T>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: T) { this.values.set(entity.id, entity) }
}

class MemoryCalendarRepo extends MemoryRepo<Calendar> implements CalendarRepository {
  async getLocalCalendar() { return (await this.list())[0] }
}

class MemoryCalendarEntityRepo<T extends CalendarEntity> extends MemoryRepo<T> implements CalendarEntityRepository<T> {
  async listByCalendarId(calendarId: string) { return (await this.list()).filter((item) => item.calendarId === calendarId) }
}

function emptyRepos(): Repositories {
  return {
    calendars: new MemoryCalendarRepo(),
    events: new MemoryCalendarEntityRepo(),
    recurrenceRules: new MemoryRepo(),
    eventExceptions: new MemoryRepo(),
    plans: new MemoryCalendarEntityRepo(),
    planTasks: new MemoryRepo(),
    tasks: new MemoryCalendarEntityRepo(),
    lists: new MemoryCalendarEntityRepo(),
    listItems: new MemoryRepo(),
    categories: new MemoryCalendarEntityRepo(),
    reminders: new MemoryRepo(),
  }
}

describe('backup', () => {
  it('exports schema-versioned envelope and rejects bad imports', async () => {
    const repos = emptyRepos()
    const calendar: Calendar = {
      id: '1d76fb58-104a-4ffd-834a-e0cb9644af74', name: 'Personal', timezone: 'UTC',
      createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
    }
    const event: Event = {
      id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: calendar.id, title: 'A', description: '',
      startAt: '2026-09-17T09:00:00.000Z', endAt: '2026-09-17T10:00:00.000Z', timezone: 'UTC',
      allDay: false, color: '#000', createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
    }
    await repos.calendars.put(calendar)
    await repos.events.put(event)
    const backup = await exportBackup(repos, '2026-09-18T00:00:00.000Z')
    expect(backup.schemaVersion).toBe(BACKUP_SCHEMA_VERSION)
    expect(backup.events).toHaveLength(1)
    expect(() => validateBackup({ schemaVersion: 999 })).toThrow('unsupported schemaVersion')

    const target = emptyRepos()
    await importBackupReplace(target, backup)
    await expect(target.events.list()).resolves.toEqual([event])
  })
})
