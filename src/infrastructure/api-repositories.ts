import type { Calendar, CalendarEntity } from '../domain/models'
import type {
  CalendarEntityRepository,
  CalendarRepository,
  EntityRepository,
  Repositories,
} from '../application/repositories'

type StoreName =
  | 'calendars'
  | 'events'
  | 'recurrenceRules'
  | 'eventExceptions'
  | 'plans'
  | 'planTasks'
  | 'tasks'
  | 'lists'
  | 'listItems'
  | 'categories'
  | 'reminders'

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) {
    let message = `API ${response.status}`
    try {
      const body = (await response.json()) as { error?: { message?: string } }
      message = body.error?.message ?? message
    } catch {
      /* ignore */
    }
    throw new Error(message)
  }
  if (response.status === 204) {
    return undefined as T
  }
  // MySQL/JSON uses null; domain filters use undefined (e.g. deletedAt, dueDate).
  return stripJsonNulls(await response.json()) as T
}

function stripJsonNulls(value: unknown): unknown {
  if (value === null) return undefined
  if (Array.isArray(value)) return value.map(stripJsonNulls)
  if (typeof value === 'object' && value !== undefined) {
    const out: Record<string, unknown> = {}
    for (const [key, entry] of Object.entries(value as Record<string, unknown>)) {
      out[key] = stripJsonNulls(entry)
    }
    return out
  }
  return value
}

class ApiEntityRepository<T extends { id: string }> implements EntityRepository<T> {
  constructor(
    protected readonly collection: StoreName,
    protected readonly baseUrl: string,
  ) {}

  protected url(suffix = ''): string {
    return `${this.baseUrl}/entities/${this.collection}${suffix}`
  }

  async get(id: string): Promise<T | undefined> {
    try {
      return await api<T>(this.url(`/${id}`))
    } catch {
      return undefined
    }
  }

  async list(): Promise<T[]> {
    return api<T[]>(this.url())
  }

  async put(entity: T): Promise<void> {
    await api<T>(this.url(`/${entity.id}`), {
      method: 'PUT',
      body: JSON.stringify(entity),
    })
  }
}

class ApiCalendarEntityRepository<T extends CalendarEntity>
  extends ApiEntityRepository<T>
  implements CalendarEntityRepository<T>
{
  async listByCalendarId(calendarId: string): Promise<T[]> {
    const query = new URLSearchParams({ calendarId })
    return api<T[]>(`${this.url()}?${query.toString()}`)
  }
}

class ApiCalendarRepository extends ApiEntityRepository<Calendar> implements CalendarRepository {
  async getLocalCalendar(): Promise<Calendar | undefined> {
    const result = await api<Calendar | null>(`${this.baseUrl}/calendars/local`)
    return result ?? undefined
  }
}

export function createApiRepositories(baseUrl = '/api'): Repositories {
  const root = baseUrl.replace(/\/$/, '')
  return {
    calendars: new ApiCalendarRepository('calendars', root),
    events: new ApiCalendarEntityRepository('events', root),
    recurrenceRules: new ApiEntityRepository('recurrenceRules', root),
    eventExceptions: new ApiEntityRepository('eventExceptions', root),
    plans: new ApiCalendarEntityRepository('plans', root),
    planTasks: new ApiEntityRepository('planTasks', root),
    tasks: new ApiCalendarEntityRepository('tasks', root),
    lists: new ApiCalendarEntityRepository('lists', root),
    listItems: new ApiEntityRepository('listItems', root),
    categories: new ApiCalendarEntityRepository('categories', root),
    reminders: new ApiEntityRepository('reminders', root),
  }
}

/**
 * MySQL via FastAPI is the source of truth (D9).
 * Opt out only with explicit VITE_USE_API=false (legacy IndexedDB).
 */
export function shouldUseApiRepository(): boolean {
  const flag = import.meta.env.VITE_USE_API
  if (flag === 'false' || flag === '0') return false
  return true
}
