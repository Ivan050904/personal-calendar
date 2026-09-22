import { describe, expect, it } from 'vitest'
import type { Event, EventException, RecurrenceRule } from '../domain/models'
import {
  clampDayOfMonth,
  generateOccurrences,
  makeOccurrenceKey,
  splitRuleAtOccurrence,
} from './recurrence'

const baseEvent: Event = {
  id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34',
  calendarId: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  title: 'Standup',
  description: '',
  startAt: '2026-09-16T23:00:00.000Z', // 09:00 Asia/Vladivostok
  endAt: '2026-09-16T23:30:00.000Z',
  timezone: 'Asia/Vladivostok',
  allDay: false,
  color: '#2563eb',
  recurrenceRuleId: 'a20ba02e-660f-48ef-880c-d5c43adff5aa',
  createdAt: '2026-09-17T00:00:00.000Z',
  updatedAt: '2026-09-17T00:00:00.000Z',
}

function rule(partial: Partial<RecurrenceRule> & Pick<RecurrenceRule, 'frequency'>): RecurrenceRule {
  return {
    id: 'a20ba02e-660f-48ef-880c-d5c43adff5aa',
    interval: 1,
    weekdays: [],
    createdAt: '2026-09-17T00:00:00.000Z',
    updatedAt: '2026-09-17T00:00:00.000Z',
    ...partial,
  }
}

describe('recurrence generation', () => {
  it('generates daily occurrences inside a bounded range', () => {
    const occurrences = generateOccurrences(baseEvent, rule({ frequency: 'daily' }), [], '2026-09-17', '2026-09-19')
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-09-17T09:00',
      '2026-09-18T09:00',
      '2026-09-19T09:00',
    ])
  })

  it('generates weekly occurrences on the series weekday', () => {
    const occurrences = generateOccurrences(baseEvent, rule({ frequency: 'weekly' }), [], '2026-09-17', '2026-10-08')
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-09-17T09:00',
      '2026-09-24T09:00',
      '2026-10-01T09:00',
      '2026-10-08T09:00',
    ])
  })

  it('generates selected-weekday occurrences', () => {
    const occurrences = generateOccurrences(
      baseEvent,
      rule({ frequency: 'weekdays', weekdays: [1, 3, 5] }),
      [],
      '2026-09-17',
      '2026-09-26',
    )
    // Series starts Thursday 2026-09-17; Mon/Wed/Fri in range begin Friday.
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-09-18T09:00',
      '2026-09-21T09:00',
      '2026-09-23T09:00',
      '2026-09-25T09:00',
    ])
  })

  it('generates monthly occurrences on day-of-month', () => {
    const event: Event = {
      ...baseEvent,
      startAt: '2026-01-14T23:00:00.000Z',
      endAt: '2026-01-14T23:30:00.000Z',
    }
    const occurrences = generateOccurrences(
      event,
      rule({ frequency: 'monthly', dayOfMonth: 15 }),
      [],
      '2026-01-01',
      '2026-04-30',
    )
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-01-15T09:00',
      '2026-02-15T09:00',
      '2026-03-15T09:00',
      '2026-04-15T09:00',
    ])
  })

  it('stops at untilDate inclusive', () => {
    const occurrences = generateOccurrences(
      baseEvent,
      rule({ frequency: 'daily', untilDate: '2026-09-18' }),
      [],
      '2026-09-17',
      '2026-09-30',
    )
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-09-17T09:00',
      '2026-09-18T09:00',
    ])
  })

  it('stops after occurrenceCount from series start', () => {
    const occurrences = generateOccurrences(
      baseEvent,
      rule({ frequency: 'daily', occurrenceCount: 2 }),
      [],
      '2026-09-17',
      '2026-09-30',
    )
    expect(occurrences).toHaveLength(2)
    expect(occurrences[1]?.occurrenceKey).toBe('2026-09-18T09:00')
  })

  it('applies a modified exception move', () => {
    const key = '2026-09-18T09:00'
    const exception: EventException = {
      id: '11111111-1111-4111-8111-111111111111',
      eventId: baseEvent.id,
      recurrenceRuleId: baseEvent.recurrenceRuleId!,
      occurrenceKey: key,
      type: 'modified',
      overrideStartAt: '2026-09-18T01:00:00.000Z', // 11:00 Vladivostok
      overrideEndAt: '2026-09-18T01:30:00.000Z',
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    }
    const occurrences = generateOccurrences(baseEvent, rule({ frequency: 'daily' }), [exception], '2026-09-18', '2026-09-18')
    expect(occurrences).toHaveLength(1)
    expect(occurrences[0]?.event.startAt).toBe('2026-09-18T01:00:00.000Z')
    expect(occurrences[0]?.event.endAt).toBe('2026-09-18T01:30:00.000Z')
  })

  it('applies a modified exception resize', () => {
    const key = '2026-09-18T09:00'
    const exception: EventException = {
      id: '22222222-2222-4222-8222-222222222222',
      eventId: baseEvent.id,
      recurrenceRuleId: baseEvent.recurrenceRuleId!,
      occurrenceKey: key,
      type: 'modified',
      overrideStartAt: '2026-09-17T23:00:00.000Z', // 09:00 on 2026-09-18
      overrideEndAt: '2026-09-18T02:00:00.000Z', // 12:00 local
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    }
    const occurrences = generateOccurrences(baseEvent, rule({ frequency: 'daily' }), [exception], '2026-09-18', '2026-09-18')
    expect(occurrences[0]?.event.startAt).toBe('2026-09-17T23:00:00.000Z')
    expect(occurrences[0]?.event.endAt).toBe('2026-09-18T02:00:00.000Z')
  })

  it('applies cancellation exceptions', () => {
    const key = '2026-09-18T09:00'
    const exception: EventException = {
      id: '33333333-3333-4333-8333-333333333333',
      eventId: baseEvent.id,
      recurrenceRuleId: baseEvent.recurrenceRuleId!,
      occurrenceKey: key,
      type: 'cancelled',
      createdAt: '2026-09-17T00:00:00.000Z',
      updatedAt: '2026-09-17T00:00:00.000Z',
    }
    const occurrences = generateOccurrences(baseEvent, rule({ frequency: 'daily' }), [exception], '2026-09-17', '2026-09-19')
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-09-17T09:00',
      '2026-09-19T09:00',
    ])
  })

  it('splits this-and-following by ending the historical rule before the selected date', () => {
    const original = rule({ frequency: 'daily', untilDate: '2026-09-30' })
    const { historical, following } = splitRuleAtOccurrence(original, '2026-09-20', '2026-09-19T00:00:00.000Z')
    expect(historical.untilDate).toBe('2026-09-19')
    expect(following.id).not.toBe(original.id)
    expect(following.untilDate).toBe('2026-09-30')
  })

  it('preserves local wall time across a DST spring-forward boundary', () => {
    const event: Event = {
      ...baseEvent,
      timezone: 'America/New_York',
      startAt: '2026-03-07T14:00:00.000Z', // 09:00 EST
      endAt: '2026-03-07T15:00:00.000Z',
    }
    const occurrences = generateOccurrences(event, rule({ frequency: 'daily' }), [], '2026-03-07', '2026-03-09')
    expect(occurrences.map((item) => makeOccurrenceKey(item.event.startAt, event.timezone))).toEqual([
      '2026-03-07T09:00',
      '2026-03-08T09:00',
      '2026-03-09T09:00',
    ])
    // 2026-03-08 is DST start in America/New_York; UTC offset shifts but local time stays 09:00.
    expect(occurrences[1]?.event.startAt).toBe('2026-03-08T13:00:00.000Z')
  })

  it('clamps month-end days to the last day of shorter months (ADR-012)', () => {
    expect(clampDayOfMonth(2026, 2, 31)).toBe(28)
    expect(clampDayOfMonth(2028, 2, 31)).toBe(29)
    expect(clampDayOfMonth(2026, 4, 31)).toBe(30)

    const event: Event = {
      ...baseEvent,
      startAt: '2026-01-30T23:00:00.000Z',
      endAt: '2026-01-30T23:30:00.000Z',
    }
    const occurrences = generateOccurrences(
      event,
      rule({ frequency: 'monthly', dayOfMonth: 31 }),
      [],
      '2026-01-01',
      '2026-04-30',
    )
    expect(occurrences.map((item) => item.occurrenceKey)).toEqual([
      '2026-01-31T09:00',
      '2026-02-28T09:00',
      '2026-03-31T09:00',
      '2026-04-30T09:00',
    ])
  })
})
