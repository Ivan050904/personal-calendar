import { describe, expect, it } from 'vitest'
import type { Reminder } from '../domain/models'
import { dueReminders, LocalRemindersService, reminderFireAt, type ReminderRepository } from './reminders'

class MemoryReminders implements ReminderRepository {
  private readonly values = new Map<string, Reminder>()
  async get(id: string) { return this.values.get(id) }
  async list() { return [...this.values.values()] }
  async put(entity: Reminder) { this.values.set(entity.id, entity) }
  async delete(id: string) { this.values.delete(id) }
}

describe('reminders', () => {
  it('adds supported offsets and rejects duplicates', async () => {
    const service = new LocalRemindersService(new MemoryReminders(), () => '2026-09-17T00:00:00.000Z')
    const first = await service.add('event-1', 15)
    expect(first.offsetMinutes).toBe(15)
    await expect(service.add('event-1', 15)).rejects.toThrow('already exists')
    await expect(service.add('event-1', 7 as never)).rejects.toThrow('unsupported')
  })

  it('removes a reminder and computes due window', async () => {
    const repo = new MemoryReminders()
    const service = new LocalRemindersService(repo, () => '2026-09-17T00:00:00.000Z')
    const reminder = await service.add('event-1', 30)
    await service.remove(reminder.id)
    await expect(service.listForEvent('event-1')).resolves.toEqual([])

    expect(reminderFireAt('2026-09-17T10:00:00.000Z', 30)).toBe('2026-09-17T09:30:00.000Z')
    expect(dueReminders(
      [{ reminder: { ...reminder, id: 'r1' }, occurrenceStartAt: '2026-09-17T10:00:00.000Z' }],
      '2026-09-17T09:30:30.000Z',
    )).toHaveLength(1)
  })
})
