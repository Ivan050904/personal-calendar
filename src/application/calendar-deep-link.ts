export interface CalendarTarget { calendarId: string; kind: 'event' | 'task' | 'plan'; entityId: string; occurrenceKey?: string }
export function resolveCalendarTarget(params: URLSearchParams, ownCalendarId: string): CalendarTarget | undefined {
  if (!params.has('entity_id')) return undefined
  const kind = params.get('kind')
  const calendarId = params.get('calendar_id')
  const entityId = params.get('entity_id')
  if (calendarId !== ownCalendarId || !entityId || !['event', 'plan', 'task'].includes(kind ?? '')) throw new Error('Запись недоступна')
  return { calendarId, kind: kind as CalendarTarget['kind'], entityId, occurrenceKey: params.get('occurrence_key') ?? undefined }
}
