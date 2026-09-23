export const HOUR_ROW_PX = 64
export const VISIBLE_HOURS_STORAGE_KEY = 'personal-calendar-visible-hours'

export interface VisibleHoursPreference {
  startHour: number
  endHour: number
}

export const DEFAULT_VISIBLE_HOURS: VisibleHoursPreference = {
  startHour: 0,
  endHour: 23,
}

export function clampHour(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(23, Math.max(0, Math.trunc(value)))
}

export function normalizeVisibleHoursPreference(
  value: Partial<VisibleHoursPreference> | null | undefined,
): VisibleHoursPreference {
  const startHour = clampHour(Number(value?.startHour ?? DEFAULT_VISIBLE_HOURS.startHour))
  const endHour = clampHour(Number(value?.endHour ?? DEFAULT_VISIBLE_HOURS.endHour))
  if (startHour <= endHour) return { startHour, endHour }
  return { startHour: endHour, endHour: startHour }
}

export function readVisibleHoursPreference(
  storage: Pick<Storage, 'getItem'> | null | undefined = typeof localStorage === 'undefined' ? undefined : localStorage,
): VisibleHoursPreference {
  try {
    const raw = storage?.getItem(VISIBLE_HOURS_STORAGE_KEY)
    if (!raw) return { ...DEFAULT_VISIBLE_HOURS }
    return normalizeVisibleHoursPreference(JSON.parse(raw) as Partial<VisibleHoursPreference>)
  } catch {
    return { ...DEFAULT_VISIBLE_HOURS }
  }
}

export function writeVisibleHoursPreference(
  preference: VisibleHoursPreference,
  storage: Pick<Storage, 'setItem'> | null | undefined = typeof localStorage === 'undefined' ? undefined : localStorage,
): void {
  const normalized = normalizeVisibleHoursPreference(preference)
  try {
    storage?.setItem(VISIBLE_HOURS_STORAGE_KEY, JSON.stringify(normalized))
  } catch {
    /* ignore quota / private mode */
  }
}

/** Hours H where the timed interval overlaps [H:00, H+1:00) in the given zone. */
export function occupiedHours(startAt: string, endAt: string, timezone: string): number[] {
  const start = zonedHourMinute(startAt, timezone)
  const end = zonedHourMinute(endAt, timezone)
  const startTotal = start.hour * 60 + start.minute
  let endTotal = end.hour * 60 + end.minute
  if (endTotal <= startTotal) endTotal = startTotal + 1
  const hours: number[] = []
  for (let minute = startTotal; minute < endTotal; minute += 60) {
    hours.push(Math.floor(minute / 60))
  }
  const lastHour = Math.floor((endTotal - 1) / 60)
  if (!hours.includes(lastHour)) hours.push(lastHour)
  return hours.filter((hour) => hour >= 0 && hour <= 23)
}

export function buildVisibleHours(
  preference: VisibleHoursPreference,
  forcedHours: Iterable<number> = [],
): number[] {
  const { startHour, endHour } = normalizeVisibleHoursPreference(preference)
  const set = new Set<number>()
  for (let hour = startHour; hour <= endHour; hour += 1) set.add(hour)
  for (const hour of forcedHours) {
    if (Number.isFinite(hour)) set.add(clampHour(hour))
  }
  return [...set].sort((a, b) => a - b)
}

export function displayOffsetPx(visibleHours: number[], hour: number, minute = 0): number {
  const index = visibleHours.indexOf(clampHour(hour))
  if (index < 0) return 0
  const clampedMinute = Math.min(59, Math.max(0, minute))
  return index * HOUR_ROW_PX + (clampedMinute / 60) * HOUR_ROW_PX
}

function zonedHourMinute(value: string, timezone: string): { hour: number; minute: number } {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(new Date(value))
      .filter((part) => part.type !== 'literal')
      .map((part) => [part.type, part.value]),
  )
  return { hour: Number(parts.hour ?? '0'), minute: Number(parts.minute ?? '0') }
}
