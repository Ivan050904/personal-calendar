// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { App, type AppServices } from './App'
import type { DayCalendarService, EventDraft } from '../application/day-calendar'
import type { Calendar } from '../domain/models'

afterEach(() => cleanup())

const calendar: Calendar = {
  id: '1d76fb58-104a-4ffd-834a-e0cb9644af74', name: 'Personal Calendar', timezone: 'UTC',
  createdAt: '2026-09-17T00:00:00.000Z', updatedAt: '2026-09-17T00:00:00.000Z',
}

function emptyList() { return Promise.resolve([]) }

describe('day calendar view', () => {
  it('opens a prefilled form when an empty hour is clicked and saves the event', async () => {
    const user = userEvent.setup()
    const created: EventDraft[] = []
    const dayCalendar: DayCalendarService = {
      calendar,
      listEvents: async () => [],
      listEventsInRange: async () => [],
      createEvent: async (draft) => {
        created.push(draft)
        return { ...draft, id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }
      },
      updateEvent: async (_id, draft) => ({ ...draft, id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }),
      deleteEvent: async () => undefined,
      moveEvent: async (_id, startAt) => ({ id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: calendar.id, title: '', description: '', startAt, endAt: startAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: startAt, updatedAt: startAt }),
      resizeEvent: async (_id, endAt) => ({ id: '46efb94a-d2d1-41ba-8b92-bec1e6da6d34', calendarId: calendar.id, title: '', description: '', startAt: endAt, endAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: endAt, updatedAt: endAt }),
    }
    const services = {
      calendar: dayCalendar,
      plans: { calendar, createPlan: async () => { throw new Error('unused') }, updatePlan: async () => { throw new Error('unused') }, deletePlan: async () => undefined, listPlansInRange: emptyList, addTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, toggleTask: async () => { throw new Error('unused') }, reorderTasks: async () => [], listTasks: emptyList, progress: async () => ({ completed: 0, total: 0, percentage: 0 }) },
      tasks: { calendar, createTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, listUndatedTasks: emptyList, listTasksForDate: emptyList, moveTask: async () => { throw new Error('unused') }, toggleCompleted: async () => { throw new Error('unused') } },
      lists: { calendar, listAll: async () => [], create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined, addItem: async () => { throw new Error('unused') }, updateItem: async () => { throw new Error('unused') }, deleteItem: async () => undefined, toggleItem: async () => { throw new Error('unused') }, reorderItems: async () => [] },
      categories: { calendar, list: emptyList, create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined },
      reminders: { listForEvent: emptyList, add: async () => { throw new Error('unused') }, remove: async () => undefined },
      repositories: {
        calendars: { get: async () => calendar, list: async () => [calendar], put: async () => undefined, getLocalCalendar: async () => calendar },
        events: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        recurrenceRules: { get: async () => undefined, list: emptyList, put: async () => undefined },
        eventExceptions: { get: async () => undefined, list: emptyList, put: async () => undefined },
        plans: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        planTasks: { get: async () => undefined, list: emptyList, put: async () => undefined },
        tasks: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        lists: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        listItems: { get: async () => undefined, list: emptyList, put: async () => undefined },
        categories: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        reminders: { get: async () => undefined, list: emptyList, put: async () => undefined },
      },
    } as unknown as AppServices

    render(<App services={services} now={() => new Date('2026-09-17T08:00:00.000Z')} />)

    expect(screen.getByRole('navigation', { name: 'Основная навигация' }).querySelectorAll('button')).toHaveLength(6)
    expect(within(screen.getByRole('navigation', { name: 'Основная навигация' })).getByRole('button', { name: 'Календарь' }).getAttribute('aria-current')).toBe('page')
    await user.click(screen.getByRole('button', { name: 'Создать событие в 9:00' }))
    await user.type(screen.getByLabelText('Название'), 'Встреча')
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    expect(created).toHaveLength(1)
    expect(created[0]?.title).toBe('Встреча')
    expect(created[0]?.startAt).toContain('T09:00:00.000Z')
  })
})

describe('tasks section', () => {
  it('shows composer and buckets, then lists a created undated task', async () => {
    const user = userEvent.setup()
    const created: { title: string; dueDate?: string }[] = []
    const undated: Array<{
      id: string
      calendarId: string
      title: string
      completed: boolean
      createdAt: string
      updatedAt: string
    }> = []
    const dayCalendar: DayCalendarService = {
      calendar,
      listEvents: emptyList,
      listEventsInRange: emptyList,
      createEvent: async () => { throw new Error('unused') },
      updateEvent: async () => { throw new Error('unused') },
      deleteEvent: async () => undefined,
      moveEvent: async () => { throw new Error('unused') },
      resizeEvent: async () => { throw new Error('unused') },
    }
    const services = {
      calendar: dayCalendar,
      plans: { calendar, createPlan: async () => { throw new Error('unused') }, updatePlan: async () => { throw new Error('unused') }, deletePlan: async () => undefined, listPlansInRange: emptyList, addTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, toggleTask: async () => { throw new Error('unused') }, reorderTasks: async () => [], listTasks: emptyList, progress: async () => ({ completed: 0, total: 0, percentage: 0 }) },
      tasks: {
        calendar,
        createTask: async (draft: { title: string; dueDate?: string }) => {
          created.push(draft)
          const task = {
            id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
            calendarId: calendar.id,
            title: draft.title,
            dueDate: draft.dueDate,
            completed: false,
            createdAt: '2026-09-17T08:00:00.000Z',
            updatedAt: '2026-09-17T08:00:00.000Z',
          }
          if (draft.dueDate === undefined) undated.push(task)
          return task
        },
        updateTask: async () => { throw new Error('unused') },
        deleteTask: async () => undefined,
        listUndatedTasks: async () => [...undated],
        listTasksForDate: emptyList,
        moveTask: async () => { throw new Error('unused') },
        toggleCompleted: async () => { throw new Error('unused') },
      },
      lists: { calendar, listAll: async () => [], create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined, addItem: async () => { throw new Error('unused') }, updateItem: async () => { throw new Error('unused') }, deleteItem: async () => undefined, toggleItem: async () => { throw new Error('unused') }, reorderItems: async () => [] },
      categories: { calendar, list: emptyList, create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined },
      reminders: { listForEvent: emptyList, add: async () => { throw new Error('unused') }, remove: async () => undefined },
      repositories: {
        calendars: { get: async () => calendar, list: async () => [calendar], put: async () => undefined, getLocalCalendar: async () => calendar },
        events: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        recurrenceRules: { get: async () => undefined, list: emptyList, put: async () => undefined },
        eventExceptions: { get: async () => undefined, list: emptyList, put: async () => undefined },
        plans: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        planTasks: { get: async () => undefined, list: emptyList, put: async () => undefined },
        tasks: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        lists: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        listItems: { get: async () => undefined, list: emptyList, put: async () => undefined },
        categories: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        reminders: { get: async () => undefined, list: emptyList, put: async () => undefined },
      },
    } as unknown as AppServices

    render(<App services={services} now={() => new Date('2026-09-17T08:00:00.000Z')} />)

    const nav = screen.getByRole('navigation', { name: 'Основная навигация' })
    await user.click(within(nav).getByRole('button', { name: 'Задачи' }))
    expect(screen.getByRole('region', { name: 'Задачи' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Без даты' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Сегодня' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Добавить' })).toBeTruthy()

    await user.type(screen.getByLabelText('Название'), 'Купить молоко')
    await user.click(screen.getByRole('button', { name: 'Добавить' }))

    expect(created).toHaveLength(1)
    expect(created[0]?.title).toBe('Купить молоко')
    expect(created[0]?.dueDate).toBeUndefined()
    expect(await screen.findByText('Купить молоко')).toBeTruthy()
  })
})

describe('visible hours settings', () => {
  it('hides hours outside the configured range on the day timeline', async () => {
    const user = userEvent.setup()
    const dayCalendar: DayCalendarService = {
      calendar,
      listEvents: async () => [],
      listEventsInRange: async () => [],
      createEvent: async (draft) => ({ ...draft, id: 'e1', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }),
      updateEvent: async (_id, draft) => ({ ...draft, id: 'e1', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }),
      deleteEvent: async () => undefined,
      moveEvent: async (_id, startAt) => ({ id: 'e1', calendarId: calendar.id, title: '', description: '', startAt, endAt: startAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: startAt, updatedAt: startAt }),
      resizeEvent: async (_id, endAt) => ({ id: 'e1', calendarId: calendar.id, title: '', description: '', startAt: endAt, endAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: endAt, updatedAt: endAt }),
    }
    const services = {
      calendar: dayCalendar,
      plans: { calendar, createPlan: async () => { throw new Error('unused') }, updatePlan: async () => { throw new Error('unused') }, deletePlan: async () => undefined, listPlansInRange: emptyList, addTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, toggleTask: async () => { throw new Error('unused') }, reorderTasks: async () => [], listTasks: emptyList, progress: async () => ({ completed: 0, total: 0, percentage: 0 }) },
      tasks: { calendar, createTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, listUndatedTasks: emptyList, listTasksForDate: emptyList, moveTask: async () => { throw new Error('unused') }, toggleCompleted: async () => { throw new Error('unused') } },
      lists: { calendar, listAll: async () => [], create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined, addItem: async () => { throw new Error('unused') }, updateItem: async () => { throw new Error('unused') }, deleteItem: async () => undefined, toggleItem: async () => { throw new Error('unused') }, reorderItems: async () => [] },
      categories: { calendar, list: emptyList, create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined },
      reminders: { listForEvent: emptyList, add: async () => { throw new Error('unused') }, remove: async () => undefined },
      repositories: {
        calendars: { get: async () => calendar, list: async () => [calendar], put: async () => undefined, getLocalCalendar: async () => calendar },
        events: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        recurrenceRules: { get: async () => undefined, list: emptyList, put: async () => undefined },
        eventExceptions: { get: async () => undefined, list: emptyList, put: async () => undefined },
        plans: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        planTasks: { get: async () => undefined, list: emptyList, put: async () => undefined },
        tasks: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        lists: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        listItems: { get: async () => undefined, list: emptyList, put: async () => undefined },
        categories: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        reminders: { get: async () => undefined, list: emptyList, put: async () => undefined },
      },
    } as unknown as AppServices

    render(<App services={services} now={() => new Date('2026-09-17T08:00:00.000Z')} />)

    expect(screen.getByRole('button', { name: 'Создать событие в 0:00' })).toBeTruthy()

    const nav = screen.getByRole('navigation', { name: 'Основная навигация' })
    await user.click(within(nav).getByRole('button', { name: 'Настройки' }))
    await user.selectOptions(screen.getByLabelText('Показывать часы с'), '3')
    await user.click(within(nav).getByRole('button', { name: 'Календарь' }))

    expect(screen.queryByRole('button', { name: 'Создать событие в 0:00' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Создать событие в 1:00' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Создать событие в 2:00' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Создать событие в 3:00' })).toBeTruthy()
  })
})

describe('week calendar create', () => {
  it('opens a prefilled form when an empty week cell is clicked', async () => {
    const user = userEvent.setup()
    const dayCalendar: DayCalendarService = {
      calendar,
      listEvents: async () => [],
      listEventsInRange: async () => [],
      createEvent: async (draft) => ({ ...draft, id: 'e1', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }),
      updateEvent: async (_id, draft) => ({ ...draft, id: 'e1', calendarId: calendar.id, timezone: 'UTC', allDay: false, createdAt: draft.startAt, updatedAt: draft.startAt }),
      deleteEvent: async () => undefined,
      moveEvent: async (_id, startAt) => ({ id: 'e1', calendarId: calendar.id, title: '', description: '', startAt, endAt: startAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: startAt, updatedAt: startAt }),
      resizeEvent: async (_id, endAt) => ({ id: 'e1', calendarId: calendar.id, title: '', description: '', startAt: endAt, endAt, timezone: 'UTC', allDay: false, color: '#000', createdAt: endAt, updatedAt: endAt }),
    }
    const services = {
      calendar: dayCalendar,
      plans: { calendar, createPlan: async () => { throw new Error('unused') }, updatePlan: async () => { throw new Error('unused') }, deletePlan: async () => undefined, listPlansInRange: emptyList, addTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, toggleTask: async () => { throw new Error('unused') }, reorderTasks: async () => [], listTasks: emptyList, progress: async () => ({ completed: 0, total: 0, percentage: 0 }) },
      tasks: { calendar, createTask: async () => { throw new Error('unused') }, updateTask: async () => { throw new Error('unused') }, deleteTask: async () => undefined, listUndatedTasks: emptyList, listTasksForDate: emptyList, moveTask: async () => { throw new Error('unused') }, toggleCompleted: async () => { throw new Error('unused') } },
      lists: { calendar, listAll: async () => [], create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined, addItem: async () => { throw new Error('unused') }, updateItem: async () => { throw new Error('unused') }, deleteItem: async () => undefined, toggleItem: async () => { throw new Error('unused') }, reorderItems: async () => [] },
      categories: { calendar, list: emptyList, create: async () => { throw new Error('unused') }, rename: async () => { throw new Error('unused') }, softDelete: async () => undefined },
      reminders: { listForEvent: emptyList, add: async () => { throw new Error('unused') }, remove: async () => undefined },
      repositories: {
        calendars: { get: async () => calendar, list: async () => [calendar], put: async () => undefined, getLocalCalendar: async () => calendar },
        events: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        recurrenceRules: { get: async () => undefined, list: emptyList, put: async () => undefined },
        eventExceptions: { get: async () => undefined, list: emptyList, put: async () => undefined },
        plans: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        planTasks: { get: async () => undefined, list: emptyList, put: async () => undefined },
        tasks: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        lists: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        listItems: { get: async () => undefined, list: emptyList, put: async () => undefined },
        categories: { get: async () => undefined, list: emptyList, put: async () => undefined, listByCalendarId: emptyList },
        reminders: { get: async () => undefined, list: emptyList, put: async () => undefined },
      },
    } as unknown as AppServices

    render(<App services={services} now={() => new Date('2026-09-17T08:00:00.000Z')} />)
    await user.click(screen.getByRole('button', { name: 'Неделя' }))
    await user.click(screen.getByRole('button', { name: 'Создать событие 2026-09-17 в 10:00' }))

    expect(screen.getByRole('heading', { name: 'Событие' })).toBeTruthy()
    expect((screen.getByLabelText('Начало') as HTMLInputElement).value).toBe('2026-09-17T10:00')
  })
})
