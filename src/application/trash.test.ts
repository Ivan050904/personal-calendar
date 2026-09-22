import { describe, expect, it } from 'vitest'
import type { Event } from '../domain/models'
import { collectTrash, isPurgeDue, purgeAtFrom, restoreEntity, softDeleteEntity } from './trash'

const event: Event = {
  id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34',
  calendarId: '1d76fb58-104a-4ffd-834a-e0cb9644af74',
  title: 'Old',
  description: '',
  startAt: '2026-09-17T09:00:00.000Z',
  endAt: '2026-09-17T10:00:00.000Z',
  timezone: 'UTC',
  allDay: false,
  color: '#000',
  createdAt: '2026-09-01T00:00:00.000Z',
  updatedAt: '2026-09-01T00:00:00.000Z',
}

describe('trash', () => {
  it('soft-deletes, exposes purgeAt after 30 days, and restores', () => {
    const deleted = softDeleteEntity(event, '2026-09-17T00:00:00.000Z')
    expect(deleted.deletedAt).toBe('2026-09-17T00:00:00.000Z')
    expect(purgeAtFrom(deleted.deletedAt!)).toBe('2026-10-17T00:00:00.000Z')
    const entries = collectTrash('event', [deleted, event])
    expect(entries).toHaveLength(1)
    expect(isPurgeDue(entries[0]!, '2026-10-17T00:00:00.000Z')).toBe(true)
    expect(isPurgeDue(entries[0]!, '2026-10-16T00:00:00.000Z')).toBe(false)
    const restored = restoreEntity(deleted, '2026-09-18T00:00:00.000Z')
    expect(restored.deletedAt).toBeUndefined()
    expect(restored.updatedAt).toBe('2026-09-18T00:00:00.000Z')
  })
})
