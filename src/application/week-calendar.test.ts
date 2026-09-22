import { describe, expect, it } from 'vitest'
import type { Event } from '../domain/models'
import { addDays, mondayOf, weekSegments } from './week-calendar'

const event = (id: string, startAt: string, endAt: string): Event => ({ id, calendarId: 'c', title: id, description: '', startAt, endAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: startAt, updatedAt: startAt })

describe('week calendar layout', () => {
  it('starts weeks on Monday and navigates by seven days', () => {
    expect(mondayOf('2026-09-17')).toBe('2026-09-14')
    expect(addDays('2026-09-14', 7)).toBe('2026-09-21')
  })
  it('creates a segment in every relevant day and separates overlaps', () => {
    const segments = weekSegments([
      event('multi', '2026-09-15T23:00:00.000Z', '2026-09-17T01:00:00.000Z'),
      event('overlap', '2026-09-16T10:00:00.000Z', '2026-09-16T11:00:00.000Z'),
      event('overlap-2', '2026-09-16T10:30:00.000Z', '2026-09-16T11:30:00.000Z'),
    ], '2026-09-14', 'UTC')
    expect(segments.filter((segment) => segment.event.id === 'multi')).toHaveLength(3)
    const wednesday = segments.filter((segment) => segment.date === '2026-09-16')
    expect(new Set(wednesday.map((segment) => segment.column)).size).toBe(3)
    expect(wednesday.every((segment) => segment.columns === 3)).toBe(true)
  })

  it('positions events by local timezone wall time, not UTC hours', () => {
    // 18:00 Asia/Vladivostok == 08:00 UTC
    const friday: Event = {
      ...event('evening', '2026-09-18T08:00:00.000Z', '2026-09-18T09:00:00.000Z'),
      timezone: 'Asia/Vladivostok',
    }
    const segments = weekSegments([friday], '2026-09-14', 'Asia/Vladivostok')
    const placed = segments.find((segment) => segment.date === '2026-09-18')
    expect(placed?.top).toBe(18 * 64)
  })
})
