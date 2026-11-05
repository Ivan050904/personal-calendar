import { calendarTransport } from './api-repositories'
import type { CalendarOccurrenceRead } from './calendar-occurrence-api'

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

/** The signed-in account; `login` is null for accounts made through Folio or the old env login. */
export interface Account { id: string; login: string | null; display_name: string | null }
export function getMe(): Promise<Account> {
  return calendarTransport('/api/v2/me')
}
export function setCredentials(body: { login: string; password: string }): Promise<Account> {
  return calendarTransport('/api/v2/me/credentials', { method: 'POST', body: JSON.stringify(body) })
}

/** An event someone else invited this account to (D38). */
export type InvitationStatus = 'pending' | 'accepted' | 'declined'
export interface Invitation {
  id: string; event_id: string; status: InvitationStatus
  event: { id: string; title: string; start_at: string | null; start_date: string | null; timezone: string }
  organizer: { login: string | null; display_name: string | null }
}
export type InvitationOccurrence = CalendarOccurrenceRead & { invitation: { id: string; status: InvitationStatus } }
export function listInvitations(): Promise<Invitation[]> {
  return calendarTransport('/api/v2/invitations')
}
export function answerInvitation(eventId: string, status: 'accepted' | 'declined'): Promise<{ status: InvitationStatus }> {
  return calendarTransport(`/api/v2/events/${encodeURIComponent(eventId)}/attendees/me`, { method: 'PATCH', body: JSON.stringify({ status }) })
}
export async function invitationOccurrences(from: string, to: string, timezone: string): Promise<InvitationOccurrence[]> {
  const query = new URLSearchParams({ from, to, timezone })
  const page = await calendarTransport<{ items: InvitationOccurrence[] }>(`/api/v2/invitations/occurrences?${query}`)
  return page.items
}

/** An app the user connected via OAuth (D35). */
export interface AppGrant {
  id: string; client_id: string; client_name: string; scopes: string[]; readable_calendar_ids: string[]
  app_calendar_id: string | null; created_at: string; last_used_at: string | null
}
export function listGrants(): Promise<AppGrant[]> {
  return calendarTransport('/api/v2/grants')
}
export function revokeGrant(id: string): Promise<{ id: string; revoked: boolean }> {
  return calendarTransport(`/api/v2/grants/${encodeURIComponent(id)}`, { method: 'DELETE' })
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
