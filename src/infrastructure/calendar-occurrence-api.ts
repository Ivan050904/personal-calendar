import { calendarTransport } from './api-repositories'

export interface CalendarOccurrenceRead {
  id: string; calendar_id: string; entity_id: string; kind: 'event' | 'plan' | 'task'; occurrence_key: string | null
  title: string; description: string; start_at: string | null; end_at: string | null; timezone: string
  all_day: boolean; start_date: string | null; end_date_exclusive: string | null; due_date: string | null
  completed: boolean | null; revision: number; location: string | null; color: string | null
  confirmation_status: 'occurred' | 'not_occurred' | null; source_href: string; cancelled?: boolean
}
export interface AgendaRead {
  contract_version: 2; calendar_id: string; calendar_timezone: string; timezone: string; from_date: string; to_date: string
  items: CalendarOccurrenceRead[]; overdue_tasks: CalendarOccurrenceRead[]; undated_tasks: CalendarOccurrenceRead[]
  complete: boolean; next_cursor: string | null
  smart_day: { current: CalendarOccurrenceRead | null; next: CalendarOccurrenceRead | null; overlaps: CalendarOccurrenceRead[] } | null
}
export interface CalendarEntityRead extends Omit<CalendarOccurrenceRead, 'entity_id' | 'occurrence_key' | 'confirmation_status'> {
  created_at: string; updated_at: string; deleted_at: string | null
  recurrence: { frequency: 'daily' | 'weekly' | 'weekdays' | 'monthly'; interval: number; weekdays: number[]; day_of_month: number | null; until_date: string | null; occurrence_count: number | null } | null
}
export interface CalendarCommandResult { command_id: string; entity: CalendarEntityRead; confirmation: { id: string; revision: number } | null; replayed: boolean; change_cursor: string | null }

export function occurrencePage(calendarId: string, from: string, to: string, timezone: string, cursor?: string): Promise<AgendaRead> {
  const query = new URLSearchParams({ calendar_id: calendarId, from, to, timezone })
  if (cursor) query.set('cursor', cursor)
  return calendarTransport(`/api/occurrences?${query}`)
}
export function exactOccurrence(entityId: string, key?: string): Promise<CalendarOccurrenceRead> {
  const query = new URLSearchParams()
  if (key) query.set('occurrence_key', key)
  return calendarTransport(`/api/integration/v1/occurrences/${encodeURIComponent(entityId)}?${query}`)
}
export function entityDetail(kind: string, id: string): Promise<CalendarEntityRead> {
  return calendarTransport(`/api/integration/v1/entities/${kind}/${encodeURIComponent(id)}`)
}
export async function allOccurrencePages(calendarId: string, from: string, to: string, timezone: string): Promise<CalendarOccurrenceRead[]> {
  const result: CalendarOccurrenceRead[] = []
  // Month boards include 42 days; split into independently bounded <=31-day windows.
  let start = from
  while (start <= to) {
    const end = new Date(`${start}T12:00:00Z`)
    end.setUTCDate(end.getUTCDate() + 30)
    const stop = end.toISOString().slice(0, 10) < to ? end.toISOString().slice(0, 10) : to
    let cursor: string | undefined
    do {
      const page = await occurrencePage(calendarId, start, stop, timezone, cursor)
      result.push(...page.items)
      if (!page.complete && !page.next_cursor) throw new Error('Неполная проекция календаря')
      cursor = page.next_cursor ?? undefined
    } while (cursor)
    const next = new Date(`${stop}T12:00:00Z`); next.setUTCDate(next.getUTCDate() + 1); start = next.toISOString().slice(0, 10)
  }
  return [...new Map(result.map(item => [item.id, item])).values()]
}
export function sendCalendarCommand(body: Record<string, unknown>): Promise<CalendarCommandResult> {
  return calendarTransport('/api/commands', { method: 'POST', headers: { 'Idempotency-Key': String(body.command_id) }, body: JSON.stringify(body) })
}
