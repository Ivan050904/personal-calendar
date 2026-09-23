import { createId } from '../domain/ids'
import type { Calendar, IsoDate, RecurrenceRule, Task } from '../domain/models'
import { validateRecurrenceRule, ValidationError } from '../domain/validation'
import type { CalendarEntityRepository, EntityRepository } from './repositories'
import { nextDueDateAfter, type RecurrenceDraft } from './recurrence'

export interface TaskDraft {
  title: string
  description?: string
  dueDate?: IsoDate
  recurrence?: RecurrenceDraft
}

export interface TasksService {
  readonly calendar: Calendar
  createTask(draft: TaskDraft): Promise<Task>
  updateTask(id: string, draft: TaskDraft): Promise<Task>
  deleteTask(id: string): Promise<void>
  listUndatedTasks(): Promise<Task[]>
  listTasksForDate(date: IsoDate): Promise<Task[]>
  /** Exact due date plus incomplete overdue tasks (for Today / «Сегодня»). */
  listTasksDueOnOrOverdue(date: IsoDate): Promise<Task[]>
  moveTask(id: string, dueDate: IsoDate): Promise<Task>
  toggleCompleted(id: string): Promise<Task>
  getRecurrenceRule(id: string): Promise<RecurrenceRule | undefined>
}

export class LocalTasksService implements TasksService {
  constructor(
    readonly calendar: Calendar,
    private readonly tasks: CalendarEntityRepository<Task>,
    private readonly recurrenceRules: EntityRepository<RecurrenceRule> = emptyRecurrenceRepository(),
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async createTask(draft: TaskDraft): Promise<Task> {
    if (draft.recurrence !== undefined && draft.dueDate === undefined) {
      throw new ValidationError('recurring task requires dueDate')
    }
    const timestamp = this.now()
    let recurrenceRuleId: string | undefined
    if (draft.recurrence !== undefined) {
      const rule = toRule(draft.recurrence, timestamp)
      validateRecurrenceRule(rule)
      await this.recurrenceRules.put(rule)
      recurrenceRuleId = rule.id
    }
    const task: Task = {
      id: createId(),
      calendarId: this.calendar.id,
      title: draft.title,
      description: draft.description,
      dueDate: draft.dueDate,
      recurrenceRuleId,
      completed: false,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    validateTask(task)
    await this.tasks.put(task)
    return task
  }

  async updateTask(id: string, draft: TaskDraft): Promise<Task> {
    const existing = await this.requireTask(id)
    if (draft.recurrence !== undefined && draft.dueDate === undefined) {
      throw new ValidationError('recurring task requires dueDate')
    }
    const timestamp = this.now()
    let recurrenceRuleId = existing.recurrenceRuleId
    if (draft.recurrence === undefined) {
      recurrenceRuleId = undefined
    } else {
      const previous = recurrenceRuleId === undefined ? undefined : await this.recurrenceRules.get(recurrenceRuleId)
      const rule = toRule(draft.recurrence, timestamp, previous)
      validateRecurrenceRule(rule)
      await this.recurrenceRules.put(rule)
      recurrenceRuleId = rule.id
    }
    const task: Task = {
      ...existing,
      title: draft.title,
      description: draft.description,
      dueDate: draft.dueDate,
      recurrenceRuleId,
      updatedAt: timestamp,
    }
    validateTask(task)
    await this.tasks.put(task)
    return task
  }

  async deleteTask(id: string): Promise<void> {
    const existing = await this.requireTask(id)
    const timestamp = this.now()
    await this.tasks.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async listUndatedTasks(): Promise<Task[]> {
    return (await this.activeTasks()).filter((task) => task.dueDate === undefined)
  }

  async listTasksForDate(date: IsoDate): Promise<Task[]> {
    return (await this.activeTasks()).filter((task) => task.dueDate === date)
  }

  async listTasksDueOnOrOverdue(date: IsoDate): Promise<Task[]> {
    return (await this.activeTasks()).filter((task) => {
      if (task.dueDate === undefined) return false
      if (task.dueDate === date) return true
      return task.dueDate < date && !task.completed
    })
  }

  async moveTask(id: string, dueDate: IsoDate): Promise<Task> {
    const existing = await this.requireTask(id)
    if (existing.dueDate === undefined) {
      throw new Error('Task has no due date')
    }
    const timestamp = this.now()
    const task: Task = { ...existing, dueDate, updatedAt: timestamp }
    validateTask(task)
    await this.tasks.put(task)
    return task
  }

  async toggleCompleted(id: string): Promise<Task> {
    const existing = await this.requireTask(id)
    const timestamp = this.now()

    if (existing.recurrenceRuleId === undefined || existing.dueDate === undefined) {
      const task: Task = { ...existing, completed: !existing.completed, updatedAt: timestamp }
      await this.tasks.put(task)
      return task
    }

    // Unchecking a finished series (no next left) just reopens.
    if (existing.completed) {
      const task: Task = { ...existing, completed: false, updatedAt: timestamp }
      await this.tasks.put(task)
      return task
    }

    const rule = await this.recurrenceRules.get(existing.recurrenceRuleId)
    if (rule === undefined) {
      const task: Task = { ...existing, completed: true, updatedAt: timestamp }
      await this.tasks.put(task)
      return task
    }

    if (rule.occurrenceCount !== undefined) {
      if (rule.occurrenceCount <= 1) {
        const task: Task = { ...existing, completed: true, updatedAt: timestamp }
        await this.tasks.put(task)
        await this.recurrenceRules.put({ ...rule, occurrenceCount: 0, updatedAt: timestamp })
        return task
      }
      await this.recurrenceRules.put({
        ...rule,
        occurrenceCount: rule.occurrenceCount - 1,
        updatedAt: timestamp,
      })
    }

    const nextDue = nextDueDateAfter(existing.dueDate, rule, this.calendar.timezone)
    if (nextDue === undefined) {
      const task: Task = { ...existing, completed: true, updatedAt: timestamp }
      await this.tasks.put(task)
      return task
    }

    const task: Task = {
      ...existing,
      dueDate: nextDue,
      completed: false,
      updatedAt: timestamp,
    }
    await this.tasks.put(task)
    return task
  }

  async getRecurrenceRule(id: string): Promise<RecurrenceRule | undefined> {
    return this.recurrenceRules.get(id)
  }

  private async activeTasks(): Promise<Task[]> {
    return (await this.tasks.listByCalendarId(this.calendar.id)).filter((task) => task.deletedAt === undefined)
  }

  private async requireTask(id: string): Promise<Task> {
    const task = await this.tasks.get(id)
    if (task === undefined || task.calendarId !== this.calendar.id || task.deletedAt !== undefined) {
      throw new Error('Task not found')
    }
    return task
  }
}

function validateTask(task: Task): void {
  if (task.title.trim().length === 0) {
    throw new ValidationError('title is required')
  }
  if (task.recurrenceRuleId !== undefined && task.dueDate === undefined) {
    throw new ValidationError('recurring task requires dueDate')
  }
}

function toRule(draft: RecurrenceDraft, timestamp: string, previous?: RecurrenceRule): RecurrenceRule {
  return {
    id: previous?.id ?? createId(),
    frequency: draft.frequency,
    interval: draft.interval,
    weekdays: draft.weekdays,
    dayOfMonth: draft.dayOfMonth,
    untilDate: draft.untilDate,
    occurrenceCount: draft.occurrenceCount,
    createdAt: previous?.createdAt ?? timestamp,
    updatedAt: timestamp,
  }
}

function emptyRecurrenceRepository(): EntityRepository<RecurrenceRule> {
  return {
    async get() { return undefined },
    async list() { return [] },
    async put() { return undefined },
  }
}
