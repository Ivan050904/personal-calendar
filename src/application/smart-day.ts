import type { Event, Plan } from '../domain/models'

export type TimedKind = 'event' | 'plan'

export interface TimedBlock {
  kind: TimedKind
  id: string
  title: string
  startAt: string
  endAt: string
  color: string
}

export interface SmartDaySnapshot {
  now: string
  status: 'busy' | 'free'
  label: string
  current: TimedBlock | null
  next: TimedBlock | null
  elapsedMs: number | null
  remainingMs: number | null
  overlaps: TimedBlock[]
}

function toBlock(kind: TimedKind, item: Event | Plan): TimedBlock {
  return {
    kind,
    id: item.id,
    title: item.title,
    startAt: item.startAt,
    endAt: item.endAt,
    color: item.color,
  }
}

function isActiveTimedEvent(event: Event): boolean {
  return event.deletedAt === undefined && !event.allDay
}

function isActivePlan(plan: Plan): boolean {
  return plan.deletedAt === undefined
}

/** Build Smart Day view from timed Events + Plans. All-day events and tasks are ignored. */
export function buildSmartDaySnapshot(
  events: Event[],
  plans: Plan[],
  nowIso: string,
): SmartDaySnapshot {
  const nowMs = Date.parse(nowIso)
  const blocks: TimedBlock[] = [
    ...events.filter(isActiveTimedEvent).map((event) => toBlock('event', event)),
    ...plans.filter(isActivePlan).map((plan) => toBlock('plan', plan)),
  ].sort((left, right) => left.startAt.localeCompare(right.startAt) || left.endAt.localeCompare(right.endAt))

  const overlaps = blocks.filter((block) => {
    const start = Date.parse(block.startAt)
    const end = Date.parse(block.endAt)
    return start <= nowMs && nowMs < end
  })

  const current = overlaps[0] ?? null
  const next =
    blocks
      .filter((block) => Date.parse(block.startAt) > nowMs)
      .sort((left, right) => left.startAt.localeCompare(right.startAt))[0] ?? null

  if (current === null) {
    return {
      now: nowIso,
      status: 'free',
      label: 'Сейчас свободно',
      current: null,
      next,
      elapsedMs: null,
      remainingMs: null,
      overlaps: [],
    }
  }

  const startMs = Date.parse(current.startAt)
  const endMs = Date.parse(current.endAt)
  return {
    now: nowIso,
    status: 'busy',
    label: current.title,
    current,
    next,
    elapsedMs: Math.max(0, nowMs - startMs),
    remainingMs: Math.max(0, endMs - nowMs),
    overlaps,
  }
}

export function formatDuration(ms: number): string {
  const totalMinutes = Math.floor(ms / 60_000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${minutes} мин`
  if (minutes === 0) return `${hours} ч`
  return `${hours} ч ${minutes} мин`
}
