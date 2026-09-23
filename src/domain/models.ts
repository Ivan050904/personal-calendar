export type EntityId = string
export type IsoDateTime = string
export type IsoDate = string

export interface Entity {
  id: EntityId
  createdAt: IsoDateTime
  updatedAt: IsoDateTime
  deletedAt?: IsoDateTime
}

export interface Calendar extends Entity {
  name: string
  timezone: string
}

export interface CalendarEntity extends Entity {
  calendarId: EntityId
}

export interface Event extends CalendarEntity {
  title: string
  description: string
  startAt: IsoDateTime
  endAt: IsoDateTime
  timezone: string
  allDay: boolean
  categoryId?: EntityId
  color: string
  recurrenceRuleId?: EntityId
}

export type RecurrenceFrequency = 'daily' | 'weekly' | 'weekdays' | 'monthly'
export type Weekday = 1 | 2 | 3 | 4 | 5 | 6 | 7

export interface RecurrenceRule extends Entity {
  frequency: RecurrenceFrequency
  interval: number
  weekdays: Weekday[]
  dayOfMonth?: number
  untilDate?: IsoDate
  occurrenceCount?: number
}

export interface EventException extends Entity {
  eventId: EntityId
  recurrenceRuleId: EntityId
  occurrenceKey: string
  type: 'modified' | 'cancelled'
  overrideStartAt?: IsoDateTime
  overrideEndAt?: IsoDateTime
}

export interface Plan extends CalendarEntity {
  title: string
  description?: string
  startAt: IsoDateTime
  endAt: IsoDateTime
  timezone: string
  color: string
}

export interface PlanTask extends Entity {
  planId: EntityId
  title: string
  completed: boolean
  order: number
}

export interface Task extends CalendarEntity {
  title: string
  description?: string
  dueDate?: IsoDate
  recurrenceRuleId?: EntityId
  completed: boolean
}

export interface TaskList extends CalendarEntity {
  title: string
}

export interface TaskListItem extends Entity {
  listId: EntityId
  title: string
  completed: boolean
  order: number
}

export interface Category extends CalendarEntity {
  name: string
}

export interface Reminder extends Entity {
  eventId: EntityId
  offsetMinutes: number
}

export type StoredEntity =
  | Calendar
  | Event
  | RecurrenceRule
  | EventException
  | Plan
  | PlanTask
  | Task
  | TaskList
  | TaskListItem
  | Category
  | Reminder
