import { createId } from '../domain/ids'
import type { Calendar, Event, EventException, RecurrenceRule } from '../domain/models'
import { validateEvent, validateRecurrenceRule } from '../domain/validation'
import type { CalendarEntityRepository, EntityRepository } from './repositories'
import {
  expandEventsInRange,
  makeOccurrenceKey,
  parseOccurrenceId,
  splitRuleAtOccurrence,
  upsertCancelledException,
  upsertModifiedException,
  type DeleteScope,
  type EditScope,
  type RecurrenceDraft,
} from './recurrence'

export interface EventDraft {
  title: string
  description: string
  startAt: string
  endAt: string
  color: string
  allDay?: boolean
  categoryId?: string
  recurrence?: RecurrenceDraft
}

export interface DayCalendarService {
  readonly calendar: Calendar
  listEvents(date: string): Promise<Event[]>
  listEventsInRange(startDate: string, endDate: string): Promise<Event[]>
  createEvent(draft: EventDraft): Promise<Event>
  updateEvent(id: string, draft: EventDraft, scope?: EditScope): Promise<Event>
  deleteEvent(id: string, scope?: DeleteScope): Promise<void>
  moveEvent(id: string, startAt: string): Promise<Event>
  resizeEvent(id: string, endAt: string): Promise<Event>
}

export class LocalDayCalendarService implements DayCalendarService {
  constructor(
    readonly calendar: Calendar,
    private readonly events: CalendarEntityRepository<Event>,
    private readonly recurrenceRules: EntityRepository<RecurrenceRule> = emptyRepository(),
    private readonly eventExceptions: EntityRepository<EventException> = emptyRepository(),
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async listEvents(date: string): Promise<Event[]> {
    return (await this.listEventsInRange(date, date)).filter(
      (event) => dateKey(event.startAt, event.timezone || this.calendar.timezone) === date,
    )
  }

  async listEventsInRange(startDate: string, endDate: string): Promise<Event[]> {
    const [events, rules, exceptions] = await Promise.all([
      this.events.listByCalendarId(this.calendar.id),
      this.recurrenceRules.list(),
      this.eventExceptions.list(),
    ])
    return expandEventsInRange(events, rules, exceptions, startDate, endDate)
  }

  async createEvent(draft: EventDraft): Promise<Event> {
    const timestamp = this.now()
    let recurrenceRuleId: string | undefined
    if (draft.recurrence !== undefined) {
      const rule = toRule(draft.recurrence, timestamp)
      validateRecurrenceRule(rule)
      await this.recurrenceRules.put(rule)
      recurrenceRuleId = rule.id
    }
    const event: Event = {
      id: createId(),
      calendarId: this.calendar.id,
      title: draft.title,
      description: draft.description,
      startAt: draft.startAt,
      endAt: draft.endAt,
      color: draft.color,
      timezone: this.calendar.timezone,
      allDay: Boolean(draft.allDay),
      categoryId: draft.categoryId,
      recurrenceRuleId,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    validateEvent(event)
    await this.events.put(event)
    return event
  }

  async updateEvent(id: string, draft: EventDraft, scope: EditScope = 'series'): Promise<Event> {
    const { seriesEventId, occurrenceKey } = parseOccurrenceId(id)
    const existing = await this.requireSeriesEvent(seriesEventId)

    if (existing.recurrenceRuleId === undefined || occurrenceKey === undefined || scope === 'series') {
      return this.updateSeries(existing, draft)
    }
    if (scope === 'this') {
      await upsertModifiedException(this.eventExceptions, {
        eventId: existing.id,
        recurrenceRuleId: existing.recurrenceRuleId,
        occurrenceKey,
        overrideStartAt: draft.startAt,
        overrideEndAt: draft.endAt,
        now: this.now(),
      })
      const visible = (await this.listEventsInRange(dateKey(draft.startAt, existing.timezone), dateKey(draft.endAt, existing.timezone)))
        .find((item) => item.id === `${existing.id}::${occurrenceKey}`)
      return visible ?? { ...existing, ...draft, id: `${existing.id}::${occurrenceKey}`, updatedAt: this.now() }
    }

    // thisAndFollowing
    const rule = await this.recurrenceRules.get(existing.recurrenceRuleId)
    if (rule === undefined) throw new Error('Recurrence rule not found')
    const occurrenceDate = occurrenceKey.slice(0, 10)
    const timestamp = this.now()
    const { historical, following } = splitRuleAtOccurrence(rule, occurrenceDate, timestamp)
    await this.recurrenceRules.put(historical)
    const followingRule = draft.recurrence !== undefined
      ? { ...toRule(draft.recurrence, timestamp), id: following.id }
      : following
    validateRecurrenceRule(followingRule)
    await this.recurrenceRules.put(followingRule)
    const followingEvent: Event = {
      ...existing,
      id: createId(),
      title: draft.title,
      description: draft.description,
      startAt: draft.startAt,
      endAt: draft.endAt,
      color: draft.color,
      recurrenceRuleId: followingRule.id,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    validateEvent(followingEvent)
    await this.events.put(followingEvent)
    return followingEvent
  }

  async deleteEvent(id: string, scope: DeleteScope = 'series'): Promise<void> {
    const { seriesEventId, occurrenceKey } = parseOccurrenceId(id)
    const existing = await this.requireSeriesEvent(seriesEventId)
    if (existing.recurrenceRuleId !== undefined && occurrenceKey !== undefined && scope === 'this') {
      await upsertCancelledException(this.eventExceptions, {
        eventId: existing.id,
        recurrenceRuleId: existing.recurrenceRuleId,
        occurrenceKey,
        now: this.now(),
      })
      return
    }
    const timestamp = this.now()
    await this.events.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async moveEvent(id: string, startAt: string): Promise<Event> {
    const { seriesEventId, occurrenceKey } = parseOccurrenceId(id)
    const event = await this.requireSeriesEvent(seriesEventId)
    const duration = Date.parse(event.endAt) - Date.parse(event.startAt)
    const endAt = new Date(Date.parse(startAt) + duration).toISOString()
    if (event.recurrenceRuleId !== undefined && occurrenceKey !== undefined) {
      await upsertModifiedException(this.eventExceptions, {
        eventId: event.id,
        recurrenceRuleId: event.recurrenceRuleId,
        occurrenceKey,
        overrideStartAt: startAt,
        overrideEndAt: endAt,
        now: this.now(),
      })
      return { ...event, id, startAt, endAt, updatedAt: this.now() }
    }
    return this.updateEvent(id, { title: event.title, description: event.description, startAt, endAt, color: event.color })
  }

  async resizeEvent(id: string, endAt: string): Promise<Event> {
    const { seriesEventId, occurrenceKey } = parseOccurrenceId(id)
    const event = await this.requireSeriesEvent(seriesEventId)
    if (event.recurrenceRuleId !== undefined && occurrenceKey !== undefined) {
      const existingException = (await this.eventExceptions.list()).find(
        (item) => item.eventId === event.id && item.occurrenceKey === occurrenceKey && item.type === 'modified',
      )
      const startAt = existingException?.overrideStartAt
        ?? zonedInputToIso(`${occurrenceKey.slice(0, 10)}T${localTimeFromKey(occurrenceKey)}`, event.timezone)
      await upsertModifiedException(this.eventExceptions, {
        eventId: event.id,
        recurrenceRuleId: event.recurrenceRuleId,
        occurrenceKey,
        overrideStartAt: startAt,
        overrideEndAt: endAt,
        now: this.now(),
      })
      return { ...event, id, startAt, endAt, updatedAt: this.now() }
    }
    return this.updateEvent(id, { title: event.title, description: event.description, startAt: event.startAt, endAt, color: event.color })
  }

  private async updateSeries(existing: Event, draft: EventDraft): Promise<Event> {
    const timestamp = this.now()
    let recurrenceRuleId = existing.recurrenceRuleId
    if (draft.recurrence !== undefined) {
      const previous = existing.recurrenceRuleId === undefined
        ? undefined
        : await this.recurrenceRules.get(existing.recurrenceRuleId)
      const rule = toRule(draft.recurrence, timestamp, previous)
      validateRecurrenceRule(rule)
      await this.recurrenceRules.put(rule)
      recurrenceRuleId = rule.id
    }
    const event = {
      ...existing,
      title: draft.title,
      description: draft.description,
      startAt: draft.startAt,
      endAt: draft.endAt,
      color: draft.color,
      timezone: this.calendar.timezone,
      allDay: draft.allDay ?? existing.allDay,
      categoryId: draft.categoryId !== undefined ? draft.categoryId : existing.categoryId,
      recurrenceRuleId,
      updatedAt: timestamp,
    }
    validateEvent(event)
    await this.events.put(event)
    return event
  }

  private async requireSeriesEvent(id: string): Promise<Event> {
    const event = await this.events.get(id)
    if (event === undefined || event.calendarId !== this.calendar.id || event.deletedAt !== undefined) {
      throw new Error('Event not found')
    }
    return event
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

function localTimeFromKey(occurrenceKey: string): string {
  return occurrenceKey.slice(11)
}

function emptyRepository<T extends { id: string }>(): EntityRepository<T> {
  return {
    async get() { return undefined },
    async list() { return [] },
    async put() { return undefined },
  }
}

function dateParts(value: string, timezone: string): Record<string, string> {
  return Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date(value)).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  )
}

export function dateKey(value: string | Date, timezone: string): string {
  const parts = dateParts(value instanceof Date ? value.toISOString() : value, timezone)
  return `${parts.year}-${parts.month}-${parts.day}`
}

export function eventHour(event: Pick<Event, 'startAt' | 'timezone'>): number {
  const hour = new Intl.DateTimeFormat('en-US', {
    timeZone: event.timezone,
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(new Date(event.startAt)).find((part) => part.type === 'hour')?.value
  return Number(hour ?? '0')
}

export function hourInTimezone(value: Date, timezone: string): number {
  const hour = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    hour: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(value).find((part) => part.type === 'hour')?.value
  return Number(hour ?? '0')
}

export function minuteInTimezone(value: Date, timezone: string): number {
  const minute = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    minute: '2-digit',
  }).formatToParts(value).find((part) => part.type === 'minute')?.value
  return Number(minute ?? '0')
}

function dateTimeParts(value: Date, timezone: string): Record<string, string> {
  return Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
    }).formatToParts(value).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  )
}

export function zonedInputToIso(value: string, timezone: string): string {
  const [date, time] = value.split('T')
  const [year, month, day] = date.split('-').map(Number)
  const [hour, minute] = time.split(':').map(Number)
  const utcGuess = Date.UTC(year, month - 1, day, hour, minute)
  const resolved = dateTimeParts(new Date(utcGuess), timezone)
  const resolvedAsUtc = Date.UTC(Number(resolved.year), Number(resolved.month) - 1, Number(resolved.day), Number(resolved.hour), Number(resolved.minute))
  return new Date(utcGuess - (resolvedAsUtc - utcGuess)).toISOString()
}

export function isoToZonedInput(value: string, timezone: string): string {
  const parts = dateTimeParts(new Date(value), timezone)
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`
}

export function allDayBounds(date: string, timezone: string): { startAt: string; endAt: string } {
  return {
    startAt: zonedInputToIso(`${date}T00:00`, timezone),
    endAt: zonedInputToIso(`${date}T23:59`, timezone),
  }
}

export function overlaps(candidate: Pick<Event, 'id' | 'startAt' | 'endAt'>, events: Event[]): boolean {
  return events.some((event) => event.id !== candidate.id && Date.parse(candidate.startAt) < Date.parse(event.endAt) && Date.parse(candidate.endAt) > Date.parse(event.startAt))
}

export { makeOccurrenceKey }
export type { DeleteScope, EditScope, RecurrenceDraft }
