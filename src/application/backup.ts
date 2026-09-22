import type {
  Calendar,
  Category,
  Event,
  EventException,
  Plan,
  PlanTask,
  RecurrenceRule,
  Reminder,
  Task,
  TaskList,
  TaskListItem,
} from '../domain/models'
import type { Repositories } from './repositories'

export const BACKUP_SCHEMA_VERSION = 1

export interface BackupEnvelope {
  schemaVersion: number
  exportedAt: string
  calendar: Calendar
  events: Event[]
  recurrenceRules: RecurrenceRule[]
  eventExceptions: EventException[]
  plans: Plan[]
  planTasks: PlanTask[]
  tasks: Task[]
  lists: TaskList[]
  listItems: TaskListItem[]
  categories: Category[]
  reminders: Reminder[]
}

export class BackupValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'BackupValidationError'
  }
}

export async function exportBackup(repositories: Repositories, exportedAt: string): Promise<BackupEnvelope> {
  const calendar = await repositories.calendars.getLocalCalendar()
  if (calendar === undefined) throw new BackupValidationError('local calendar is missing')
  const [
    events, recurrenceRules, eventExceptions, plans, planTasks, tasks, lists, listItems, categories, reminders,
  ] = await Promise.all([
    repositories.events.list(),
    repositories.recurrenceRules.list(),
    repositories.eventExceptions.list(),
    repositories.plans.list(),
    repositories.planTasks.list(),
    repositories.tasks.list(),
    repositories.lists.list(),
    repositories.listItems.list(),
    repositories.categories.list(),
    repositories.reminders.list(),
  ])
  return {
    schemaVersion: BACKUP_SCHEMA_VERSION,
    exportedAt,
    calendar,
    events,
    recurrenceRules,
    eventExceptions,
    plans,
    planTasks,
    tasks,
    lists,
    listItems,
    categories,
    reminders,
  }
}

export function validateBackup(payload: unknown): BackupEnvelope {
  if (payload === null || typeof payload !== 'object') throw new BackupValidationError('backup must be an object')
  const value = payload as Partial<BackupEnvelope>
  if (value.schemaVersion !== BACKUP_SCHEMA_VERSION) {
    throw new BackupValidationError(`unsupported schemaVersion: ${String(value.schemaVersion)}`)
  }
  if (value.calendar === undefined || typeof value.calendar.id !== 'string') {
    throw new BackupValidationError('calendar is required')
  }
  const arrays: Array<keyof BackupEnvelope> = [
    'events', 'recurrenceRules', 'eventExceptions', 'plans', 'planTasks', 'tasks', 'lists', 'listItems', 'categories', 'reminders',
  ]
  for (const key of arrays) {
    if (!Array.isArray(value[key])) throw new BackupValidationError(`${key} must be an array`)
  }
  return value as BackupEnvelope
}

/**
 * Replace-only import (docs/08_STORAGE.md). Caller must confirm before invoking.
 */
export async function importBackupReplace(repositories: Repositories, payload: unknown): Promise<BackupEnvelope> {
  const backup = validateBackup(payload)
  await repositories.calendars.put(backup.calendar)
  for (const event of backup.events) await repositories.events.put(event)
  for (const rule of backup.recurrenceRules) await repositories.recurrenceRules.put(rule)
  for (const exception of backup.eventExceptions) await repositories.eventExceptions.put(exception)
  for (const plan of backup.plans) await repositories.plans.put(plan)
  for (const task of backup.planTasks) await repositories.planTasks.put(task)
  for (const task of backup.tasks) await repositories.tasks.put(task)
  for (const list of backup.lists) await repositories.lists.put(list)
  for (const item of backup.listItems) await repositories.listItems.put(item)
  for (const category of backup.categories) await repositories.categories.put(category)
  for (const reminder of backup.reminders) await repositories.reminders.put(reminder)
  return backup
}
