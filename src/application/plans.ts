import { createId } from '../domain/ids'
import type { Calendar, Plan, PlanTask } from '../domain/models'
import { validatePlan, ValidationError } from '../domain/validation'
import { dateKey } from './day-calendar'
import type { CalendarEntityRepository, EntityRepository } from './repositories'

export interface PlanDraft {
  title: string
  description?: string
  startAt: string
  endAt: string
  color: string
}

export interface PlanProgress {
  completed: number
  total: number
  percentage: number
}

export interface PlansService {
  readonly calendar: Calendar
  createPlan(draft: PlanDraft): Promise<Plan>
  updatePlan(id: string, draft: PlanDraft): Promise<Plan>
  deletePlan(id: string): Promise<void>
  listPlansInRange(startDate: string, endDate: string): Promise<Plan[]>
  addTask(planId: string, title: string): Promise<PlanTask>
  updateTask(id: string, title: string): Promise<PlanTask>
  deleteTask(id: string): Promise<void>
  toggleTask(id: string): Promise<PlanTask>
  reorderTasks(planId: string, orderedIds: string[]): Promise<PlanTask[]>
  listTasks(planId: string): Promise<PlanTask[]>
  progress(planId: string): Promise<PlanProgress>
}

export class LocalPlansService implements PlansService {
  constructor(
    readonly calendar: Calendar,
    private readonly plans: CalendarEntityRepository<Plan>,
    private readonly planTasks: EntityRepository<PlanTask>,
    private readonly now: () => string = () => new Date().toISOString(),
  ) {}

  async createPlan(draft: PlanDraft): Promise<Plan> {
    const timestamp = this.now()
    const plan: Plan = {
      id: createId(),
      calendarId: this.calendar.id,
      title: draft.title,
      description: draft.description,
      startAt: draft.startAt,
      endAt: draft.endAt,
      timezone: this.calendar.timezone,
      color: draft.color,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    validatePlan(plan)
    await this.plans.put(plan)
    return plan
  }

  async updatePlan(id: string, draft: PlanDraft): Promise<Plan> {
    const existing = await this.requirePlan(id)
    const plan: Plan = {
      ...existing,
      title: draft.title,
      description: draft.description,
      startAt: draft.startAt,
      endAt: draft.endAt,
      color: draft.color,
      updatedAt: this.now(),
    }
    validatePlan(plan)
    await this.plans.put(plan)
    return plan
  }

  async deletePlan(id: string): Promise<void> {
    const existing = await this.requirePlan(id)
    const timestamp = this.now()
    await this.plans.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async listPlansInRange(startDate: string, endDate: string): Promise<Plan[]> {
    const plans = await this.plans.listByCalendarId(this.calendar.id)
    return plans
      .filter((plan) => {
        if (plan.deletedAt !== undefined) return false
        const start = dateKey(plan.startAt, plan.timezone)
        const end = dateKey(plan.endAt, plan.timezone)
        return start <= endDate && end >= startDate
      })
      .sort((left, right) => left.startAt.localeCompare(right.startAt))
  }

  async addTask(planId: string, title: string): Promise<PlanTask> {
    await this.requirePlan(planId)
    requireTaskTitle(title)
    const timestamp = this.now()
    const existing = await this.activeTasks(planId)
    const task: PlanTask = {
      id: createId(),
      planId,
      title: title.trim(),
      completed: false,
      order: existing.length === 0 ? 0 : Math.max(...existing.map((item) => item.order)) + 1,
      createdAt: timestamp,
      updatedAt: timestamp,
    }
    await this.planTasks.put(task)
    return task
  }

  async updateTask(id: string, title: string): Promise<PlanTask> {
    const existing = await this.requireTask(id)
    requireTaskTitle(title)
    const task: PlanTask = {
      ...existing,
      title: title.trim(),
      updatedAt: this.now(),
    }
    await this.planTasks.put(task)
    return task
  }

  async deleteTask(id: string): Promise<void> {
    const existing = await this.requireTask(id)
    const timestamp = this.now()
    await this.planTasks.put({ ...existing, deletedAt: timestamp, updatedAt: timestamp })
  }

  async toggleTask(id: string): Promise<PlanTask> {
    const existing = await this.requireTask(id)
    const task: PlanTask = {
      ...existing,
      completed: !existing.completed,
      updatedAt: this.now(),
    }
    await this.planTasks.put(task)
    return task
  }

  async reorderTasks(planId: string, orderedIds: string[]): Promise<PlanTask[]> {
    await this.requirePlan(planId)
    const tasks = await this.activeTasks(planId)
    const byId = new Map(tasks.map((task) => [task.id, task]))
    if (orderedIds.length !== tasks.length || orderedIds.some((id) => !byId.has(id))) {
      throw new ValidationError('orderedIds must include each active plan task exactly once')
    }
    const timestamp = this.now()
    const reordered: PlanTask[] = []
    for (let index = 0; index < orderedIds.length; index += 1) {
      const current = byId.get(orderedIds[index]!)!
      const next: PlanTask = { ...current, order: index, updatedAt: timestamp }
      await this.planTasks.put(next)
      reordered.push(next)
    }
    return reordered
  }

  async listTasks(planId: string): Promise<PlanTask[]> {
    await this.requirePlan(planId)
    return this.activeTasks(planId)
  }

  async progress(planId: string): Promise<PlanProgress> {
    const tasks = await this.listTasks(planId)
    return planProgress(tasks)
  }

  private async requirePlan(id: string): Promise<Plan> {
    const plan = await this.plans.get(id)
    if (plan === undefined || plan.calendarId !== this.calendar.id || plan.deletedAt !== undefined) {
      throw new Error('Plan not found')
    }
    return plan
  }

  private async requireTask(id: string): Promise<PlanTask> {
    const task = await this.planTasks.get(id)
    if (task === undefined || task.deletedAt !== undefined) {
      throw new Error('Plan task not found')
    }
    await this.requirePlan(task.planId)
    return task
  }

  private async activeTasks(planId: string): Promise<PlanTask[]> {
    return (await this.planTasks.list())
      .filter((task) => task.planId === planId && task.deletedAt === undefined)
      .sort((left, right) => left.order - right.order || left.createdAt.localeCompare(right.createdAt))
  }
}

export function planProgress(tasks: PlanTask[]): PlanProgress {
  const active = tasks.filter((task) => task.deletedAt === undefined)
  const completed = active.filter((task) => task.completed).length
  const total = active.length
  return {
    completed,
    total,
    percentage: total === 0 ? 0 : Math.round((completed / total) * 100),
  }
}

function requireTaskTitle(title: string): void {
  if (title.trim().length === 0) {
    throw new ValidationError('title is required')
  }
}
