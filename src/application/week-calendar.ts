import type { Event } from '../domain/models'
import { dateKey, zonedInputToIso } from './day-calendar'

export interface WeekSegment { event: Event; date: string; top: number; height: number; column: number; columns: number }

export function mondayOf(date: string): string {
  const value = new Date(`${date}T12:00:00Z`)
  const weekday = (value.getUTCDay() + 6) % 7
  value.setUTCDate(value.getUTCDate() - weekday)
  return value.toISOString().slice(0, 10)
}

export function addDays(date: string, days: number): string {
  const value = new Date(`${date}T12:00:00Z`)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

function zonedHourMinute(value: string, timezone: string): { hour: number; minute: number } {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(new Date(value)).filter((part) => part.type !== 'literal').map((part) => [part.type, part.value]),
  )
  return { hour: Number(parts.hour ?? '0'), minute: Number(parts.minute ?? '0') }
}

export function weekSegments(events: Event[], weekStart: string, timezone: string): WeekSegment[] {
  const raw = events.flatMap((event) => {
    const zone = event.timezone || timezone
    const start = dateKey(event.startAt, zone)
    const end = dateKey(event.endAt, zone)
    return Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))
      .filter((date) => date >= start && date <= end)
      .map((date) => {
        const segmentStart = date === start ? event.startAt : zonedInputToIso(`${date}T00:00`, zone)
        const segmentEnd = date === end ? event.endAt : zonedInputToIso(`${date}T23:59`, zone)
        const { hour, minute } = zonedHourMinute(segmentStart, zone)
        const top = hour * 64 + minute / 60 * 64
        return {
          event,
          date,
          top,
          height: Math.max(28, (Date.parse(segmentEnd) - Date.parse(segmentStart)) / 3_600_000 * 64),
          column: 0,
          columns: 1,
        }
      })
  })
  for (const date of Array.from(new Set(raw.map((segment) => segment.date)))) {
    const group = raw.filter((segment) => segment.date === date).sort((a, b) => a.top - b.top)
    const active: WeekSegment[] = []
    for (const segment of group) {
      for (let index = active.length - 1; index >= 0; index -= 1) if (active[index]!.top + active[index]!.height <= segment.top) active.splice(index, 1)
      segment.column = active.length
      active.push(segment)
      const columns = active.length
      for (const item of active) item.columns = Math.max(item.columns, columns)
    }
  }
  return raw
}
