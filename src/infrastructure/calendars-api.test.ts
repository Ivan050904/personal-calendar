import { afterEach, expect, it, vi } from 'vitest'
import type { Calendar } from '../domain/models'
import { overlayTargets, setOverlayCalendars, type CalendarV2 } from './calendars-api'

const base = { sort_order: 0, timezone: 'UTC', source_client_id: null, revision: 1 }
const personal: CalendarV2 = { ...base, id: 'p', name: 'Личное', kind: 'personal', color: '#0f766e', visible: true }
const sport: CalendarV2 = { ...base, id: 's', name: 'Спорт', kind: 'user', color: '#ff0000', visible: true }
const hidden: CalendarV2 = { ...base, id: 'h', name: 'Скрытый', kind: 'user', color: '#00ff00', visible: false }

afterEach(() => { setOverlayCalendars([]); vi.unstubAllGlobals() })

it('falls back to the primary calendar until the list is loaded', () => {
  expect(overlayTargets('p')).toEqual([{ id: 'p' }])
})

it('overlays visible calendars only and paints non-primary ones in their colour', () => {
  setOverlayCalendars([personal, sport, hidden])
  expect(overlayTargets('p')).toEqual([{ id: 'p' }, { id: 's', color: '#ff0000' }])
})

it('day board merges events of every visible calendar', async () => {
  setOverlayCalendars([personal, sport, hidden])
  const asked: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path.includes('/invitations/')) return { ok: true, status: 200, json: async () => ({ items: [] }) }
    const id = new URL(path, 'http://x').searchParams.get('calendar_id')!
    asked.push(id)
    return { ok: true, status: 200, json: async () => ({ complete: true, next_cursor: null, items: [{
      id: `e-${id}`, entity_id: `e-${id}`, calendar_id: id, kind: 'event', title: id, description: '', timezone: 'UTC',
      all_day: false, start_at: '2026-11-10T09:00:00Z', end_at: '2026-11-10T10:00:00Z', revision: 1, color: '#000000', location: null }] }) }
  }))
  const { ApiDayCalendarService } = await import('./api-calendar-services')
  const primary: Calendar = { id: 'p', name: 'Личное', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const events = await new ApiDayCalendarService(primary).listEvents('2026-11-10')
  expect(asked.sort()).toEqual(['p', 's'])
  expect(events.map(e => [e.calendarId, e.color]).sort()).toEqual([['p', '#000000'], ['s', '#ff0000']])
})

it('board shows invitations; pending ones greyed with ✉ until answered', async () => {
  const row = (id: string, status: string) => ({ id, entity_id: id, calendar_id: 'someone-else', kind: 'event', title: id, description: '',
    timezone: 'UTC', all_day: false, start_at: '2026-11-10T09:00:00Z', end_at: '2026-11-10T10:00:00Z', revision: 1, color: '#123456',
    location: null, invitation: { id: `a-${id}`, status } })
  vi.stubGlobal('fetch', vi.fn(async (path: string) => ({ ok: true, status: 200, json: async () => path.includes('/invitations/occurrences')
    ? { items: [row('ужин', 'pending'), row('кино', 'accepted')] }
    : { complete: true, next_cursor: null, items: [] } })))
  const { ApiDayCalendarService } = await import('./api-calendar-services')
  const primary: Calendar = { id: 'p', name: 'Личное', timezone: 'UTC', createdAt: '', updatedAt: '' }
  const events = await new ApiDayCalendarService(primary).listEvents('2026-11-10')
  expect(events.map(e => [e.title, e.color]).sort()).toEqual([['кино', '#123456'], ['✉ ужин', '#94a3b8']])
})

it('board still loads when the invitations request fails', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => path.includes('/invitations/')
    ? { ok: false, status: 500, json: async () => ({ error: { code: 'database_error', message: 'x' } }) }
    : { ok: true, status: 200, json: async () => ({ complete: true, next_cursor: null, items: [] }) }))
  const { ApiDayCalendarService } = await import('./api-calendar-services')
  const primary: Calendar = { id: 'p', name: 'Личное', timezone: 'UTC', createdAt: '', updatedAt: '' }
  expect(await new ApiDayCalendarService(primary).listEvents('2026-11-10')).toEqual([])
})

it('new event goes to the chosen calendar, primary needs no calendar_id', async () => {
  const bodies: Array<Record<string, unknown>> = []
  vi.stubGlobal('fetch', vi.fn(async (_path: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body))
    bodies.push(body)
    return { ok: true, status: 200, json: async () => ({ entity: { id: 'n', calendar_id: body.calendar_id ?? 'p', kind: 'event', title: 'x', description: '', timezone: 'UTC', all_day: false, start_at: '2026-11-10T09:00:00Z', end_at: '2026-11-10T10:00:00Z', revision: 1, color: '#000', location: null, created_at: '', updated_at: '', deleted_at: null, recurrence: null }, confirmation: null }) }
  }))
  const { ApiDayCalendarService } = await import('./api-calendar-services')
  const service = new ApiDayCalendarService({ id: 'p', name: 'Личное', timezone: 'UTC', createdAt: '', updatedAt: '' })
  const draft = { title: 'x', description: '', startAt: '2026-11-10T09:00:00Z', endAt: '2026-11-10T10:00:00Z', color: '#000' }
  await service.createEvent({ ...draft, calendarId: 's' })
  await service.createEvent({ ...draft, calendarId: 'p' })
  await service.createEvent(draft)
  expect(bodies.map(b => b.calendar_id)).toEqual(['s', undefined, undefined])
})
