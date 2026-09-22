import type { CalendarEntity, Entity } from '../domain/models'

export const TRASH_RETENTION_DAYS = 30

export interface TrashEntry<T extends Entity = Entity> {
  entityType: string
  entity: T
  deletedAt: string
  purgeAt: string
}

export function purgeAtFrom(deletedAt: string, retentionDays = TRASH_RETENTION_DAYS): string {
  return new Date(Date.parse(deletedAt) + retentionDays * 86_400_000).toISOString()
}

export function isPurgeDue(entry: Pick<TrashEntry, 'purgeAt'>, nowIso: string): boolean {
  return Date.parse(entry.purgeAt) <= Date.parse(nowIso)
}

export function toTrashEntry<T extends Entity>(entityType: string, entity: T): TrashEntry<T> {
  if (entity.deletedAt === undefined) throw new Error('Entity is not soft-deleted')
  return {
    entityType,
    entity,
    deletedAt: entity.deletedAt,
    purgeAt: purgeAtFrom(entity.deletedAt),
  }
}

export function restoreEntity<T extends Entity>(entity: T, nowIso: string): T {
  const next = { ...entity, updatedAt: nowIso }
  delete next.deletedAt
  return next
}

export function collectTrash<T extends Entity>(entityType: string, entities: T[]): TrashEntry<T>[] {
  return entities
    .filter((entity) => entity.deletedAt !== undefined)
    .map((entity) => toTrashEntry(entityType, entity))
    .sort((left, right) => left.deletedAt.localeCompare(right.deletedAt))
}

export function filterActive<T extends Entity>(entities: T[]): T[] {
  return entities.filter((entity) => entity.deletedAt === undefined)
}

export function softDeleteEntity<T extends Entity>(entity: T, nowIso: string): T {
  return { ...entity, deletedAt: nowIso, updatedAt: nowIso }
}

export function assertSameCalendar<T extends CalendarEntity>(entity: T, calendarId: string): void {
  if (entity.calendarId !== calendarId) throw new Error('Entity calendar mismatch')
}
