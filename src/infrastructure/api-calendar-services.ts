import type { Calendar, Event, Plan, Task } from '../domain/models'
import type { DayCalendarService, EventDraft } from '../application/day-calendar'
import { dateKey, zonedInputToIso } from '../application/day-calendar'
import { parseOccurrenceId, type EditScope, type DeleteScope, type RecurrenceDraft } from '../application/recurrence'
import { LocalTasksService, type TaskDraft, type TaskActionSnapshot } from '../application/tasks'
import { LocalPlansService, type PlanDraft } from '../application/plans'
import { allOccurrencePages, entityDetail, exactOccurrence, sendCalendarCommand, type CalendarEntityRead, type CalendarOccurrenceRead } from './calendar-occurrence-api'
import { calendarTransport } from './api-repositories'
import { invitationOccurrences, overlayTargets } from './calendars-api'

const PENDING_INVITATION_COLOR = '#94a3b8'

/** Occurrences of every visible calendar for the board (D36). */
async function overlayOccurrences(primary: Calendar, from: string, to: string, kind: 'event' | 'plan') {
  const pages = await Promise.all(overlayTargets(primary.id).map(async target => {
    const rows = (await allOccurrencePages(target.id, from, to, primary.timezone)).filter(row => row.kind === kind)
    return target.color ? rows.map(row => ({ ...row, color: target.color! })) : rows
  }))
  // D38: events others invited me to; until answered they show greyed out with ✉.
  const invited = kind === 'event' ? await invitationOccurrences(from, to, primary.timezone).catch(() => []) : []
  return [...pages.flat(), ...invited.map(row => row.invitation.status === 'pending'
    ? { ...row, title: `✉ ${row.title}`, color: PENDING_INVITATION_COLOR } : row)]
}

function recurrence(draft?: RecurrenceDraft) {
  return draft ? { frequency: draft.frequency, interval: draft.interval, weekdays: draft.weekdays, day_of_month: draft.dayOfMonth ?? null, until_date: draft.untilDate ?? null, occurrence_count: draft.occurrenceCount ?? null, dst_gap_policy: 'skip', dst_fold_policy: 'earlier' } : null
}
function timestamps(row: CalendarEntityRead | CalendarOccurrenceRead) {
  return { createdAt: 'created_at' in row ? row.created_at : '', updatedAt: 'updated_at' in row ? row.updated_at : '', deletedAt: 'deleted_at' in row ? row.deleted_at ?? undefined : undefined, revision: row.revision }
}
export function occurrenceEvent(row: CalendarOccurrenceRead | CalendarEntityRead): Event {
  const end = row.end_date_exclusive ? new Date(`${row.end_date_exclusive}T12:00:00Z`) : undefined
  if (end) end.setUTCDate(end.getUTCDate() - 1)
  const rule = 'recurrence' in row ? row.recurrence : null
  return { ...timestamps(row), id: row.id, calendarId: row.calendar_id, title: row.title, description: row.description,
    startAt: row.start_at ?? zonedInputToIso(`${row.start_date}T00:00`, row.timezone),
    endAt: row.end_at ?? zonedInputToIso(`${end?.toISOString().slice(0, 10)}T23:59`, row.timezone),
    timezone: row.timezone, color: row.color ?? '#0f766e', allDay: row.all_day, location: row.location ?? undefined,
    startDate: row.start_date ?? undefined, endDateExclusive: row.end_date_exclusive ?? undefined,
    recurrenceRuleId: rule ? row.id + ':rule' : ('occurrence_key' in row && row.occurrence_key ? row.entity_id + ':rule' : undefined) }
}
function entityTask(row: CalendarEntityRead): Task {
  return { ...timestamps(row), id: row.id, calendarId: row.calendar_id, title: row.title, description: row.description || undefined, dueDate: row.due_date ?? undefined, completed: row.completed ?? false }
}
function eventPayload(draft: EventDraft, timezone: string) {
  if (draft.allDay) {
    const end = new Date(`${dateKey(draft.endAt, timezone)}T12:00:00Z`); end.setUTCDate(end.getUTCDate() + 1)
    return { title: draft.title, description: draft.description, timezone, color: draft.color, all_day: true,
      start_at: null, end_at: null, start_date: dateKey(draft.startAt, timezone), end_date_exclusive: end.toISOString().slice(0, 10), recurrence: draft.recurrence ? recurrence(draft.recurrence) : undefined }
  }
  return { title: draft.title, description: draft.description, timezone, color: draft.color, all_day: false, start_at: draft.startAt, end_at: draft.endAt, recurrence: draft.recurrence ? recurrence(draft.recurrence) : undefined }
}
function command(kind: string, operation: string, payload: object, extra: object = {}) {
  return sendCalendarCommand({ command_id: crypto.randomUUID(), kind, operation, payload, ...extra })
}

function readRevision(revision?: number) {
  if (!revision || !Number.isInteger(revision)) throw new Error('Обновите календарь перед изменением: версия записи неизвестна')
  return revision
}

export class ApiDayCalendarService implements DayCalendarService {
  private readonly revisions = new Map<string, number>()
  constructor(readonly calendar: Calendar) {}
  async listEvents(date: string) { return this.listEventsInRange(date, date) }
  async listEventsInRange(from: string, to: string) {
    const rows = await overlayOccurrences(this.calendar, from, to, 'event')
    rows.forEach(row => this.revisions.set(row.entity_id, row.revision))
    return rows.map(occurrenceEvent)
  }
  async createEvent(draft: EventDraft) {
    const target = draft.calendarId && draft.calendarId !== this.calendar.id ? { calendar_id: draft.calendarId } : {}
    const result = await command('event', 'create', eventPayload(draft, this.calendar.timezone), target)
    this.revisions.set(result.entity.id, result.entity.revision)
    return occurrenceEvent(result.entity)
  }
  async updateEvent(id: string, draft: EventDraft, scope?: EditScope) {
    const parsed = parseOccurrenceId(id)
    const existing = await entityDetail('event', parsed.seriesEventId)
    if (existing.recurrence && !scope) throw new Error('Выберите область изменения повтора')
    const result = await command('event', 'patch', eventPayload(draft, existing.timezone), { entity_id: existing.id, occurrence_key: parsed.occurrenceKey ?? null, scope: scope ?? null, expected_revision: this.revisions.get(existing.id) ?? existing.revision })
    this.revisions.set(result.entity.id, result.entity.revision)
    if (scope === 'this' && parsed.occurrenceKey) return occurrenceEvent(await exactOccurrence(existing.id, parsed.occurrenceKey))
    return occurrenceEvent(result.entity)
  }
  async deleteEvent(id: string, scope?: DeleteScope) {
    const parsed = parseOccurrenceId(id)
    const existing = await entityDetail('event', parsed.seriesEventId)
    if (existing.recurrence && !scope) throw new Error('Выберите область удаления повтора')
    const result = await command('event', 'delete', {}, { entity_id: existing.id, occurrence_key: parsed.occurrenceKey ?? null, scope: scope ?? null, expected_revision: this.revisions.get(existing.id) ?? existing.revision })
    this.revisions.set(result.entity.id, result.entity.revision)
  }
  async moveEvent(id: string, startAt: string) {
    const parsed = parseOccurrenceId(id)
    const row = await exactOccurrence(parsed.seriesEventId, parsed.occurrenceKey)
    const endAt = new Date(Date.parse(startAt) + Date.parse(row.end_at!) - Date.parse(row.start_at!)).toISOString()
    const result = await command('event', 'patch', { start_at: startAt, end_at: endAt }, { entity_id: row.entity_id, occurrence_key: row.occurrence_key, scope: row.occurrence_key ? 'this' : null, expected_revision: this.revisions.get(row.entity_id) ?? row.revision })
    this.revisions.set(row.entity_id, result.entity.revision)
    return occurrenceEvent(await exactOccurrence(row.entity_id, row.occurrence_key ?? undefined))
  }
  async resizeEvent(id: string, endAt: string) {
    const parsed = parseOccurrenceId(id)
    const row = await exactOccurrence(parsed.seriesEventId, parsed.occurrenceKey)
    const result = await command('event', 'patch', { end_at: endAt }, { entity_id: row.entity_id, occurrence_key: row.occurrence_key, scope: row.occurrence_key ? 'this' : null, expected_revision: this.revisions.get(row.entity_id) ?? row.revision })
    this.revisions.set(row.entity_id, result.entity.revision)
    return occurrenceEvent(await exactOccurrence(row.entity_id, row.occurrence_key ?? undefined))
  }
}

export class ApiTasksService extends LocalTasksService {
  override async createTask(draft: TaskDraft) { return entityTask((await command('task', 'create', { title: draft.title, description: draft.description ?? null, due_date: draft.dueDate ?? null, timezone: this.calendar.timezone, recurrence: recurrence(draft.recurrence) })).entity) }
  override async updateTask(id: string, draft: TaskDraft) {
    return entityTask((await command('task', 'patch', { title: draft.title, description: draft.description ?? null, due_date: draft.dueDate ?? null, recurrence: recurrence(draft.recurrence) }, { entity_id: id, expected_revision: readRevision(draft.expectedRevision), scope: 'series' })).entity)
  }
  override async deleteTask(id: string, expectedRevision?: number) {
    await command('task', 'delete', {}, { entity_id: id, expected_revision: readRevision(expectedRevision), scope: 'series' })
  }
  override async moveTask(id: string, dueDate: string, expectedRevision?: number) {
    return entityTask((await command('task', 'patch', { due_date: dueDate }, { entity_id: id, expected_revision: readRevision(expectedRevision), scope: 'series' })).entity)
  }
  override async toggleCompleted(id: string, snapshot?: TaskActionSnapshot) {
    const revision = readRevision(snapshot?.revision)
    const dueDate = snapshot?.dueDate ?? null
    const happenedDate = dateKey(new Date().toISOString(), this.calendar.timezone)
    if (snapshot?.completed) {
      const query = new URLSearchParams(); if (dueDate) query.set('occurrence_key', dueDate)
      const { confirmation } = await calendarTransport<{ confirmation: { revision: number; happened_date: string } | null }>(`/api/integration/v1/confirmations/${id}?${query}`)
      if (!confirmation) throw new Error('Подтверждение не найдено')
      return entityTask((await command('task', 'confirm', { status: 'revoked', happened_date: confirmation.happened_date, expected_confirmation_revision: confirmation.revision }, { entity_id: id, occurrence_key: dueDate, expected_revision: revision })).entity)
    }
    return entityTask((await command('task', 'complete', { happened_date: happenedDate }, { entity_id: id, occurrence_key: dueDate, expected_revision: revision })).entity)
  }
}

export class ApiPlansService extends LocalPlansService {
  override async createPlan(draft: PlanDraft): Promise<Plan> {
    return occurrenceEvent((await command('plan', 'create', { title: draft.title, description: draft.description ?? null, timezone: this.calendar.timezone, start_at: draft.startAt, end_at: draft.endAt, color: draft.color })).entity)
  }
  override async updatePlan(id: string, draft: PlanDraft): Promise<Plan> {
    return occurrenceEvent((await command('plan', 'patch', { title: draft.title, description: draft.description ?? null, start_at: draft.startAt, end_at: draft.endAt, color: draft.color }, { entity_id: id, expected_revision: readRevision(draft.expectedRevision) })).entity)
  }
  override async deletePlan(id: string, expectedRevision?: number) { await command('plan', 'delete', {}, { entity_id: id, expected_revision: readRevision(expectedRevision) }) }
  override async listPlansInRange(from: string, to: string): Promise<Plan[]> { return (await overlayOccurrences(this.calendar, from, to, 'plan')).map(occurrenceEvent) }
}
