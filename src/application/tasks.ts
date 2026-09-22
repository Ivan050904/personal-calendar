import { createId } from '../domain/ids'
import type { Calendar, IsoDate, Task } from '../domain/models'
import { ValidationError } from '../domain/validation'
import type { CalendarEntityRepository } from './repositories'

export interface TaskDraft {
  title: string
  description?: string
  dueDate?: IsoDate
}

export interface TasksService {
  readonly calendar: Calendar
  createTask(draft: TaskDraft): Promise<Task>
  updateTask(id: string, draft: TaskDraft): Promise<Task>
  deleteTask(id: string): Promise<void>
  listUndatedTasks(): Promise<Task[]>
  listTasksForDate(date: IsoDate): Promise<Task[]>
  moveTask(id: string, dueDate: IsoDate): Promise<Task>
  toggleCompleted(id: string): Promise<Task>
}

export class LocalTasksService implements TasksService {
  constructor(
    readonly calendar: Calendar,
    private readonly tasks: CalendarEntityRepository<Task>,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async createTask(draft: TaskDraft): Promise<Task> {
    const timestamp = this.now()
    const task: Task = {
      id: createId(),
      calendarId: this.calendar.id,
      title: draft.title,
      description: draft.description,
      dueDate: draft.dueDate,
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
    const timestamp = this.now()
    const task: Task = {
      ...existing,
      title: draft.title,
      description: draft.description,
      dueDate: draft.dueDate,
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
    const task: Task = { ...existing, completed: !existing.completed, updatedAt: timestamp }
    await this.tasks.put(task)
    return task
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
}
