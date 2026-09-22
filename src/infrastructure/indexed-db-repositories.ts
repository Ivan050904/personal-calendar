import type { Calendar, CalendarEntity } from '../domain/models'
import type { CalendarRepository, CalendarEntityRepository, EntityRepository, Repositories } from '../application/repositories'

export const DATABASE_NAME = 'personal-calendar'
export const DATABASE_VERSION = 1

const STORE_NAMES = [
  'calendars', 'events', 'recurrenceRules', 'eventExceptions', 'plans', 'planTasks',
  'tasks', 'lists', 'listItems', 'categories', 'reminders',
] as const

type StoreName = (typeof STORE_NAMES)[number]

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error ?? new Error('IndexedDB request failed'))
  })
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error ?? new Error('IndexedDB transaction failed'))
    transaction.onabort = () => reject(transaction.error ?? new Error('IndexedDB transaction aborted'))
  })
}

export class IndexedDbEntityRepository<T extends { id: string }> implements EntityRepository<T> {
  constructor(
    protected readonly database: IDBDatabase,
    protected readonly storeName: StoreName,
  ) {}

  async get(id: string): Promise<T | undefined> {
    const transaction = this.database.transaction(this.storeName, 'readonly')
    const result = await requestResult(transaction.objectStore(this.storeName).get(id))
    await transactionDone(transaction)
    return result as T | undefined
  }

  async list(): Promise<T[]> {
    const transaction = this.database.transaction(this.storeName, 'readonly')
    const result = await requestResult(transaction.objectStore(this.storeName).getAll())
    await transactionDone(transaction)
    return result as T[]
  }

  async put(entity: T): Promise<void> {
    const transaction = this.database.transaction(this.storeName, 'readwrite')
    await requestResult(transaction.objectStore(this.storeName).put(entity))
    await transactionDone(transaction)
  }
}

class IndexedDbCalendarEntityRepository<T extends CalendarEntity>
  extends IndexedDbEntityRepository<T>
  implements CalendarEntityRepository<T> {
  async listByCalendarId(calendarId: string): Promise<T[]> {
    const transaction = this.database.transaction(this.storeName, 'readonly')
    const result = await requestResult(transaction.objectStore(this.storeName).index('calendarId').getAll(calendarId))
    await transactionDone(transaction)
    return result as T[]
  }
}

class IndexedDbCalendarRepository
  extends IndexedDbEntityRepository<Calendar>
  implements CalendarRepository {
  async getLocalCalendar() {
    const calendars = await this.list()
    return calendars[0]
  }
}

export async function openCalendarDatabase(name = DATABASE_NAME): Promise<IDBDatabase> {
  const request = indexedDB.open(name, DATABASE_VERSION)
  request.onupgradeneeded = () => {
    const database = request.result
    for (const storeName of STORE_NAMES) {
      const store = database.createObjectStore(storeName, { keyPath: 'id' })
      if (['events', 'plans', 'tasks', 'lists', 'categories'].includes(storeName)) {
        store.createIndex('calendarId', 'calendarId', { unique: false })
      }
    }
  }
  return requestResult(request)
}

export function createIndexedDbRepositories(database: IDBDatabase): Repositories {
  return {
    calendars: new IndexedDbCalendarRepository(database, 'calendars'),
    events: new IndexedDbCalendarEntityRepository(database, 'events'),
    recurrenceRules: new IndexedDbEntityRepository(database, 'recurrenceRules'),
    eventExceptions: new IndexedDbEntityRepository(database, 'eventExceptions'),
    plans: new IndexedDbCalendarEntityRepository(database, 'plans'),
    planTasks: new IndexedDbEntityRepository(database, 'planTasks'),
    tasks: new IndexedDbCalendarEntityRepository(database, 'tasks'),
    lists: new IndexedDbCalendarEntityRepository(database, 'lists'),
    listItems: new IndexedDbEntityRepository(database, 'listItems'),
    categories: new IndexedDbCalendarEntityRepository(database, 'categories'),
    reminders: new IndexedDbEntityRepository(database, 'reminders'),
  }
}
