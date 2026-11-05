import { expect, it } from 'vitest'
import { zonedInputToIso } from './day-calendar'
import { generateOccurrences } from './recurrence'
import type { Event, RecurrenceRule } from '../domain/models'

it('Berlin fall week spans 169 UTC hours', () => {
  expect((Date.parse(zonedInputToIso('2026-10-26T00:00', 'Europe/Berlin')) - Date.parse(zonedInputToIso('2026-10-19T00:00', 'Europe/Berlin'))) / 3600000).toBe(169)
})
it('standalone recurrence skips DST gap without consuming count and chooses earlier fold', () => {
  const event: Event = { id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: '1d76fb58-104a-4ffd-834a-e0cb9644af74', title: 'DST', description: '', startAt: '2026-03-28T01:30:00Z', endAt: '2026-03-28T02:30:00Z', timezone: 'Europe/Berlin', allDay: false, color: '#000', createdAt: '', updatedAt: '' }
  const rule: RecurrenceRule = { id: 'a20ba02e-660f-48ef-880c-d5c43adff5aa', frequency: 'daily', interval: 1, weekdays: [], occurrenceCount: 2, createdAt: '', updatedAt: '' }
  expect(generateOccurrences(event, rule, [], '2026-03-28', '2026-03-30').map(item => item.event.startAt)).toEqual(['2026-03-28T01:30:00.000Z', '2026-03-30T00:30:00.000Z'])
  const fall = { ...event, startAt: '2026-10-24T00:30:00Z', endAt: '2026-10-24T01:30:00Z' }
  expect(generateOccurrences(fall, rule, [], '2026-10-25', '2026-10-25')[0]?.event.startAt).toBe('2026-10-25T00:30:00.000Z')
})
