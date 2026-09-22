import { createId } from '../domain/ids'
import type { Calendar, TaskList, TaskListItem } from '../domain/models'
import { ValidationError } from '../domain/validation'
import type { CalendarEntityRepository, EntityRepository } from './repositories'

export interface ListDraft {
  title: string
}

export interface ListItemDraft {
  title: string
}

export interface TaskListWithItems {
  list: TaskList
  items: TaskListItem[]
}

export class LocalListsService {
  constructor(
    readonly calendar: Calendar,
    private readonly lists: CalendarEntityRepository<TaskList>,
    private readonly listItems: EntityRepository<TaskListItem>,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async listAll(): Promise<TaskListWithItems[]> {
    const [lists, items] = await Promise.all([
      this.lists.listByCalendarId(this.calendar.id),
      this.listItems.list(),
    ])
    const activeLists = lists
      .filter((list) => list.deletedAt === undefined)
      .sort((left, right) => left.title.localeCompare(right.title))

    return activeLists.map((list) => ({
      list,
      items: items
        .filter((item) => item.listId === list.id && item.deletedAt === undefined)
        .sort((left, right) => left.order - right.order),
    }))
  }

  async create(draft: ListDraft): Promise<TaskList> {
    requireTitle(draft.title)
    const timestamp = this.now()
    const list: TaskList = {
      id: createId(),
      calendarId: this.calendar.id,
      title: draft.title.trim(),
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    await this.lists.put(list)
    return list
  }

  async rename(id: string, title: string): Promise<TaskList> {
    requireTitle(title)
    const existing = await this.requireList(id)
    const list = { ...existing, title: title.trim(), updatedAt: this.now() }
    await this.lists.put(list)
    return list
  }

  async softDelete(id: string): Promise<void> {
    const existing = await this.requireList(id)
    const timestamp = this.now()
    await this.lists.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async addItem(listId: string, draft: ListItemDraft): Promise<TaskListItem> {
    await this.requireList(listId)
    requireTitle(draft.title)
    const timestamp = this.now()
    const siblings = await this.activeItemsForList(listId)
    const order = siblings.reduce((max, item) => Math.max(max, item.order), -1) + 1
    const item: TaskListItem = {
      id: createId(),
      listId,
      title: draft.title.trim(),
      completed: false,
      order,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    await this.listItems.put(item)
    return item
  }

  async updateItem(id: string, draft: ListItemDraft): Promise<TaskListItem> {
    requireTitle(draft.title)
    const existing = await this.requireItem(id)
    const item = { ...existing, title: draft.title.trim(), updatedAt: this.now() }
    await this.listItems.put(item)
    return item
  }

  async deleteItem(id: string): Promise<void> {
    const existing = await this.requireItem(id)
    const timestamp = this.now()
    await this.listItems.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async toggleItem(id: string): Promise<TaskListItem> {
    const existing = await this.requireItem(id)
    const item = { ...existing, completed: !existing.completed, updatedAt: this.now() }
    await this.listItems.put(item)
    return item
  }

  async reorderItems(listId: string, orderedIds: string[]): Promise<TaskListItem[]> {
    await this.requireList(listId)
    const siblings = await this.activeItemsForList(listId)
    if (orderedIds.length !== siblings.length) {
      throw new ValidationError('orderedIds must include every list item exactly once')
    }
    const byId = new Map(siblings.map((item) => [item.id, item]))
    const seen = new Set<string>()
    const timestamp = this.now()
    const reordered: TaskListItem[] = []
    for (let index = 0; index < orderedIds.length; index += 1) {
      const id = orderedIds[index]
      if (seen.has(id)) {
        throw new ValidationError('orderedIds must include every list item exactly once')
      }
      const existing = byId.get(id)
      if (existing === undefined) {
        throw new ValidationError('orderedIds must include every list item exactly once')
      }
      seen.add(id)
      const item = { ...existing, order: index, updatedAt: timestamp }
      await this.listItems.put(item)
      reordered.push(item)
    }
    return reordered
  }

  private async activeItemsForList(listId: string): Promise<TaskListItem[]> {
    return (await this.listItems.list())
      .filter((item) => item.listId === listId && item.deletedAt === undefined)
  }

  private async requireList(id: string): Promise<TaskList> {
    const list = await this.lists.get(id)
    if (list === undefined || list.calendarId !== this.calendar.id || list.deletedAt !== undefined) {
      throw new Error('List not found')
    }
    return list
  }

  private async requireItem(id: string): Promise<TaskListItem> {
    const item = await this.listItems.get(id)
    if (item === undefined || item.deletedAt !== undefined) {
      throw new Error('List item not found')
    }
    await this.requireList(item.listId)
    return item
  }
}

function requireTitle(title: string): void {
  if (title.trim().length === 0) throw new ValidationError('title is required')
}
