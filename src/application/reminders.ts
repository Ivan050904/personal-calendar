import { createId } from '../domain/ids'
import type { Reminder } from '../domain/models'
import { ValidationError } from '../domain/validation'
import type { EntityRepository } from './repositories'

/** MVP reminder offsets from docs/07_NOTIFICATIONS.md */
export const REMINDER_OFFSETS_MINUTES = [5, 15, 30, 60, 1440] as const
export type ReminderOffset = (typeof REMINDER_OFFSETS_MINUTES)[number]

export interface ReminderRepository extends EntityRepository<Reminder> {
  delete(id: string): Promise<void>
}

export class LocalRemindersService {
  constructor(
    private readonly reminders: ReminderRepository,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async listForEvent(eventId: string): Promise<Reminder[]> {
    return (await this.reminders.list())
      .filter((item) => item.eventId === eventId)
      .sort((left, right) => left.offsetMinutes - right.offsetMinutes)
  }

  async add(eventId: string, offsetMinutes: ReminderOffset): Promise<Reminder> {
    if (!(REMINDER_OFFSETS_MINUTES as readonly number[]).includes(offsetMinutes)) {
      throw new ValidationError('unsupported reminder offset')
    }
    const existing = await this.listForEvent(eventId)
    if (existing.some((item) => item.offsetMinutes === offsetMinutes)) {
      throw new ValidationError('reminder offset already exists')
    }
    const timestamp = this.now()
    const reminder: Reminder = {
      id: createId(),
      eventId,
      offsetMinutes,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    await this.reminders.put(reminder)
    return reminder
  }

  async remove(id: string): Promise<void> {
    const reminder = await this.reminders.get(id)
    if (reminder === undefined) throw new Error('Reminder not found')
    await this.reminders.delete(id)
  }
}

/**
 * Fire time for an occurrence start minus offset.
 * Browser tabs cannot guarantee delivery (permission + lifecycle limits).
 */
export function reminderFireAt(occurrenceStartAt: string, offsetMinutes: number): string {
  return new Date(Date.parse(occurrenceStartAt) - offsetMinutes * 60_000).toISOString()
}

export function dueReminders(
  items: Array<{ reminder: Reminder; occurrenceStartAt: string }>,
  nowIso: string,
  windowMinutes = 1,
): Reminder[] {
  const now = Date.parse(nowIso)
  const windowMs = windowMinutes * 60_000
  return items
    .filter(({ reminder, occurrenceStartAt }) => {
      const fire = Date.parse(reminderFireAt(occurrenceStartAt, reminder.offsetMinutes))
      return fire <= now && now - fire < windowMs
    })
    .map(({ reminder }) => reminder)
}
