import { describe, expect, it } from 'vitest'
import {
  buildVisibleHours,
  displayOffsetPx,
  HOUR_ROW_PX,
  normalizeVisibleHoursPreference,
  occupiedHours,
  readVisibleHoursPreference,
  writeVisibleHoursPreference,
} from './visible-hours'

describe('normalizeVisibleHoursPreference', () => {
  it('defaults to full day and swaps inverted range', () => {
    expect(normalizeVisibleHoursPreference(undefined)).toEqual({ startHour: 0, endHour: 23 })
    expect(normalizeVisibleHoursPreference({ startHour: 22, endHour: 7 })).toEqual({
      startHour: 7,
      endHour: 22,
    })
  })
})

describe('buildVisibleHours', () => {
  it('keeps preferred range and forces event / now hours outside it', () => {
    expect(buildVisibleHours({ startHour: 7, endHour: 23 }, [1, 2])).toEqual([
      1, 2, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
    ])
    expect(buildVisibleHours({ startHour: 3, endHour: 23 })).toEqual(
      Array.from({ length: 21 }, (_, index) => index + 3),
    )
  })
})

describe('occupiedHours', () => {
  it('lists hours overlapped by an interval', () => {
    expect(occupiedHours('2026-09-17T09:00:00.000Z', '2026-09-17T10:00:00.000Z', 'UTC')).toEqual([9])
    expect(occupiedHours('2026-09-17T05:00:00.000Z', '2026-09-17T08:00:00.000Z', 'UTC')).toEqual([5, 6, 7])
    expect(occupiedHours('2026-09-17T01:30:00.000Z', '2026-09-17T02:15:00.000Z', 'UTC')).toEqual([1, 2])
  })
})

describe('displayOffsetPx', () => {
  it('remaps tops into the compressed hour list', () => {
    const visible = buildVisibleHours({ startHour: 7, endHour: 23 }, [1])
    expect(displayOffsetPx(visible, 1)).toBe(0)
    expect(displayOffsetPx(visible, 7)).toBe(HOUR_ROW_PX)
    expect(displayOffsetPx(visible, 8, 30)).toBe(2 * HOUR_ROW_PX + HOUR_ROW_PX / 2)
  })
})

describe('visible hours preference storage', () => {
  it('round-trips through a storage stub', () => {
    const store = new Map<string, string>()
    const storage = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => { store.set(key, value) },
    }
    writeVisibleHoursPreference({ startHour: 3, endHour: 22 }, storage)
    expect(readVisibleHoursPreference(storage)).toEqual({ startHour: 3, endHour: 22 })
  })
})
