import type {
  Calendar,
  CalendarEntity,
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

export interface EntityRepository<T extends { id: string }> {
  get(id: string): Promise<T | undefined>
  list(): Promise<T[]>
  put(entity: T): Promise<void>
}

export interface CalendarEntityRepository<T extends CalendarEntity> extends EntityRepository<T> {
  listByCalendarId(calendarId: string): Promise<T[]>
}

export interface CalendarRepository extends EntityRepository<Calendar> {
  getLocalCalendar(): Promise<Calendar | undefined>
}

export interface Repositories {
  calendars: CalendarRepository
  events: CalendarEntityRepository<Event>
  recurrenceRules: EntityRepository<RecurrenceRule>
  eventExceptions: EntityRepository<EventException>
  plans: CalendarEntityRepository<Plan>
  planTasks: EntityRepository<PlanTask>
  tasks: CalendarEntityRepository<Task>
  lists: CalendarEntityRepository<TaskList>
  listItems: EntityRepository<TaskListItem>
  categories: CalendarEntityRepository<Category>
  reminders: EntityRepository<Reminder>
}
