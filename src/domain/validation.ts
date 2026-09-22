import type { Event, EventException, Plan, RecurrenceRule } from './models'

export class ValidationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ValidationError'
  }
}

function isDateTime(value: string): boolean {
  return !Number.isNaN(Date.parse(value))
}

function requireText(value: string, field: string): void {
  if (value.trim().length === 0) {
    throw new ValidationError(`${field} is required`)
  }
}

function requireTimeRange(startAt: string, endAt: string): void {
  if (!isDateTime(startAt) || !isDateTime(endAt) || Date.parse(endAt) <= Date.parse(startAt)) {
    throw new ValidationError('endAt must be after startAt')
  }
}

export function validateEvent(event: Event): void {
  requireText(event.title, 'title')
  requireText(event.timezone, 'timezone')
  requireText(event.color, 'color')
  requireTimeRange(event.startAt, event.endAt)
}

export function validatePlan(plan: Plan): void {
  requireText(plan.title, 'title')
  requireText(plan.timezone, 'timezone')
  requireText(plan.color, 'color')
  requireTimeRange(plan.startAt, plan.endAt)
}

export function validateRecurrenceRule(rule: RecurrenceRule): void {
  if (!Number.isInteger(rule.interval) || rule.interval < 1) {
    throw new ValidationError('interval must be a positive integer')
  }
  if (rule.frequency === 'weekdays' && rule.weekdays.length === 0) {
    throw new ValidationError('weekdays frequency requires at least one weekday')
  }
  if (rule.frequency === 'monthly' && (rule.dayOfMonth === undefined || rule.dayOfMonth < 1 || rule.dayOfMonth > 31)) {
    throw new ValidationError('monthly frequency requires a dayOfMonth from 1 to 31')
  }
  if (rule.occurrenceCount !== undefined && (!Number.isInteger(rule.occurrenceCount) || rule.occurrenceCount < 1)) {
    throw new ValidationError('occurrenceCount must be a positive integer')
  }
}

export function validateEventException(exception: EventException): void {
  requireText(exception.occurrenceKey, 'occurrenceKey')
  if (exception.type === 'cancelled' && (exception.overrideStartAt !== undefined || exception.overrideEndAt !== undefined)) {
    throw new ValidationError('cancelled exceptions cannot have overrides')
  }
  if (exception.overrideStartAt !== undefined || exception.overrideEndAt !== undefined) {
    if (exception.overrideStartAt === undefined || exception.overrideEndAt === undefined) {
      throw new ValidationError('modified exception requires both override times')
    }
    requireTimeRange(exception.overrideStartAt, exception.overrideEndAt)
  }
}
