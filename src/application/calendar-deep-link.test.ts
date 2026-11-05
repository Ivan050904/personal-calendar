import { expect, it } from 'vitest'

it('resolves exact target and rejects a different calendar', async () => {
  const { resolveCalendarTarget } = await import('./calendar-deep-link')
  expect(resolveCalendarTarget(new URLSearchParams('calendar_id=own&kind=task&entity_id=t&occurrence_key=2026-10-01'), 'own')).toEqual({ calendarId: 'own', kind: 'task', entityId: 't', occurrenceKey: '2026-10-01' })
  expect(() => resolveCalendarTarget(new URLSearchParams('calendar_id=bob&kind=event&entity_id=e'), 'own')).toThrow()
})
