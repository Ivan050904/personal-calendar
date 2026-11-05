import { calendarTransport } from './api-repositories'

/** Calendar as served by /api/v2/calendars (D36). */
export interface CalendarV2 {
  id: string; name: string; kind: 'personal' | 'user' | 'app'; color: string; visible: boolean
  sort_order: number; timezone: string; source_client_id: string | null; revision: number
}

export function listCalendars(): Promise<CalendarV2[]> {
  return calendarTransport('/api/v2/calendars')
}
export function createCalendar(body: { name: string; color?: string }): Promise<CalendarV2> {
  return calendarTransport('/api/v2/calendars', { method: 'POST', body: JSON.stringify(body) })
}
export function patchCalendar(id: string, body: Partial<Pick<CalendarV2, 'name' | 'color' | 'visible' | 'sort_order'>>): Promise<CalendarV2> {
  return calendarTransport(`/api/v2/calendars/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify(body) })
}
export function deleteCalendar(id: string): Promise<{ id: string; deleted: boolean }> {
  return calendarTransport(`/api/v2/calendars/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

/**
 * Calendars the board overlays. Empty until App loads the list; then readers
 * fall back to the primary calendar only, which is the pre-D36 behaviour.
 */
let overlay: CalendarV2[] = []
export function setOverlayCalendars(calendars: CalendarV2[]): void {
  overlay = calendars
}
export function overlayTargets(primaryId: string): { id: string; color?: string }[] {
  if (overlay.length === 0) return [{ id: primaryId }]
  // Primary calendar keeps per-event colours; other calendars paint their events in the calendar colour.
  return overlay.filter(c => c.visible).map(c => (c.id === primaryId ? { id: c.id } : { id: c.id, color: c.color }))
}
