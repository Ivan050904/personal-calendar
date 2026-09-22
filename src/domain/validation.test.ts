import { describe, expect, it } from 'vitest'
import type { Event, RecurrenceRule } from './models'
import { ValidationError, validateEvent, validateRecurrenceRule } from './validation'

const event: Event = {
  id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34',
  calendarId: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  title: 'Planning',
  description: '',
  startAt: '2026-09-17T09:00:00+10:00',
  endAt: '2026-09-17T10:00:00+10:00',
  timezone: 'Asia/Vladivostok',
  allDay: false,
  color: '#000000',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
}

describe('domain validation', () => {
  it('accepts a timed event with an end after its start', () => {
    expect(() => validateEvent(event)).not.toThrow()
  })

  it('rejects an event whose end is not after its start', () => {
    expect(() => validateEvent({ ...event, endAt: event.startAt })).toThrow(ValidationError)
  })

  it('requires weekdays for a selected-weekdays recurrence', () => {
    const recurrence: RecurrenceRule = {
      id: 'a20ba02e-660f-48ef-880c-d5c43adff5aa',
      frequency: 'weekdays',
      interval: 1,
      weekdays: [],
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    }
    expect(() => validateRecurrenceRule(recurrence)).toThrow('requires at least one weekday')
  })
})
