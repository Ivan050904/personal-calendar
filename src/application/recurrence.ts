import { createId } from '../domain/ids'
import type { Event, EventException, RecurrenceRule, Weekday } from '../domain/models'
import { validateEventException, validateRecurrenceRule } from '../domain/validation'
import { dateKey, isoToZonedInput, zonedInputToIso } from './day-calendar'
import type { EntityRepository } from './repositories'

export type EditScope = 'this' | 'thisAndFollowing' | 'series'
export type DeleteScope = 'this' | 'series'

export interface RecurrenceDraft {
  frequency: RecurrenceRule['frequency']
  interval: number
  weekdays: Weekday[]
  dayOfMonth?: number
  untilDate?: string
  occurrenceCount?: number
}

export interface OccurrenceProjection {
  seriesEventId: string
  occurrenceKey: string
  event: Event
}

function addDaysIso(date: string, days: number): string {
  const value = new Date(`${date}T12:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate()
}

/** Clamp day-of-month into the target month (ADR-012). */
export function clampDayOfMonth(year: number, month: number, dayOfMonth: number): number {
  return Math.min(dayOfMonth, daysInMonth(year, month))
}

export function weekdayOf(date: string, timezone: string): Weekday {
  const noon = zonedInputToIso(`${date}T12:00`, timezone)
  const weekday = new Intl.DateTimeFormat('en-US', { timeZone: timezone, weekday: 'short' })
    .format(new Date(noon))
  const map: Record<string, Weekday> = { Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6, Sun: 7 }
  return map[weekday] ?? 1
}

export function makeOccurrenceKey(startAt: string, timezone: string): string {
  return isoToZonedInput(startAt, timezone)
}

function localTimeOf(startAt: string, timezone: string): string {
  return isoToZonedInput(startAt, timezone).slice(11)
}

function buildOccurrenceStart(date: string, time: string, timezone: string): string {
  return zonedInputToIso(`${date}T${time}`, timezone)
}

function matchesWeekdays(date: string, timezone: string, weekdays: Weekday[]): boolean {
  return weekdays.includes(weekdayOf(date, timezone))
}

function weeksBetween(startDate: string, candidate: string): number {
  const start = Date.parse(`${startDate}T12:00:00Z`)
  const end = Date.parse(`${candidate}T12:00:00Z`)
  return Math.floor((end - start) / (7 * 24 * 60 * 60 * 1000))
}

function monthsBetween(startDate: string, candidate: string): number {
  const [sy, sm] = startDate.split('-').map(Number)
  const [cy, cm] = candidate.split('-').map(Number)
  return (cy! - sy!) * 12 + (cm! - sm!)
}

function isCandidate(
  event: Event,
  rule: RecurrenceRule,
  date: string,
): boolean {
  const timezone = event.timezone
  const seriesStart = dateKey(event.startAt, timezone)
  if (date < seriesStart) return false

  const interval = Math.max(1, rule.interval)

  switch (rule.frequency) {
    case 'daily': {
      const start = Date.parse(`${seriesStart}T12:00:00Z`)
      const current = Date.parse(`${date}T12:00:00Z`)
      const dayDiff = Math.floor((current - start) / (24 * 60 * 60 * 1000))
      return dayDiff % interval === 0
    }
    case 'weekly': {
      const weekdays = rule.weekdays.length > 0 ? rule.weekdays : [weekdayOf(seriesStart, timezone)]
      if (!matchesWeekdays(date, timezone, weekdays)) return false
      return weeksBetween(seriesStart, date) % interval === 0
    }
    case 'weekdays': {
      if (!matchesWeekdays(date, timezone, rule.weekdays)) return false
      return weeksBetween(seriesStart, date) % interval === 0
    }
    case 'monthly': {
      const dayOfMonth = rule.dayOfMonth ?? Number(seriesStart.slice(8, 10))
      const [year, month] = date.split('-').map(Number)
      if (Number(date.slice(8, 10)) !== clampDayOfMonth(year!, month!, dayOfMonth)) return false
      return monthsBetween(seriesStart, date) % interval === 0
    }
    default:
      return false
  }
}

function applyExceptionToProjection(
  base: Event,
  occurrenceKey: string,
  startAt: string,
  endAt: string,
  exception: EventException | undefined,
): OccurrenceProjection | undefined {
  if (exception?.type === 'cancelled') return undefined
  const projectedStart = exception?.overrideStartAt ?? startAt
  const projectedEnd = exception?.overrideEndAt ?? endAt
  return {
    seriesEventId: base.id,
    occurrenceKey,
    event: {
      ...base,
      id: `${base.id}::${occurrenceKey}`,
      startAt: projectedStart,
      endAt: projectedEnd,
    },
  }
}

/**
 * Generate occurrences for a bounded visible range. Never materializes an infinite series.
 */
export function generateOccurrences(
  event: Event,
  rule: RecurrenceRule,
  exceptions: EventException[],
  rangeStart: string,
  rangeEnd: string,
): OccurrenceProjection[] {
  if (rangeEnd < rangeStart) {
    throw new Error('rangeEnd must be on or after rangeStart')
  }
  validateRecurrenceRule(rule)

  const timezone = event.timezone
  const seriesStart = dateKey(event.startAt, timezone)
  const time = localTimeOf(event.startAt, timezone)
  const durationMs = Date.parse(event.endAt) - Date.parse(event.startAt)
  const exceptionByKey = new Map(exceptions.filter((item) => item.eventId === event.id).map((item) => [item.occurrenceKey, item]))

  const results: OccurrenceProjection[] = []
  let emitted = 0
  let cursor = seriesStart
  // Hard bound: stop scanning far past the visible window (and past untilDate when set).
  const scanEnd = rule.untilDate !== undefined && rule.untilDate < rangeEnd ? rule.untilDate : rangeEnd
  const maxScanDays = Math.max(1, Math.floor((Date.parse(`${scanEnd}T12:00:00Z`) - Date.parse(`${seriesStart}T12:00:00Z`)) / 86_400_000) + 2)
  let scanned = 0

  while (cursor <= scanEnd && scanned <= maxScanDays) {
    if (isCandidate(event, rule, cursor)) {
      emitted += 1
      if (rule.occurrenceCount !== undefined && emitted > rule.occurrenceCount) break
      if (rule.untilDate !== undefined && cursor > rule.untilDate) break

      if (cursor >= rangeStart && cursor <= rangeEnd) {
        const startAt = buildOccurrenceStart(cursor, time, timezone)
        const endAt = new Date(Date.parse(startAt) + durationMs).toISOString()
        const key = makeOccurrenceKey(startAt, timezone)
        const projection = applyExceptionToProjection(event, key, startAt, endAt, exceptionByKey.get(key))
        if (projection !== undefined) results.push(projection)
      }
    }
    cursor = addDaysIso(cursor, 1)
    scanned += 1
  }

  return results
}

export function expandEventsInRange(
  events: Event[],
  rules: RecurrenceRule[],
  exceptions: EventException[],
  rangeStart: string,
  rangeEnd: string,
): Event[] {
  const ruleById = new Map(rules.map((rule) => [rule.id, rule]))
  const visible: Event[] = []

  for (const event of events) {
    if (event.deletedAt !== undefined) continue
    if (event.recurrenceRuleId === undefined) {
      const start = dateKey(event.startAt, event.timezone)
      const end = dateKey(event.endAt, event.timezone)
      if (start <= rangeEnd && end >= rangeStart) visible.push(event)
      continue
    }
    const rule = ruleById.get(event.recurrenceRuleId)
    if (rule === undefined) continue
    for (const occurrence of generateOccurrences(event, rule, exceptions, rangeStart, rangeEnd)) {
      visible.push(occurrence.event)
    }
  }

  return visible.sort((left, right) => left.startAt.localeCompare(right.startAt))
}

export function parseOccurrenceId(id: string): { seriesEventId: string; occurrenceKey?: string } {
  const separator = id.indexOf('::')
  if (separator === -1) return { seriesEventId: id }
  return { seriesEventId: id.slice(0, separator), occurrenceKey: id.slice(separator + 2) }
}

export async function upsertCancelledException(
  exceptions: EntityRepository<EventException>,
  params: { eventId: string; recurrenceRuleId: string; occurrenceKey: string; now: string },
): Promise<EventException> {
  const existing = (await exceptions.list()).find(
    (item) => item.eventId === params.eventId && item.occurrenceKey === params.occurrenceKey,
  )
  const exception: EventException = {
    id: existing?.id ?? createId(),
    eventId: params.eventId,
    recurrenceRuleId: params.recurrenceRuleId,
    occurrenceKey: params.occurrenceKey,
    type: 'cancelled',
    createdAt: existing?.createdAt ?? params.now,
    updatedAt: params.now,
  }
  validateEventException(exception)
  await exceptions.put(exception)
  return exception
}

export async function upsertModifiedException(
  exceptions: EntityRepository<EventException>,
  params: {
    eventId: string
    recurrenceRuleId: string
    occurrenceKey: string
    overrideStartAt: string
    overrideEndAt: string
    now: string
  },
): Promise<EventException> {
  const existing = (await exceptions.list()).find(
    (item) => item.eventId === params.eventId && item.occurrenceKey === params.occurrenceKey,
  )
  const exception: EventException = {
    id: existing?.id ?? createId(),
    eventId: params.eventId,
    recurrenceRuleId: params.recurrenceRuleId,
    occurrenceKey: params.occurrenceKey,
    type: 'modified',
    overrideStartAt: params.overrideStartAt,
    overrideEndAt: params.overrideEndAt,
    createdAt: existing?.createdAt ?? params.now,
    updatedAt: params.now,
  }
  validateEventException(exception)
  await exceptions.put(exception)
  return exception
}

/**
 * Next due date after a completed rolling task occurrence (ADR-015).
 * Returns undefined when the series has ended (untilDate / no further match).
 */
export function nextDueDateAfter(
  dueDate: string,
  rule: RecurrenceRule,
  timezone = 'UTC',
): string | undefined {
  validateRecurrenceRule(rule)
  const interval = Math.max(1, rule.interval)
  let next: string | undefined

  switch (rule.frequency) {
    case 'daily':
      next = addDaysIso(dueDate, interval)
      break
    case 'monthly': {
      const dayOfMonth = rule.dayOfMonth ?? Number(dueDate.slice(8, 10))
      const [year, month] = dueDate.split('-').map(Number)
      let y = year!
      let m = month! + interval
      while (m > 12) {
        m -= 12
        y += 1
      }
      const day = clampDayOfMonth(y, m, dayOfMonth)
      next = `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`
      break
    }
    case 'weekly':
    case 'weekdays': {
      const weekdays = rule.weekdays.length > 0
        ? rule.weekdays
        : rule.frequency === 'weekdays'
          ? ([1, 2, 3, 4, 5] as Weekday[])
          : [weekdayOf(dueDate, timezone)]
      let cursor = addDaysIso(dueDate, 1)
      const maxScan = interval * 14 + 7
      for (let i = 0; i < maxScan; i += 1) {
        if (matchesWeekdays(cursor, timezone, weekdays) && weeksBetween(dueDate, cursor) % interval === 0) {
          next = cursor
          break
        }
        cursor = addDaysIso(cursor, 1)
      }
      break
    }
    default:
      return undefined
  }

  if (next === undefined) return undefined
  if (rule.untilDate !== undefined && next > rule.untilDate) return undefined
  return next
}

export function splitRuleAtOccurrence(
  rule: RecurrenceRule,
  occurrenceDate: string,
  now: string,
): { historical: RecurrenceRule; following: RecurrenceRule } {
  const dayBefore = addDaysIso(occurrenceDate, -1)
  const historical: RecurrenceRule = {
    ...rule,
    untilDate: rule.untilDate !== undefined && rule.untilDate < dayBefore ? rule.untilDate : dayBefore,
    occurrenceCount: undefined,
    updatedAt: now,
  }
  const following: RecurrenceRule = {
    ...rule,
    id: createId(),
    createdAt: now,
    updatedAt: now,
  }
  return { historical, following }
}
