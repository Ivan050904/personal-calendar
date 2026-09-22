import { describe, expect, it } from 'vitest'
import type { Event, Plan } from '../domain/models'
import { buildSmartDaySnapshot, formatDuration } from './smart-day'

const baseEvent = (overrides: Partial<Event>): Event => ({
  id: 'e1',
  calendarId: 'c',
  title: 'Meeting',
  description: '',
  startAt: '2026-09-18T10:00:00.000Z',
  endAt: '2026-09-18T11:00:00.000Z',
  timezone: 'UTC',
  allDay: false,
  color: '#0f766e',
  createdAt: '',
  updatedAt: '',
  ...overrides,
})

const basePlan = (overrides: Partial<Plan>): Plan => ({
  id: 'p1',
  calendarId: 'c',
  title: 'Deep work',
  startAt: '2026-09-18T12:00:00.000Z',
  endAt: '2026-09-18T14:00:00.000Z',
  timezone: 'UTC',
  color: '#333',
  createdAt: '',
  updatedAt: '',
  ...overrides,
})

describe('smart day', () => {
  it('reports free time and next block', () => {
    const snapshot = buildSmartDaySnapshot(
      [baseEvent({})],
      [basePlan({})],
      '2026-09-18T09:00:00.000Z',
    )
    expect(snapshot.status).toBe('free')
    expect(snapshot.label).toBe('Сейчас свободно')
    expect(snapshot.current).toBeNull()
    expect(snapshot.next?.title).toBe('Meeting')
  })

  it('reports current event with elapsed and remaining', () => {
    const snapshot = buildSmartDaySnapshot(
      [baseEvent({})],
      [],
      '2026-09-18T10:20:00.000Z',
    )
    expect(snapshot.status).toBe('busy')
    expect(snapshot.current?.title).toBe('Meeting')
    expect(snapshot.elapsedMs).toBe(20 * 60_000)
    expect(snapshot.remainingMs).toBe(40 * 60_000)
    expect(formatDuration(snapshot.elapsedMs!)).toBe('20 мин')
  })

  it('ignores all-day events for current activity', () => {
    const snapshot = buildSmartDaySnapshot(
      [baseEvent({ allDay: true, title: 'Holiday' })],
      [],
      '2026-09-18T10:20:00.000Z',
    )
    expect(snapshot.status).toBe('free')
    expect(snapshot.current).toBeNull()
  })

  it('keeps overlapping blocks visible without inventing priority beyond start order', () => {
    const snapshot = buildSmartDaySnapshot(
      [
        baseEvent({ id: 'a', title: 'A', startAt: '2026-09-18T10:00:00.000Z', endAt: '2026-09-18T11:00:00.000Z' }),
        baseEvent({ id: 'b', title: 'B', startAt: '2026-09-18T10:15:00.000Z', endAt: '2026-09-18T11:15:00.000Z' }),
      ],
      [],
      '2026-09-18T10:30:00.000Z',
    )
    expect(snapshot.current?.id).toBe('a')
    expect(snapshot.overlaps.map((item) => item.id)).toEqual(['a', 'b'])
  })
})
