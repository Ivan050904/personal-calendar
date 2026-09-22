import { createId } from '../domain/ids'
import type { Calendar, Category, Event, Plan, Task, TaskList } from '../domain/models'
import { ValidationError } from '../domain/validation'
import type { CalendarEntityRepository } from './repositories'

export interface CategoryDraft {
  name: string
}

export class LocalCategoriesService {
  constructor(
    readonly calendar: Calendar,
    private readonly categories: CalendarEntityRepository<Category>,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async list(): Promise<Category[]> {
    return (await this.categories.listByCalendarId(this.calendar.id))
      .filter((item) => item.deletedAt === undefined)
      .sort((left, right) => left.name.localeCompare(right.name))
  }

  async create(draft: CategoryDraft): Promise<Category> {
    requireName(draft.name)
    const timestamp = this.now()
    const category: Category = {
      id: createId(),
      calendarId: this.calendar.id,
      name: draft.name.trim(),
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    await this.categories.put(category)
    return category
  }

  async rename(id: string, name: string): Promise<Category> {
    requireName(name)
    const existing = await this.require(id)
    const category = { ...existing, name: name.trim(), updatedAt: this.now() }
    await this.categories.put(category)
    return category
  }

  async softDelete(id: string): Promise<void> {
    const existing = await this.require(id)
    const timestamp = this.now()
    await this.categories.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  private async require(id: string): Promise<Category> {
    const category = await this.categories.get(id)
    if (category === undefined || category.calendarId !== this.calendar.id || category.deletedAt !== undefined) {
      throw new Error('Category not found')
    }
    return category
  }
}

export function filterEventsByCategory(events: Event[], categoryId: string | undefined): Event[] {
  if (categoryId === undefined) return events
  return events.filter((event) => event.categoryId === categoryId)
}

export interface SearchHit {
  type: 'event' | 'plan' | 'task' | 'list'
  id: string
  title: string
}

export function searchEntities(
  query: string,
  data: { events: Event[]; plans: Plan[]; tasks: Task[]; lists: TaskList[] },
): SearchHit[] {
  const needle = query.trim().toLowerCase()
  if (needle.length === 0) return []
  const hits: SearchHit[] = []
  for (const event of data.events) {
    if (event.deletedAt === undefined && matches(event.title, event.description, needle)) {
      hits.push({ type: 'event', id: event.id, title: event.title })
    }
  }
  for (const plan of data.plans) {
    if (plan.deletedAt === undefined && matches(plan.title, plan.description ?? '', needle)) {
      hits.push({ type: 'plan', id: plan.id, title: plan.title })
    }
  }
  for (const task of data.tasks) {
    if (task.deletedAt === undefined && matches(task.title, task.description ?? '', needle)) {
      hits.push({ type: 'task', id: task.id, title: task.title })
    }
  }
  for (const list of data.lists) {
    if (list.deletedAt === undefined && matches(list.title, '', needle)) {
      hits.push({ type: 'list', id: list.id, title: list.title })
    }
  }
  return hits
}

function matches(title: string, description: string, needle: string): boolean {
  return title.toLowerCase().includes(needle) || description.toLowerCase().includes(needle)
}

function requireName(name: string): void {
  if (name.trim().length === 0) throw new ValidationError('name is required')
}
