import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { Event, Plan, Weekday } from '../domain/models'
import {
  allDayBounds,
  dateKey,
  eventHour,
  hourInTimezone,
  isoToZonedInput,
  minuteInTimezone,
  zonedInputToIso,
  type DayCalendarService,
  type DeleteScope,
  type EditScope,
  type EventDraft,
  type RecurrenceDraft,
} from '../application/day-calendar'
import { weekdayOf } from '../application/recurrence'
import type { PlansService } from '../application/plans'
import type { TasksService } from '../application/tasks'
import type { LocalListsService } from '../application/lists'
import type { LocalCategoriesService } from '../application/categories'
import { searchEntities, filterEventsByCategory } from '../application/categories'
import { dueReminders, REMINDER_OFFSETS_MINUTES, type LocalRemindersService } from '../application/reminders'
import { collectTrash, restoreEntity, type TrashEntry } from '../application/trash'
import type { Repositories } from '../application/repositories'
import { exportBackup, importBackupReplace } from '../application/backup'
import { addDays } from '../application/week-calendar'
import { buildSmartDaySnapshot, formatDuration, type SmartDaySnapshot } from '../application/smart-day'
import {
  buildVisibleHours,
  displayOffsetPx,
  HOUR_ROW_PX,
  normalizeVisibleHoursPreference,
  occupiedHours,
  readVisibleHoursPreference,
  writeVisibleHoursPreference,
  type VisibleHoursPreference,
} from '../application/visible-hours'
import './day-calendar.css'
import { WeekCalendar } from './WeekCalendar'
import { MonthCalendar } from './MonthCalendar'
import { AiChatPanel } from './AiChatPanel'
import './month-calendar.css'
import './app-shell.css'

const HOUR_OPTIONS = Array.from({ length: 24 }, (_, hour) => hour)
const DEFAULT_COLOR = '#475569'
const THEME_STORAGE_KEY = 'personal-calendar-theme'
const SIDEBAR_STORAGE_KEY = 'personal-calendar-sidebar-open'
const WEEKDAY_LABELS: { value: Weekday; label: string }[] = [
  { value: 1, label: 'Пн' }, { value: 2, label: 'Вт' }, { value: 3, label: 'Ср' },
  { value: 4, label: 'Чт' }, { value: 5, label: 'Пт' }, { value: 6, label: 'Сб' }, { value: 7, label: 'Вс' },
]
const ENTITY_TYPE_LABELS: Record<string, string> = {
  event: 'Событие',
  plan: 'План',
  task: 'Задача',
  list: 'Список',
}

type Section = 'calendar' | 'tasks' | 'lists' | 'assistant' | 'trash' | 'settings'
type CalendarView = 'now' | 'day' | 'week' | 'month'

type NavIconId = Section

const NAV_ICON_PATHS: Record<NavIconId, ReactNode> = {
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M3.5 9.5h17M8 3.5v3M16 3.5v3" />
    </>
  ),
  tasks: (
    <>
      <rect x="4" y="4" width="16" height="16" rx="2" />
      <path d="M8 12l2.5 2.5L16 9" />
    </>
  ),
  lists: (
    <>
      <path d="M8 7h12M8 12h12M8 17h12" />
      <path d="M4.5 7h.01M4.5 12h.01M4.5 17h.01" strokeLinecap="round" />
    </>
  ),
  assistant: (
    <>
      <path d="M5 18.5V8.2A2.2 2.2 0 0 1 7.2 6h9.6A2.2 2.2 0 0 1 19 8.2v6.1A2.2 2.2 0 0 1 16.8 16.5H9.2L5 18.5Z" />
      <path d="M9 10.5h6M9 13h4" />
    </>
  ),
  trash: (
    <>
      <path d="M5 8h14M9.5 8V6.5A1.5 1.5 0 0 1 11 5h2a1.5 1.5 0 0 1 1.5 1.5V8M7.5 8l.8 11a1.5 1.5 0 0 0 1.5 1.4h4.4a1.5 1.5 0 0 0 1.5-1.4l.8-11" />
    </>
  ),
  settings: (
    <>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 0 1 0 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281Z"
      />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </>
  ),
}

function NavIcon({ id }: { id: NavIconId }) {
  return (
    <span className="app-nav-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
        {NAV_ICON_PATHS[id]}
      </svg>
    </span>
  )
}

const PRIMARY_NAV: { id: Section; label: string }[] = [
  { id: 'calendar', label: 'Календарь' },
  { id: 'tasks', label: 'Задачи' },
  { id: 'lists', label: 'Списки' },
  { id: 'assistant', label: 'Ассистент' },
  { id: 'trash', label: 'Корзина' },
  { id: 'settings', label: 'Настройки' },
]

function useCoarsePointer(): boolean {
  const [coarse, setCoarse] = useState(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false
    return window.matchMedia('(pointer: coarse)').matches
  })
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const media = window.matchMedia('(pointer: coarse)')
    const onChange = () => setCoarse(media.matches)
    onChange()
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])
  return coarse
}

function readStoredTheme(): 'light' | 'dark' {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

function readSidebarOpen(): boolean {
  try {
    const value = localStorage.getItem(SIDEBAR_STORAGE_KEY)
    if (value === '0') return false
    if (value === '1') return true
  } catch { /* ignore */ }
  return true
}

export interface AppServices {
  calendar: DayCalendarService
  plans: PlansService
  tasks: TasksService
  lists: LocalListsService
  categories: LocalCategoriesService
  reminders: LocalRemindersService
  repositories: Repositories
}

export function App({
  services,
  now = () => new Date(),
  onLogout,
}: {
  services: AppServices
  now?: () => Date
  onLogout?: () => void
}) {
  const { calendar } = services
  const [section, setSection] = useState<Section>('calendar')
  const [selectedDate, setSelectedDate] = useState(() => dateKey(now(), calendar.calendar.timezone))
  const [view, setView] = useState<CalendarView>('day')
  const [events, setEvents] = useState<Event[]>([])
  const [dayPlans, setDayPlans] = useState<Plan[]>([])
  const [draft, setDraft] = useState<EventDraft | undefined>()
  const [editing, setEditing] = useState<Event | undefined>()
  const [dragged, setDragged] = useState<Event | undefined>()
  const [warning, setWarning] = useState<string | undefined>()
  const [pendingScope, setPendingScope] = useState<{ kind: 'edit' | 'delete'; draft?: EventDraft; id: string } | undefined>()
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>()
  const [searchQuery, setSearchQuery] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>(readStoredTheme)
  const [sidebarOpen, setSidebarOpen] = useState(readSidebarOpen)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [visibleHoursPref, setVisibleHoursPref] = useState<VisibleHoursPreference>(readVisibleHoursPreference)
  const [notificationsEnabled, setNotificationsEnabled] = useState(false)
  const [status, setStatus] = useState<string | undefined>()
  const [boardRevision, setBoardRevision] = useState(0)
  const [focusPlanId, setFocusPlanId] = useState<string | undefined>()
  const [dockOpen, setDockOpen] = useState(false)
  const touchStartX = useRef<number | undefined>(undefined)
  const touchStartY = useRef<number | undefined>(undefined)
  const dayTimelineRef = useRef<HTMLElement | null>(null)
  const coarsePointer = useCoarsePointer()
  const allowDayDrag = !coarsePointer

  const goSection = (id: Section) => {
    setSection(id)
    setMobileMenuOpen(false)
  }

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem(THEME_STORAGE_KEY, theme) } catch { /* ignore */ }
  }, [theme])

  useEffect(() => {
    try { localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarOpen ? '1' : '0') } catch { /* ignore */ }
  }, [sidebarOpen])

  useEffect(() => {
    if (!mobileMenuOpen) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileMenuOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.body.classList.add('is-mobile-nav-open')
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.classList.remove('is-mobile-nav-open')
    }
  }, [mobileMenuOpen])

  useEffect(() => {
    writeVisibleHoursPreference(visibleHoursPref)
  }, [visibleHoursPref])

  const refresh = async () => {
    const listed = await calendar.listEvents(selectedDate)
    setEvents(filterEventsByCategory(listed, categoryFilter))
    const plans = await services.plans.listPlansInRange(selectedDate, selectedDate)
    setDayPlans(plans)
    setBoardRevision((value) => value + 1)
  }

  useEffect(() => {
    if (!notificationsEnabled || typeof Notification === 'undefined' || Notification.permission !== 'granted') return
    const fired = new Set<string>()
    const tick = async () => {
      const nowIso = now().toISOString()
      const day = dateKey(now(), calendar.calendar.timezone)
      const [todayEvents, reminders] = await Promise.all([
        calendar.listEventsInRange(day, day),
        services.repositories.reminders.list(),
      ])
      const byEvent = new Map(todayEvents.map((event) => [event.id.split('::')[0]!, event]))
      const due = dueReminders(
        reminders.flatMap((reminder) => {
          const event = byEvent.get(reminder.eventId)
          if (!event) return []
          return [{ reminder, occurrenceStartAt: event.startAt }]
        }),
        nowIso,
        2,
      )
      for (const reminder of due) {
        if (fired.has(reminder.id)) continue
        fired.add(reminder.id)
        const event = byEvent.get(reminder.eventId)
        try {
          const title = event?.title ?? 'Напоминание'
          const body = `Скоро: ${event?.title ?? 'событие'}`
          const reg = 'serviceWorker' in navigator ? await navigator.serviceWorker.getRegistration() : undefined
          if (reg?.showNotification) {
            await reg.showNotification(title, { body, tag: reminder.id })
          } else {
            new Notification(title, { body })
          }
        } catch { /* ignore */ }
      }
    }
    void tick()
    const timer = window.setInterval(() => { void tick() }, 30_000)
    return () => window.clearInterval(timer)
  }, [notificationsEnabled, calendar, services.repositories.reminders, now])

  const createAt = (date: string, hour: number) => {
    const start = zonedInputToIso(`${date}T${String(hour).padStart(2, '0')}:00`, calendar.calendar.timezone)
    const end = new Date(new Date(start).getTime() + 60 * 60 * 1000).toISOString()
    setSelectedDate(date)
    setEditing(undefined)
    setDraft({ title: '', description: '', startAt: start, endAt: end, color: DEFAULT_COLOR })
  }

  const createAtHour = (hour: number) => createAt(selectedDate, hour)

  const createAtNow = () => createAtHour(hourInTimezone(now(), calendar.calendar.timezone))

  useEffect(() => {
    let cancelled = false
    void calendar.listEvents(selectedDate).then((nextEvents) => {
      if (!cancelled) setEvents(filterEventsByCategory(nextEvents, categoryFilter))
    })
    void services.plans.listPlansInRange(selectedDate, selectedDate).then((plans) => {
      if (!cancelled) setDayPlans(plans)
    })
    return () => { cancelled = true }
  }, [calendar, selectedDate, categoryFilter, services.plans, boardRevision])

  useEffect(() => {
    if (view !== 'day' || section !== 'calendar') return
    const todayKey = dateKey(now(), calendar.calendar.timezone)
    if (selectedDate !== todayKey) return
    const node = dayTimelineRef.current
    if (!node) return
    const hour = hourInTimezone(now(), calendar.calendar.timezone)
    const forced = events.flatMap((event) => occupiedHours(event.startAt, event.endAt, event.timezone || calendar.calendar.timezone))
    const visible = buildVisibleHours(visibleHoursPref, [...forced, hour])
    const target = Math.max(0, displayOffsetPx(visible, hour) - HOUR_ROW_PX)
    node.scrollTop = target
  }, [view, section, selectedDate, calendar.calendar.timezone, now, events, visibleHoursPref])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
      if (event.key === 'n') createAtNow()
      if (event.key === 't') setSection('tasks')
      if (event.key === 'a') setSection('assistant')
      if (event.key === 'ArrowLeft') setSelectedDate((date) => addDays(date, view === 'week' ? -7 : -1))
      if (event.key === 'ArrowRight') setSelectedDate((date) => addDays(date, view === 'week' ? 7 : 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const titleParts = useMemo(() => {
    const date = new Date(`${selectedDate}T12:00:00`)
    const weekday = new Intl.DateTimeFormat('ru-RU', { weekday: 'long', timeZone: calendar.calendar.timezone }).format(date)
    const rest = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', year: 'numeric', timeZone: calendar.calendar.timezone }).format(date)
    return { weekday, rest }
  }, [calendar.calendar.timezone, selectedDate])

  const submit = async (nextDraft: EventDraft, reminderOffsets: number[] = []) => {
    let eventId: string | undefined
    if (editing === undefined) {
      const created = await calendar.createEvent(nextDraft)
      eventId = created.id
      setDraft(undefined)
    } else if (editing.id.includes('::')) {
      setPendingScope({ kind: 'edit', draft: nextDraft, id: editing.id })
      return
    } else {
      await calendar.updateEvent(editing.id, nextDraft, 'series')
      eventId = editing.id
      setDraft(undefined)
      setEditing(undefined)
    }
    if (eventId !== undefined) {
      const existing = await services.reminders.listForEvent(eventId)
      for (const reminder of existing) {
        if (!reminderOffsets.includes(reminder.offsetMinutes)) await services.reminders.remove(reminder.id)
      }
      for (const offset of reminderOffsets) {
        if (!existing.some((item) => item.offsetMinutes === offset) && (REMINDER_OFFSETS_MINUTES as readonly number[]).includes(offset)) {
          await services.reminders.add(eventId, offset as (typeof REMINDER_OFFSETS_MINUTES)[number])
        }
      }
    }
    await refresh()
  }

  const remove = async (id: string) => {
    if (id.includes('::')) {
      setPendingScope({ kind: 'delete', id })
      return
    }
    if (!window.confirm('Удалить это событие?')) return
    await calendar.deleteEvent(id, 'series')
    await refresh()
  }

  const jumpFromSearch = async (hit: { type: string; id: string }) => {
    setSearchQuery('')
    if (hit.type === 'task') {
      setSection('tasks')
      return
    }
    if (hit.type === 'list') {
      setSection('lists')
      return
    }
    setSection('calendar')
    if (hit.type === 'event') {
      const event = await services.repositories.events.get(hit.id)
      if (event) {
        setSelectedDate(dateKey(event.startAt, event.timezone || calendar.calendar.timezone))
        setView('day')
        return
      }
    }
    if (hit.type === 'plan') {
      const plan = await services.repositories.plans.get(hit.id)
      if (plan) {
        setSelectedDate(dateKey(plan.startAt, plan.timezone || calendar.calendar.timezone))
        setView('day')
      }
    }
  }

  const todayKey = dateKey(now(), calendar.calendar.timezone)
  const nowHour = hourInTimezone(now(), calendar.calendar.timezone)
  const nowMinute = minuteInTimezone(now(), calendar.calendar.timezone)
  const showNowLine = view === 'day' && selectedDate === todayKey
  const dayVisibleHours = useMemo(() => {
    const timed = events.filter((event) => !event.allDay)
    const forced = [
      ...timed.flatMap((event) =>
        occupiedHours(event.startAt, event.endAt, event.timezone || calendar.calendar.timezone),
      ),
      ...dayPlans.flatMap((plan) =>
        occupiedHours(plan.startAt, plan.endAt, plan.timezone || calendar.calendar.timezone),
      ),
    ]
    if (showNowLine) forced.push(nowHour)
    return buildVisibleHours(visibleHoursPref, forced)
  }, [events, dayPlans, calendar.calendar.timezone, visibleHoursPref, showNowLine, nowHour])

  const allDayEvents = useMemo(() => events.filter((event) => event.allDay), [events])
  const timedEvents = useMemo(() => events.filter((event) => !event.allDay), [events])

  const applyScope = async (scope: EditScope | DeleteScope) => {
    if (pendingScope === undefined) return
    if (pendingScope.kind === 'delete') await calendar.deleteEvent(pendingScope.id, scope as DeleteScope)
    else if (pendingScope.draft !== undefined) await calendar.updateEvent(pendingScope.id, pendingScope.draft, scope as EditScope)
    setPendingScope(undefined)
    setDraft(undefined)
    setEditing(undefined)
    await refresh()
  }

  const moveToHour = async (hour: number) => {
    if (dragged === undefined) return
    const startAt = zonedInputToIso(`${selectedDate}T${String(hour).padStart(2, '0')}:00`, calendar.calendar.timezone)
    const moved = await calendar.moveEvent(dragged.id, startAt)
    const current = await calendar.listEvents(selectedDate)
    setWarning(current.some((event) => event.id !== moved.id && Date.parse(moved.startAt) < Date.parse(event.endAt) && Date.parse(moved.endAt) > Date.parse(event.startAt)) ? 'События пересекаются' : undefined)
    setDragged(undefined)
    await refresh()
  }

  const openEvent = (event: Event) => {
    setEditing(event)
    setDraft({
      title: event.title,
      description: event.description,
      startAt: event.startAt,
      endAt: event.endAt,
      color: event.color,
      allDay: event.allDay,
      categoryId: event.categoryId,
    })
  }

  return (
    <main className={`calendar-app${sidebarOpen ? '' : ' is-sidebar-collapsed'}${mobileMenuOpen ? ' is-mobile-nav-open' : ''}`}>
      <button
        type="button"
        className="mobile-nav-backdrop"
        aria-label="Закрыть меню"
        tabIndex={mobileMenuOpen ? 0 : -1}
        onClick={() => setMobileMenuOpen(false)}
      />
      <aside
        className={`app-sidebar${sidebarOpen ? '' : ' is-collapsed'}${mobileMenuOpen ? ' is-mobile-open' : ''}`}
        id="app-primary-sidebar"
      >
        <div className="app-sidebar-top">
          <p className="app-sidebar-brand">Calendar</p>
          <p className="app-sidebar-mark" aria-hidden="true">C</p>
          <button
            type="button"
            className="mobile-sidebar-close"
            aria-label="Закрыть меню"
            onClick={() => setMobileMenuOpen(false)}
          >
            ×
          </button>
        </div>
        <nav className="app-nav" aria-label="Основная навигация" id="app-primary-nav">
          {PRIMARY_NAV.map(({ id, label }) => (
            <button type="button" key={id} aria-current={section === id ? 'page' : undefined} onClick={() => goSection(id)}>
              <NavIcon id={id} />
              <span className="app-nav-label">{label}</span>
            </button>
          ))}
        </nav>
        <div className="app-sidebar-footer">
          <button
            type="button"
            className="app-sidebar-toggle"
            aria-expanded={sidebarOpen}
            aria-controls="app-primary-nav"
            aria-label={sidebarOpen ? 'Свернуть меню' : 'Открыть меню'}
            title={sidebarOpen ? 'Свернуть меню' : 'Открыть меню'}
            onClick={() => setSidebarOpen((open) => !open)}
          >
            <span className="app-sidebar-toggle-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3.5" y="4.5" width="17" height="15" rx="2.5" />
                <path d="M9.5 4.5v15" />
                {sidebarOpen ? (
                  <path d="M14.25 9.5 11.75 12l2.5 2.5" />
                ) : (
                  <path d="M12.75 9.5 15.25 12l-2.5 2.5" />
                )}
              </svg>
            </span>
            <span className="app-sidebar-toggle-label">{sidebarOpen ? 'Свернуть' : 'Меню'}</span>
          </button>
        </div>
      </aside>

      <nav className="app-bottom-nav" aria-label="Быстрая навигация">
        {PRIMARY_NAV.map(({ id, label }) => (
          <button type="button" key={id} aria-current={section === id ? 'page' : undefined} onClick={() => goSection(id)}>
            <NavIcon id={id} />
            <span className="app-nav-label">{label}</span>
          </button>
        ))}
      </nav>

      <div className="app-main">
      <div className="mobile-app-bar">
        <button
          type="button"
          className="mobile-menu-btn"
          aria-expanded={mobileMenuOpen}
          aria-controls="app-primary-sidebar"
          aria-label="Открыть меню"
          onClick={() => setMobileMenuOpen(true)}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
        <p className="mobile-app-bar-title">Calendar</p>
      </div>
      <div className="assistant-section" hidden={section !== 'assistant'}>
        <AiChatPanel onApplied={() => void refresh()} />
      </div>

      {section === 'calendar' && (
        <>
          <header className="calendar-header">
            <div>
              <p className="eyebrow">
                {view === 'now' ? 'Сейчас' : view === 'day' ? 'День' : view === 'week' ? 'Неделя' : 'Месяц'}
              </p>
              <h1 className="calendar-title">
                {view === 'now' ? (
                  'Сейчас'
                ) : (
                  <>
                    <span className="calendar-title-weekday">{titleParts.weekday}</span>
                    <span className="calendar-title-rest">{titleParts.rest}</span>
                  </>
                )}
              </h1>
            </div>
            <div className="toolbar toolbar-scroll">
              <div className="toolbar-group" role="group" aria-label="Дата">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setSelectedDate(addDays(selectedDate, view === 'week' ? -7 : -1))}
                  aria-label={view === 'week' ? 'Предыдущая неделя' : 'Предыдущий день'}
                >
                  ←
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => { setSelectedDate(todayKey); setView(view === 'week' ? 'week' : 'day') }}>Сегодня</button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => setSelectedDate(addDays(selectedDate, view === 'week' ? 7 : 1))}
                  aria-label={view === 'week' ? 'Следующая неделя' : 'Следующий день'}
                >
                  →
                </button>
              </div>
              <div className="toolbar-group" role="group" aria-label="Вид">
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'now'} onClick={() => setView('now')}>Сейчас</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'day'} onClick={() => setView('day')}>День</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'week'} onClick={() => setView('week')}>Неделя</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'month'} onClick={() => setView('month')}>Месяц</button>
              </div>
              <button type="button" className="btn btn-primary desktop-new-event" onClick={createAtNow}>Новое событие</button>
            </div>
          </header>
          <div className="filters">
            <label>Поиск<input aria-label="Поиск" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /></label>
            <CategoryFilter services={services} value={categoryFilter} onChange={setCategoryFilter} />
          </div>
          {searchQuery.trim() !== '' && (
            <SearchResults services={services} query={searchQuery} onSelect={(hit) => void jumpFromSearch(hit)} />
          )}
          {view === 'now' && <SmartDayPanel services={services} now={now} compact />}
          {view === 'day' && (
            <section
              ref={dayTimelineRef}
              className={`day-timeline${events.length === 0 ? ' is-empty' : ''}`}
              aria-label={`Расписание на ${selectedDate}`}
              onTouchStart={(event) => {
                touchStartX.current = event.changedTouches[0]?.clientX
                touchStartY.current = event.changedTouches[0]?.clientY
              }}
              onTouchEnd={(event) => {
                const startX = touchStartX.current
                const startY = touchStartY.current
                const endX = event.changedTouches[0]?.clientX
                const endY = event.changedTouches[0]?.clientY
                touchStartX.current = undefined
                touchStartY.current = undefined
                if (startX === undefined || startY === undefined || endX === undefined || endY === undefined) return
                const dx = endX - startX
                const dy = endY - startY
                if (Math.abs(dx) < 60 || Math.abs(dx) <= Math.abs(dy)) return
                setSelectedDate((date) => addDays(date, dx < 0 ? 1 : -1))
              }}
            >
              {(timedEvents.length === 0 && allDayEvents.length === 0 && dayPlans.length === 0) && (
                <div className="day-empty" role="status">
                  <p className="empty-state">На этот день событий нет</p>
                  <button type="button" className="btn btn-primary desktop-new-event" onClick={createAtNow}>Создать событие</button>
                </div>
              )}
              {allDayEvents.length > 0 && (
                <div className="all-day-strip" aria-label="События на весь день">
                  {allDayEvents.map((event) => (
                    <button
                      type="button"
                      key={event.id}
                      className="all-day-chip"
                      style={{ ['--event-bg' as string]: event.color }}
                      onClick={() => openEvent(event)}
                    >
                      {event.title}
                    </button>
                  ))}
                </div>
              )}
              {dayVisibleHours.map((hour) => {
                const rowClass = [
                  'hour-row',
                  showNowLine && hour < nowHour ? 'is-past' : '',
                  showNowLine && hour === nowHour ? 'is-now' : '',
                ].filter(Boolean).join(' ')
                return (
                  <div className={rowClass} key={hour} data-hour={hour}>
                    <span>{String(hour).padStart(2, '0')}:00</span>
                    <button
                      type="button"
                      className="hour-slot"
                      aria-label={`Создать событие в ${hour}:00`}
                      onDragOver={allowDayDrag ? (event) => event.preventDefault() : undefined}
                      onDrop={allowDayDrag ? () => void moveToHour(hour) : undefined}
                      onClick={() => createAtHour(hour)}
                    />
                  </div>
                )
              })}
              {showNowLine && dayVisibleHours.includes(nowHour) && (
                <div
                  className="now-line"
                  style={{ top: `${displayOffsetPx(dayVisibleHours, nowHour, nowMinute)}px` }}
                  aria-hidden="true"
                />
              )}
              <div className="events-layer" style={{ height: `${dayVisibleHours.length * HOUR_ROW_PX}px` }}>
                {dayPlans.map((plan) => {
                  const duration = Math.max(56, (Date.parse(plan.endAt) - Date.parse(plan.startAt)) / 60_000 * HOUR_ROW_PX / 60)
                  return (
                    <article
                      key={`plan-${plan.id}`}
                      className="event-block plan-on-day"
                      style={{
                        top: `${displayOffsetPx(dayVisibleHours, eventHour(plan))}px`,
                        height: `${duration}px`,
                        ['--event-bg' as string]: plan.color,
                      }}
                    >
                      <strong>План · {plan.title}</strong>
                    </article>
                  )
                })}
                {timedEvents.map((event) => (
                  <EventBlock
                    event={event}
                    topPx={displayOffsetPx(dayVisibleHours, eventHour(event))}
                    allowDrag={allowDayDrag && !event.allDay}
                    onDrag={() => setDragged(event)}
                    onResize={() => { setEditing(event); setDraft({ title: event.title, description: event.description, startAt: event.startAt, endAt: new Date(Date.parse(event.endAt) + 30 * 60_000).toISOString(), color: event.color, allDay: event.allDay, categoryId: event.categoryId }) }}
                    onEdit={() => openEvent(event)}
                    onDelete={() => void remove(event.id)}
                    key={event.id}
                  />
                ))}
              </div>
            </section>
          )}
          {view === 'week' && (
            <WeekCalendar
              calendar={calendar}
              plans={services.plans}
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
              onEditEvent={openEvent}
              onOpenPlan={(planId) => {
                setFocusPlanId(planId)
                setDockOpen(true)
              }}
              onCreateAt={createAt}
              onMoveEvent={(eventId, date, hour) => {
                const startAt = zonedInputToIso(
                  `${date}T${String(hour).padStart(2, '0')}:00`,
                  calendar.calendar.timezone,
                )
                if (eventId.includes('::')) {
                  void calendar.moveEvent(eventId, startAt).then(() => refresh())
                  return
                }
                void calendar.moveEvent(eventId, startAt).then(() => refresh())
              }}
              now={now}
              visibleHoursPref={visibleHoursPref}
              boardRevision={boardRevision}
            />
          )}
          {view === 'month' && (
            <MonthCalendar
              calendar={calendar}
              selectedDate={selectedDate}
              now={now}
              onSelectDate={setSelectedDate}
              onOpenDay={(date) => { setSelectedDate(date); setView('day') }}
              boardRevision={boardRevision}
            />
          )}          {view !== 'now' && (
            <details className="calendar-dock" open={dockOpen || undefined} onToggle={(event) => setDockOpen((event.target as HTMLDetailsElement).open)}>
              <summary>Планы и задачи на день</summary>
              <div className="dock-body">
                <PlansPanel
                  services={services}
                  selectedDate={selectedDate}
                  boardRevision={boardRevision}
                  focusPlanId={focusPlanId}
                  onFocusConsumed={() => setFocusPlanId(undefined)}
                  onChanged={() => void refresh()}
                />
                <TodayTasksPanel services={services} selectedDate={selectedDate} boardRevision={boardRevision} />
              </div>
            </details>
          )}
          <button
            type="button"
            className="fab-new-event"
            onClick={createAtNow}
            aria-label="Новое событие"
          >
            +
          </button>
        </>
      )}

      {section === 'tasks' && <TasksSection services={services} boardRevision={boardRevision} />}
      {section === 'lists' && <ListsSection services={services} boardRevision={boardRevision} />}
      {section === 'trash' && <TrashSection services={services} boardRevision={boardRevision} onRestored={() => void refresh()} />}
      {section === 'settings' && (
        <SettingsSection
          services={services}
          theme={theme}
          onTheme={setTheme}
          visibleHours={visibleHoursPref}
          onVisibleHours={(value) => setVisibleHoursPref(normalizeVisibleHoursPreference(value))}
          notificationsEnabled={notificationsEnabled}
          onNotifications={async (enabled) => {
            if (enabled && typeof Notification !== 'undefined' && Notification.permission === 'default') {
              await Notification.requestPermission()
            }
            setNotificationsEnabled(enabled && (typeof Notification === 'undefined' || Notification.permission === 'granted'))
            setStatus(enabled ? 'Напоминания: вкладка открыта (~30с) или PWA через service worker' : undefined)
          }}
          onExport={async () => {
            const backup = await exportBackup(services.repositories, now().toISOString())
            const blob = new Blob([JSON.stringify(backup, null, 2)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const anchor = document.createElement('a')
            anchor.href = url
            anchor.download = 'personal-calendar-backup.json'
            anchor.click()
            URL.revokeObjectURL(url)
          }}
          onImport={async (file) => {
            const text = await file.text()
            if (!window.confirm('Импорт заменит текущие локальные данные. Продолжить?')) return
            await importBackupReplace(services.repositories, JSON.parse(text) as unknown)
            setStatus('Импорт выполнен (режим замены)')
            await refresh()
          }}
          onLogout={onLogout}
        />
      )}

      {draft !== undefined && (
        <EventForm
          key={editing?.id ?? `new-${draft.startAt}`}
          draft={draft}
          timezone={calendar.calendar.timezone}
          reminders={services.reminders}
          categories={services.categories}
          editingId={editing?.id}
          onCancel={() => { setDraft(undefined); setEditing(undefined) }}
          onSubmit={async (nextDraft, offsets) => submit(nextDraft, offsets)}
        />
      )}
      {pendingScope !== undefined && <ScopeDialog kind={pendingScope.kind} onCancel={() => setPendingScope(undefined)} onChoose={(scope) => void applyScope(scope)} />}
      {warning !== undefined && <p className="status-banner" role="status">{warning}</p>}
      {status !== undefined && <p className="status-banner" role="status">{status}</p>}
      </div>
    </main>
  )
}

function EventBlock({
  event,
  topPx,
  allowDrag,
  onDrag,
  onResize,
  onEdit,
  onDelete,
}: {
  event: Event
  topPx: number
  allowDrag: boolean
  onDrag: () => void
  onResize: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const duration = Math.max(56, (Date.parse(event.endAt) - Date.parse(event.startAt)) / 60_000 * HOUR_ROW_PX / 60)
  return (
    <article
      draggable={allowDrag}
      onDragStart={allowDrag ? onDrag : undefined}
      className={`event-block${allowDrag ? '' : ' no-drag'}`}
      tabIndex={0}
      style={{
        top: `${topPx}px`,
        height: `${duration}px`,
        ['--event-bg' as string]: event.color,
      }}
    >
      <strong>{event.title}</strong>
      <div className="event-block-actions">
        <button type="button" onClick={onEdit}>Изменить</button>
        <button type="button" onClick={onDelete}>Удалить</button>
        {allowDrag && (
          <button type="button" className="resize-handle" aria-label="Увеличить длительность на 30 минут" onClick={onResize} />
        )}
      </div>
    </article>
  )
}

function ScopeDialog({ kind, onCancel, onChoose }: { kind: 'edit' | 'delete'; onCancel: () => void; onChoose: (scope: EditScope | DeleteScope) => void }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  return (
    <div className="event-form-backdrop" role="presentation" onClick={onCancel}>
      <div className="event-form-card" role="dialog" aria-label={kind === 'edit' ? 'Область изменения' : 'Область удаления'} onClick={(event) => event.stopPropagation()}>
        <h2>{kind === 'edit' ? 'Изменить повторение' : 'Удалить повторение'}</h2>
        <div className="form-actions">
          <button type="button" className="btn btn-primary" onClick={() => onChoose('this')}>Только это</button>
          {kind === 'edit' && <button type="button" className="btn btn-ghost" onClick={() => onChoose('thisAndFollowing')}>Это и следующие</button>}
          <button type="button" className="btn btn-ghost" onClick={() => onChoose('series')}>Всю серию</button>
          <button type="button" className="btn btn-ghost" onClick={onCancel}>Отмена</button>
        </div>
      </div>
    </div>
  )
}

function EventForm({ draft, timezone, reminders, categories, editingId, onCancel, onSubmit }: {
  draft: EventDraft
  timezone: string
  reminders: LocalRemindersService
  categories: LocalCategoriesService
  editingId?: string
  onCancel: () => void
  onSubmit: (draft: EventDraft, reminderOffsets: number[]) => Promise<void>
}) {
  type RepeatMode = 'never' | 'daily' | 'every_n_days' | RecurrenceDraft['frequency']
  const initialInterval = Math.max(1, draft.recurrence?.interval ?? 1)
  const [value, setValue] = useState(draft)
  const [allDay, setAllDay] = useState(Boolean(draft.allDay))
  const [categoryList, setCategoryList] = useState<Awaited<ReturnType<LocalCategoriesService['list']>>>([])
  const [repeat, setRepeat] = useState<RepeatMode>(() => {
    if (draft.recurrence === undefined) return 'never'
    if (draft.recurrence.frequency === 'daily' && initialInterval > 1) return 'every_n_days'
    return draft.recurrence.frequency
  })
  const [intervalDays, setIntervalDays] = useState(String(initialInterval > 1 ? initialInterval : 2))
  const [weekdays, setWeekdays] = useState<Weekday[]>(draft.recurrence?.weekdays ?? [])
  const [endMode, setEndMode] = useState<'never' | 'until' | 'count'>(
    draft.recurrence?.untilDate !== undefined ? 'until' : draft.recurrence?.occurrenceCount !== undefined ? 'count' : 'never',
  )
  const [untilDate, setUntilDate] = useState(draft.recurrence?.untilDate ?? '')
  const [occurrenceCount, setOccurrenceCount] = useState(String(draft.recurrence?.occurrenceCount ?? 10))
  const [selectedReminders, setSelectedReminders] = useState<number[]>([])

  useEffect(() => {
    void categories.list().then(setCategoryList)
  }, [categories])

  useEffect(() => {
    const seriesId = editingId?.includes('::') ? editingId.split('::')[0] : editingId
    if (seriesId === undefined) return
    void reminders.listForEvent(seriesId).then((items) => setSelectedReminders(items.map((item) => item.offsetMinutes)))
  }, [editingId, reminders])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onCancel() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancel])

  const toggleWeekday = (day: Weekday) => {
    setWeekdays((current) => current.includes(day) ? current.filter((item) => item !== day) : [...current, day].sort((a, b) => a - b))
  }

  const submit = async () => {
    const parsedInterval = Math.max(2, Math.trunc(Number(intervalDays)) || 2)
    const recurrence: RecurrenceDraft | undefined = repeat === 'never'
      ? undefined
      : {
          frequency: repeat === 'every_n_days' ? 'daily' : repeat,
          interval: repeat === 'every_n_days' ? parsedInterval : 1,
          weekdays: repeat === 'weekdays' || repeat === 'weekly' ? weekdays : [],
          dayOfMonth: repeat === 'monthly' ? Number(isoToZonedInput(value.startAt, timezone).slice(8, 10)) : undefined,
          untilDate: endMode === 'until' && untilDate !== '' ? untilDate : undefined,
          occurrenceCount: endMode === 'count' ? Number(occurrenceCount) : undefined,
        }
    await onSubmit({ ...value, allDay, recurrence }, selectedReminders)
  }

  const dayValue = isoToZonedInput(value.startAt, timezone).slice(0, 10)

  return (
    <div className="event-form-backdrop" role="presentation" onClick={onCancel}>
      <form className="event-form-card" onClick={(event) => event.stopPropagation()} onSubmit={(event) => { event.preventDefault(); void submit() }}>
        <h2>Событие</h2>
        <label>Название<input required value={value.title} onChange={(event) => setValue({ ...value, title: event.target.value })} /></label>
        <label>
          Категория
          <select
            aria-label="Категория события"
            value={value.categoryId ?? ''}
            onChange={(event) => setValue({ ...value, categoryId: event.target.value || undefined })}
          >
            <option value="">Без категории</option>
            {categoryList.map((category) => (
              <option key={category.id} value={category.id}>{category.name}</option>
            ))}
          </select>
        </label>
        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={allDay}
            onChange={(event) => {
              const next = event.target.checked
              setAllDay(next)
              if (next) {
                const bounds = allDayBounds(dayValue, timezone)
                setValue({ ...value, ...bounds })
              }
            }}
          />
          Весь день
        </label>
        {allDay ? (
          <label>
            Дата
            <input
              required
              type="date"
              value={dayValue}
              onChange={(event) => {
                const bounds = allDayBounds(event.target.value, timezone)
                setValue({ ...value, ...bounds })
              }}
            />
          </label>
        ) : (
          <>
            <label>Начало<input required type="datetime-local" value={isoToZonedInput(value.startAt, timezone)} onChange={(event) => {
              const nextStart = zonedInputToIso(event.target.value, timezone)
              const durationMs = Math.max(60_000, Date.parse(value.endAt) - Date.parse(value.startAt))
              setValue({
                ...value,
                startAt: nextStart,
                endAt: new Date(Date.parse(nextStart) + durationMs).toISOString(),
              })
            }} /></label>
            <label>Окончание<input required type="datetime-local" value={isoToZonedInput(value.endAt, timezone)} onChange={(event) => setValue({ ...value, endAt: zonedInputToIso(event.target.value, timezone) })} /></label>
          </>
        )}

        <details className="form-disclosure" open={repeat !== 'never'}>
          <summary>Повтор</summary>
          <fieldset>
            <legend className="sr-only">Повтор</legend>
            <label><input type="radio" name="repeat" checked={repeat === 'never'} onChange={() => setRepeat('never')} /> Без повтора</label>
            <label><input type="radio" name="repeat" checked={repeat === 'daily'} onChange={() => setRepeat('daily')} /> Каждый день</label>
            <label><input type="radio" name="repeat" checked={repeat === 'every_n_days'} onChange={() => setRepeat('every_n_days')} /> Раз в N дней</label>
            {repeat === 'every_n_days' && (
              <label>
                Каждые
                <input
                  aria-label="Интервал в днях"
                  type="number"
                  min={2}
                  max={365}
                  value={intervalDays}
                  onChange={(event) => setIntervalDays(event.target.value)}
                />
                дн.
              </label>
            )}
            <label><input type="radio" name="repeat" checked={repeat === 'weekly'} onChange={() => setRepeat('weekly')} /> Каждую неделю</label>
            <label><input type="radio" name="repeat" checked={repeat === 'weekdays'} onChange={() => setRepeat('weekdays')} /> По дням недели</label>
            <label><input type="radio" name="repeat" checked={repeat === 'monthly'} onChange={() => setRepeat('monthly')} /> Каждый месяц</label>
          </fieldset>
          {(repeat === 'weekly' || repeat === 'weekdays') && (
            <fieldset>
              <legend>Дни недели</legend>
              {WEEKDAY_LABELS.map((day) => (
                <label key={day.value}>
                  <input type="checkbox" checked={weekdays.includes(day.value)} onChange={() => toggleWeekday(day.value)} />
                  {day.label}
                </label>
              ))}
            </fieldset>
          )}
          {repeat !== 'never' && (
            <fieldset>
              <legend>Окончание</legend>
              <label><input type="radio" name="end" checked={endMode === 'never'} onChange={() => setEndMode('never')} /> Никогда</label>
              <label><input type="radio" name="end" checked={endMode === 'until'} onChange={() => setEndMode('until')} /> До даты</label>
              {endMode === 'until' && <input aria-label="Дата окончания повтора" type="date" value={untilDate} onChange={(event) => setUntilDate(event.target.value)} />}
              <label><input type="radio" name="end" checked={endMode === 'count'} onChange={() => setEndMode('count')} /> После N</label>
              {endMode === 'count' && <input aria-label="Число повторений" type="number" min={1} value={occurrenceCount} onChange={(event) => setOccurrenceCount(event.target.value)} />}
            </fieldset>
          )}
        </details>

        <details className="form-disclosure">
          <summary>Категория и цвет</summary>
          <label>Цвет<input aria-label="Цвет" type="color" value={value.color} onChange={(event) => setValue({ ...value, color: event.target.value })} /></label>
        </details>

        <details className="form-disclosure">
          <summary>Напоминания</summary>
          <fieldset>
            <legend className="sr-only">Напоминания</legend>
            {REMINDER_OFFSETS_MINUTES.map((offset) => (
              <label key={offset}>
                <input
                  type="checkbox"
                  checked={selectedReminders.includes(offset)}
                  onChange={() => setSelectedReminders((current) => current.includes(offset) ? current.filter((item) => item !== offset) : [...current, offset])}
                />
                за {offset >= 1440 ? `${offset / 1440} дн.` : `${offset} мин.`}
              </label>
            ))}
          </fieldset>
        </details>

        <details className="form-disclosure">
          <summary>Заметки</summary>
          <label>Заметки<textarea value={value.description} onChange={(event) => setValue({ ...value, description: event.target.value })} /></label>
        </details>

        <div className="form-actions form-actions-sticky">
          <button type="submit" className="btn btn-primary">Сохранить</button>
          <button type="button" className="btn btn-ghost" onClick={onCancel}>Отмена</button>
        </div>
      </form>
    </div>
  )
}

function CategoryFilter({ services, value, onChange }: { services: AppServices; value?: string; onChange: (id?: string) => void }) {
  const [categories, setCategories] = useState<Awaited<ReturnType<LocalCategoriesService['list']>>>([])
  useEffect(() => { void services.categories.list().then(setCategories) }, [services.categories])
  return (
    <label>Категория
      <select aria-label="Фильтр категории" value={value ?? ''} onChange={(event) => onChange(event.target.value === '' ? undefined : event.target.value)}>
        <option value="">Все</option>
        {categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}
      </select>
    </label>
  )
}

function SearchResults({
  services,
  query,
  onSelect,
}: {
  services: AppServices
  query: string
  onSelect: (hit: { type: string; id: string; title: string }) => void
}) {
  const [hits, setHits] = useState<ReturnType<typeof searchEntities>>([])
  useEffect(() => {
    void (async () => {
      const [events, plans, tasks, lists] = await Promise.all([
        services.repositories.events.listByCalendarId(services.calendar.calendar.id),
        services.repositories.plans.listByCalendarId(services.calendar.calendar.id),
        services.repositories.tasks.listByCalendarId(services.calendar.calendar.id),
        services.repositories.lists.listByCalendarId(services.calendar.calendar.id),
      ])
      setHits(searchEntities(query, { events, plans, tasks, lists }))
    })()
  }, [query, services])
  if (hits.length === 0) return <p className="empty-state" role="status">Ничего не найдено — попробуйте другое слово</p>
  return (
    <ul className="search-results">
      {hits.map((hit) => (
        <li key={`${hit.type}-${hit.id}`}>
          <button type="button" className="search-hit" onClick={() => onSelect(hit)}>
            <span className="search-hit-type">{ENTITY_TYPE_LABELS[hit.type] ?? hit.type}</span>
            <span>{hit.title}</span>
          </button>
        </li>
      ))}
    </ul>
  )
}

function TaskRow({
  title,
  completed,
  dueLabel,
  repeatLabel,
  onToggle,
  onDelete,
}: {
  title: string
  completed: boolean
  dueLabel?: string
  repeatLabel?: string
  onToggle: () => void
  onDelete?: () => void
}) {
  return (
    <li className={`task-row${completed ? ' is-completed' : ''}`}>
      <label className="task-row-main">
        <input type="checkbox" checked={completed} onChange={onToggle} />
        <span className="task-row-title">{title}</span>
      </label>
      {(repeatLabel !== undefined || dueLabel !== undefined) && (
        <span className="task-row-meta">
          {repeatLabel !== undefined && <span className="task-row-repeat">{repeatLabel}</span>}
          {dueLabel !== undefined && <span className="task-row-due">{dueLabel}</span>}
        </span>
      )}
      {onDelete !== undefined && (
        <button type="button" className="btn btn-ghost task-row-delete" aria-label="Удалить задачу" onClick={onDelete}>
          ×
        </button>
      )}
    </li>
  )
}

function TaskBucket({
  heading,
  empty,
  tasks,
  dueLabel,
  repeatLabels,
  onToggle,
  onDelete,
}: {
  heading: string
  empty: string
  tasks: Awaited<ReturnType<TasksService['listUndatedTasks']>>
  dueLabel?: string
  repeatLabels?: Record<string, string>
  onToggle: (id: string) => void
  onDelete?: (id: string) => void
}) {
  return (
    <section className="task-bucket" aria-label={heading}>
      <header className="task-bucket-header">
        <h2>{heading}</h2>
        <span className="task-bucket-count">{tasks.length}</span>
      </header>
      {tasks.length === 0 ? (
        <p className="empty-state">{empty}</p>
      ) : (
        <ul className="task-list">
          {tasks.map((task) => (
            <TaskRow
              key={task.id}
              title={task.title}
              completed={task.completed}
              dueLabel={dueLabel}
              repeatLabel={repeatLabels?.[task.id]}
              onToggle={() => onToggle(task.id)}
              onDelete={onDelete === undefined ? undefined : () => onDelete(task.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

const TASK_REPEAT_LABELS: Record<string, string> = {
  daily: 'каждый день',
  weekly: 'каждую неделю',
  weekdays: 'по будням',
  monthly: 'каждый месяц',
}

function TodayTasksPanel({ services, selectedDate, boardRevision = 0 }: { services: AppServices; selectedDate: string; boardRevision?: number }) {
  const timezone = services.calendar.calendar.timezone
  const today = dateKey(new Date(), timezone)
  const [tasks, setTasks] = useState<Awaited<ReturnType<TasksService['listTasksForDate']>>>([])
  const [repeatLabels, setRepeatLabels] = useState<Record<string, string>>({})
  const listForDay = selectedDate === today
    ? (date: string) => services.tasks.listTasksDueOnOrOverdue(date)
    : (date: string) => services.tasks.listTasksForDate(date)

  useEffect(() => {
    let cancelled = false
    void listForDay(selectedDate).then(async (next) => {
      if (cancelled) return
      setTasks(next)
      const labels: Record<string, string> = {}
      await Promise.all(next.map(async (task) => {
        if (task.recurrenceRuleId === undefined) return
        const rule = await services.tasks.getRecurrenceRule(task.recurrenceRuleId)
        if (rule !== undefined) labels[task.id] = TASK_REPEAT_LABELS[rule.frequency] ?? 'повтор'
      }))
      if (!cancelled) setRepeatLabels(labels)
    })
    return () => { cancelled = true }
  }, [services.tasks, selectedDate, boardRevision, today])

  return (
    <section className="side-panel tasks-panel is-dock" aria-label="Задачи на день">
      <h2>Задачи на день</h2>
      {tasks.length === 0 ? (
        <p className="empty-state">Нет задач на эту дату</p>
      ) : (
        <ul className="task-list">
          {tasks.map((task) => (
            <TaskRow
              key={task.id}
              title={task.title}
              completed={task.completed}
              dueLabel={task.dueDate !== undefined && task.dueDate < selectedDate ? 'Просрочено' : undefined}
              repeatLabel={repeatLabels[task.id]}
              onToggle={() => {
                void services.tasks.toggleCompleted(task.id).then(() => listForDay(selectedDate).then(setTasks))
              }}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function PlansPanel({
  services,
  selectedDate,
  boardRevision = 0,
  focusPlanId,
  onFocusConsumed,
  onChanged,
}: {
  services: AppServices
  selectedDate: string
  boardRevision?: number
  focusPlanId?: string
  onFocusConsumed?: () => void
  onChanged?: () => void
}) {
  const timezone = services.calendar.calendar.timezone
  const [plans, setPlans] = useState<Awaited<ReturnType<PlansService['listPlansInRange']>>>([])
  const [progress, setProgress] = useState<Record<string, { completed: number; total: number; percentage: number }>>({})
  const [tasksByPlan, setTasksByPlan] = useState<Record<string, Awaited<ReturnType<PlansService['listTasks']>>>>({})
  const [expanded, setExpanded] = useState<string | undefined>()
  const [title, setTitle] = useState('')
  const [startHour, setStartHour] = useState('10')
  const [newTask, setNewTask] = useState('')

  const reload = async () => {
    const items = await services.plans.listPlansInRange(selectedDate, selectedDate)
    setPlans(items)
    const nextProgress: Record<string, { completed: number; total: number; percentage: number }> = {}
    const nextTasks: Record<string, Awaited<ReturnType<PlansService['listTasks']>>> = {}
    for (const plan of items) {
      nextProgress[plan.id] = await services.plans.progress(plan.id)
      nextTasks[plan.id] = await services.plans.listTasks(plan.id)
    }
    setProgress(nextProgress)
    setTasksByPlan(nextTasks)
  }

  useEffect(() => { void reload() }, [services.plans, selectedDate, boardRevision])

  useEffect(() => {
    if (!focusPlanId) return
    setExpanded(focusPlanId)
    onFocusConsumed?.()
  }, [focusPlanId, onFocusConsumed])

  const createPlan = async () => {
    if (title.trim() === '') return
    const hour = String(Math.min(23, Math.max(0, Number(startHour) || 10))).padStart(2, '0')
    const start = zonedInputToIso(`${selectedDate}T${hour}:00`, timezone)
    const end = new Date(Date.parse(start) + 60 * 60 * 1000).toISOString()
    await services.plans.createPlan({ title: title.trim(), startAt: start, endAt: end, color: DEFAULT_COLOR })
    setTitle('')
    await reload()
    onChanged?.()
  }

  return (
    <section className="side-panel" aria-label="Планы">
      <h2>Планы</h2>
      <div className="composer-row">
        <label>
          Название плана
          <input aria-label="Название плана" value={title} onChange={(event) => setTitle(event.target.value)} />
        </label>
        <label>
          Час
          <input aria-label="Час начала плана" type="number" min={0} max={23} value={startHour} onChange={(event) => setStartHour(event.target.value)} />
        </label>
        <button type="button" className="btn btn-primary" onClick={() => void createPlan()}>Добавить план</button>
      </div>
      {plans.length === 0 ? <p className="empty-state">Нет планов на эту дату</p> : plans.map((plan) => (
        <article key={plan.id} className="plan-block" style={{ borderColor: plan.color }}>
          <button type="button" className="plan-block-toggle" onClick={() => setExpanded((id) => id === plan.id ? undefined : plan.id)}>
            <strong>{plan.title}</strong>
            <span>{progress[plan.id]?.completed ?? 0}/{progress[plan.id]?.total ?? 0} · {progress[plan.id]?.percentage ?? 0}%</span>
          </button>
          {expanded === plan.id && (
            <div className="plan-checklist">
              <ul>
                {(tasksByPlan[plan.id] ?? []).map((task, index, all) => (
                  <li key={task.id} className="plan-checklist-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={task.completed}
                        onChange={() => {
                          void services.plans.toggleTask(task.id).then(async () => {
                            await reload()
                            onChanged?.()
                          })
                        }}
                      />
                      {task.title}
                    </label>
                    <div className="reorder-actions">
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-label="Выше"
                        disabled={index === 0}
                        onClick={() => {
                          const ids = all.map((entry) => entry.id)
                          ;[ids[index - 1], ids[index]] = [ids[index]!, ids[index - 1]!]
                          void services.plans.reorderTasks(plan.id, ids).then(async () => {
                            await reload()
                            onChanged?.()
                          })
                        }}
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-label="Ниже"
                        disabled={index === all.length - 1}
                        onClick={() => {
                          const ids = all.map((entry) => entry.id)
                          ;[ids[index], ids[index + 1]] = [ids[index + 1]!, ids[index]!]
                          void services.plans.reorderTasks(plan.id, ids).then(async () => {
                            await reload()
                            onChanged?.()
                          })
                        }}
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-label="Удалить пункт"
                        onClick={() => {
                          void services.plans.deleteTask(task.id).then(async () => {
                            await reload()
                            onChanged?.()
                          })
                        }}
                      >
                        ×
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
              <div className="composer-row">
                <input
                  aria-label={`Новая задача плана ${plan.title}`}
                  value={expanded === plan.id ? newTask : ''}
                  onChange={(event) => setNewTask(event.target.value)}
                  placeholder="Пункт чек-листа"
                />
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    if (newTask.trim() === '') return
                    void services.plans.addTask(plan.id, newTask.trim()).then(async () => {
                      setNewTask('')
                      await reload()
                      onChanged?.()
                    })
                  }}
                >
                  +
                </button>
              </div>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => {
                  if (!window.confirm('Удалить план?')) return
                  void services.plans.deletePlan(plan.id).then(async () => {
                    await reload()
                    onChanged?.()
                  })
                }}
              >
                Удалить план
              </button>
            </div>
          )}
        </article>
      ))}
    </section>
  )
}

function SmartDayPanel({ services, now, compact = false }: { services: AppServices; now: () => Date; compact?: boolean }) {
  const [snapshot, setSnapshot] = useState<SmartDaySnapshot | undefined>()
  const timezone = services.calendar.calendar.timezone

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const current = now()
      const day = dateKey(current, timezone)
      const [events, plans] = await Promise.all([
        services.calendar.listEventsInRange(day, day),
        services.plans.listPlansInRange(day, day),
      ])
      if (!cancelled) setSnapshot(buildSmartDaySnapshot(events, plans, current.toISOString()))
    }
    void load()
    const timer = window.setInterval(() => { void load() }, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [services, now, timezone])

  if (snapshot === undefined) {
    return <section className={`smart-day${compact ? ' is-compact' : ''}`} aria-label="Сейчас"><p className="empty-state">Загрузка…</p></section>
  }

  return (
    <section className={`smart-day${compact ? ' is-compact' : ''}`} aria-label="Сейчас">
      {!compact && (
        <header className="calendar-header">
          <div>
            <p className="eyebrow">Сейчас</p>
            <h1>{snapshot.label}</h1>
          </div>
          <p className="smart-day-clock" aria-live="polite">
            {new Date(snapshot.now).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          </p>
        </header>
      )}
      {compact && (
        <p className="smart-day-clock" aria-live="polite">
          {new Date(snapshot.now).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          {' · '}
          {snapshot.label}
        </p>
      )}
      {snapshot.current ? (
        <article className="smart-day-card" style={{ borderColor: snapshot.current.color }}>
          <p className="eyebrow">{snapshot.current.kind === 'event' ? 'Событие' : 'План'}</p>
          <strong>{snapshot.current.title}</strong>
          <p>
            {new Date(snapshot.current.startAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
            {' — '}
            {new Date(snapshot.current.endAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          </p>
          <p>Прошло: {formatDuration(snapshot.elapsedMs ?? 0)}</p>
          <p>Осталось: {formatDuration(snapshot.remainingMs ?? 0)}</p>
          {snapshot.overlaps.length > 1 && (
            <p className="smart-day-overlap">Пересечение: {snapshot.overlaps.map((item) => item.title).join(', ')}</p>
          )}
        </article>
      ) : (
        <p className="empty-state">Сейчас свободно</p>
      )}
      {snapshot.next && (
        <article className="smart-day-next">
          <p className="eyebrow">Далее</p>
          <strong>{snapshot.next.title}</strong>
          <p>
            {new Date(snapshot.next.startAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
            {' — '}
            {new Date(snapshot.next.endAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
          </p>
        </article>
      )}
    </section>
  )
}

function TasksSection({ services, boardRevision = 0 }: { services: AppServices; boardRevision?: number }) {
  const timezone = services.calendar.calendar.timezone
  const today = dateKey(new Date(), timezone)
  const tomorrow = addDays(today, 1)
  const nextWeek = addDays(today, 7)
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [repeat, setRepeat] = useState<'never' | 'daily' | 'weekly' | 'monthly'>('never')
  const [undated, setUndated] = useState<Awaited<ReturnType<TasksService['listUndatedTasks']>>>([])
  const [todayTasks, setTodayTasks] = useState<Awaited<ReturnType<TasksService['listTasksDueOnOrOverdue']>>>([])
  const [focusTasks, setFocusTasks] = useState<Awaited<ReturnType<TasksService['listTasksForDate']>>>([])
  const [repeatLabels, setRepeatLabels] = useState<Record<string, string>>({})
  const showFocusSection = dueDate !== '' && dueDate !== today

  const loadRepeatLabels = async (tasks: Awaited<ReturnType<TasksService['listUndatedTasks']>>[]) => {
    const labels: Record<string, string> = {}
    for (const group of tasks) {
      for (const task of group) {
        if (task.recurrenceRuleId === undefined) continue
        const rule = await services.tasks.getRecurrenceRule(task.recurrenceRuleId)
        if (rule !== undefined) labels[task.id] = TASK_REPEAT_LABELS[rule.frequency] ?? 'повтор'
      }
    }
    setRepeatLabels(labels)
  }

  const refresh = () => {
    void Promise.all([
      services.tasks.listUndatedTasks(),
      services.tasks.listTasksDueOnOrOverdue(today),
      showFocusSection ? services.tasks.listTasksForDate(dueDate) : Promise.resolve([]),
    ]).then(([nextUndated, nextToday, nextFocus]) => {
      setUndated(nextUndated)
      setTodayTasks(nextToday)
      setFocusTasks(nextFocus)
      void loadRepeatLabels([nextUndated, nextToday, nextFocus])
    })
  }

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      services.tasks.listUndatedTasks(),
      services.tasks.listTasksDueOnOrOverdue(today),
      showFocusSection ? services.tasks.listTasksForDate(dueDate) : Promise.resolve([]),
    ]).then(([nextUndated, nextToday, nextFocus]) => {
      if (cancelled) return
      setUndated(nextUndated)
      setTodayTasks(nextToday)
      setFocusTasks(nextFocus)
      void loadRepeatLabels([nextUndated, nextToday, nextFocus])
    })
    return () => { cancelled = true }
  }, [services.tasks, today, dueDate, showFocusSection, boardRevision])

  const focusHeading =
    dueDate === tomorrow ? 'Завтра' : dueDate === nextWeek ? 'Через неделю' : dueDate

  return (
    <section className="side-panel tasks-panel is-flat" aria-label="Задачи">
      <h1>Задачи</h1>

      <form
        className="task-composer"
        onSubmit={(event) => {
          event.preventDefault()
          const effectiveDue = dueDate === '' ? (repeat === 'never' ? undefined : today) : dueDate
          const recurrence: RecurrenceDraft | undefined = repeat === 'never' || effectiveDue === undefined
            ? undefined
            : {
                frequency: repeat,
                interval: 1,
                weekdays: repeat === 'weekly' ? [weekdayOf(effectiveDue, timezone)] : [],
                dayOfMonth: repeat === 'monthly' ? Number(effectiveDue.slice(8, 10)) : undefined,
              }
          void services.tasks.createTask({ title, dueDate: effectiveDue, recurrence }).then(() => {
            setTitle('')
            setRepeat('never')
            refresh()
          })
        }}
      >
        <div className="task-composer-main">
          <input
            className="task-composer-title"
            aria-label="Название"
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Что нужно сделать"
            autoComplete="off"
          />
          <button type="submit" className="btn btn-primary">Добавить</button>
        </div>
        <div className="task-composer-meta">
          <div className="date-shortcuts" role="group" aria-label="Дата для новой задачи">
            <button type="button" aria-pressed={dueDate === ''} onClick={() => { setDueDate(''); if (repeat !== 'never') setRepeat('never') }}>Без даты</button>
            <button type="button" aria-pressed={dueDate === today} onClick={() => setDueDate(today)}>Сегодня</button>
            <button type="button" aria-pressed={dueDate === tomorrow} onClick={() => setDueDate(tomorrow)}>Завтра</button>
            <button type="button" aria-pressed={dueDate === nextWeek} onClick={() => setDueDate(nextWeek)}>Через неделю</button>
          </div>
          <label className="task-composer-field">
            <span className="task-composer-field-label">Дата</span>
            <input
              className="task-composer-date"
              aria-label="Дата"
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
            />
          </label>
          <label className="task-composer-field">
            <span className="task-composer-field-label">Повтор</span>
            <select
              className="task-composer-repeat"
              aria-label="Повтор"
              value={repeat}
              onChange={(event) => {
                const value = event.target.value as typeof repeat
                setRepeat(value)
                if (value !== 'never' && dueDate === '') setDueDate(today)
              }}
            >
              <option value="never">Без повтора</option>
              <option value="daily">Каждый день</option>
              <option value="weekly">Каждую неделю</option>
              <option value="monthly">Каждый месяц</option>
            </select>
          </label>
        </div>
        {showFocusSection && (
          <p className="task-composer-hint">Ниже также список на {focusHeading}</p>
        )}
      </form>

      <div className="task-buckets">
        <TaskBucket
          heading="Без даты"
          empty="Пока пусто"
          tasks={undated}
          repeatLabels={repeatLabels}
          onToggle={(id) => { void services.tasks.toggleCompleted(id).then(refresh) }}
          onDelete={(id) => { void services.tasks.deleteTask(id).then(refresh) }}
        />
        <TaskBucket
          heading="Сегодня"
          empty="На сегодня задач нет"
          tasks={todayTasks}
          repeatLabels={repeatLabels}
          onToggle={(id) => { void services.tasks.toggleCompleted(id).then(refresh) }}
          onDelete={(id) => { void services.tasks.deleteTask(id).then(refresh) }}
        />
        {showFocusSection && (
          <TaskBucket
            heading={focusHeading}
            empty="На эту дату задач нет"
            tasks={focusTasks}
            dueLabel={focusHeading}
            repeatLabels={repeatLabels}
            onToggle={(id) => { void services.tasks.toggleCompleted(id).then(refresh) }}
            onDelete={(id) => { void services.tasks.deleteTask(id).then(refresh) }}
          />
        )}
      </div>
    </section>
  )
}

function ListsSection({ services, boardRevision = 0 }: { services: AppServices; boardRevision?: number }) {
  const [title, setTitle] = useState('')
  const [lists, setLists] = useState<Awaited<ReturnType<LocalListsService['listAll']>>>([])
  const [itemTitle, setItemTitle] = useState<Record<string, string>>({})
  const refresh = () => { void services.lists.listAll().then(setLists) }
  useEffect(() => {
    let cancelled = false
    void services.lists.listAll().then((items) => { if (!cancelled) setLists(items) })
    return () => { cancelled = true }
  }, [services.lists, boardRevision])
  return (
    <section className="side-panel lists-panel is-flat" aria-label="Списки">
      <h1>Списки</h1>

      <form
        className="task-composer"
        onSubmit={(event) => {
          event.preventDefault()
          void services.lists.create({ title }).then(() => { setTitle(''); refresh() })
        }}
      >
        <div className="task-composer-main">
          <input
            className="task-composer-title"
            aria-label="Название списка"
            required
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Например, Покупки"
            autoComplete="off"
          />
          <button type="submit" className="btn btn-primary">Создать список</button>
        </div>
      </form>

      {lists.length === 0 ? (
        <p className="empty-state">Списков пока нет</p>
      ) : (
        <div className="list-stack">
          {lists.map(({ list, items }) => (
            <article key={list.id} className="list-card is-flat">
              <header className="task-bucket-header">
                <h2>{list.title}</h2>
                <span className="task-bucket-count">{items.length}</span>
              </header>
              {items.length === 0 ? (
                <p className="empty-state">Пустой список</p>
              ) : (
                <ul className="task-list">
                  {items.map((item, index) => (
                    <li key={item.id} className="list-item-row">
                      <TaskRow
                        title={item.title}
                        completed={item.completed}
                        onToggle={() => { void services.lists.toggleItem(item.id).then(refresh) }}
                        onDelete={() => { void services.lists.deleteItem(item.id).then(refresh) }}
                      />
                      <div className="reorder-actions">
                        <button
                          type="button"
                          className="btn btn-ghost"
                          aria-label="Выше"
                          disabled={index === 0}
                          onClick={() => {
                            const ids = items.map((entry) => entry.id)
                            ;[ids[index - 1], ids[index]] = [ids[index]!, ids[index - 1]!]
                            void services.lists.reorderItems(list.id, ids).then(refresh)
                          }}
                        >
                          ↑
                        </button>
                        <button
                          type="button"
                          className="btn btn-ghost"
                          aria-label="Ниже"
                          disabled={index === items.length - 1}
                          onClick={() => {
                            const ids = items.map((entry) => entry.id)
                            ;[ids[index], ids[index + 1]] = [ids[index + 1]!, ids[index]!]
                            void services.lists.reorderItems(list.id, ids).then(refresh)
                          }}
                        >
                          ↓
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
              <form
                className="list-item-composer"
                onSubmit={(event) => {
                  event.preventDefault()
                  const value = itemTitle[list.id] ?? ''
                  void services.lists.addItem(list.id, { title: value }).then(() => {
                    setItemTitle((current) => ({ ...current, [list.id]: '' }))
                    refresh()
                  })
                }}
              >
                <input
                  aria-label={`Элемент для ${list.title}`}
                  required
                  value={itemTitle[list.id] ?? ''}
                  onChange={(event) => setItemTitle((current) => ({ ...current, [list.id]: event.target.value }))}
                  placeholder="Новый пункт"
                />
                <button type="submit" className="btn btn-ghost">Добавить</button>
              </form>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}

function TrashSection({ services, onRestored, boardRevision = 0 }: { services: AppServices; onRestored: () => void; boardRevision?: number }) {
  const [entries, setEntries] = useState<TrashEntry[]>([])
  const load = () => {
    void Promise.all([
      services.repositories.events.list(),
      services.repositories.plans.list(),
      services.repositories.tasks.list(),
      services.repositories.lists.list(),
    ]).then(([events, plans, tasks, lists]) => {
      setEntries([
        ...collectTrash('event', events),
        ...collectTrash('plan', plans),
        ...collectTrash('task', tasks),
        ...collectTrash('list', lists),
      ])
    })
  }
  useEffect(() => {
    let cancelled = false
    void Promise.all([
      services.repositories.events.list(),
      services.repositories.plans.list(),
      services.repositories.tasks.list(),
      services.repositories.lists.list(),
    ]).then(([events, plans, tasks, lists]) => {
      if (cancelled) return
      setEntries([
        ...collectTrash('event', events),
        ...collectTrash('plan', plans),
        ...collectTrash('task', tasks),
        ...collectTrash('list', lists),
      ])
    })
    return () => { cancelled = true }
  }, [services.repositories, boardRevision])
  return (
    <section className="side-panel trash-panel is-flat" aria-label="Корзина">
      <h1>Корзина</h1>
      {entries.length === 0 ? (
        <p className="empty-state">Корзина пуста</p>
      ) : (
        <ul className="trash-list">
          {entries.map((entry) => {
            const label = 'title' in entry.entity
              ? String((entry.entity as { title?: string }).title ?? entry.entity.id)
              : entry.entity.id
            return (
              <li key={`${entry.entityType}-${entry.entity.id}`} className="trash-row">
                <div className="trash-row-main">
                  <span className="trash-row-type">{ENTITY_TYPE_LABELS[entry.entityType] ?? entry.entityType}</span>
                  <span className="trash-row-title">{label}</span>
                </div>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    void (async () => {
                      const restored = restoreEntity(entry.entity, new Date().toISOString())
                      if (entry.entityType === 'event') await services.repositories.events.put(restored as Event)
                      if (entry.entityType === 'plan') await services.repositories.plans.put(restored as never)
                      if (entry.entityType === 'task') await services.repositories.tasks.put(restored as never)
                      if (entry.entityType === 'list') await services.repositories.lists.put(restored as never)
                      load()
                      onRestored()
                    })()
                  }}
                >
                  Восстановить
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function SettingsSection({
  services, theme, onTheme, visibleHours, onVisibleHours, notificationsEnabled, onNotifications, onExport, onImport, onLogout,
}: {
  services: AppServices
  theme: 'light' | 'dark'
  onTheme: (theme: 'light' | 'dark') => void
  visibleHours: VisibleHoursPreference
  onVisibleHours: (value: VisibleHoursPreference) => void
  notificationsEnabled: boolean
  onNotifications: (enabled: boolean) => void | Promise<void>
  onExport: () => Promise<void>
  onImport: (file: File) => Promise<void>
  onLogout?: () => void
}) {
  const [categories, setCategories] = useState<Awaited<ReturnType<LocalCategoriesService['list']>>>([])
  const [newCategory, setNewCategory] = useState('')
  const [renameId, setRenameId] = useState<string | undefined>()
  const [renameValue, setRenameValue] = useState('')

  const reloadCategories = async () => {
    setCategories(await services.categories.list())
  }
  useEffect(() => { void reloadCategories() }, [services.categories])

  return (
    <section className="side-panel settings-panel">
      <h1>Настройки</h1>

      <div className="settings-block">
        <p className="settings-label">Категории</p>
        <div className="composer-row">
          <input
            aria-label="Новая категория"
            value={newCategory}
            onChange={(event) => setNewCategory(event.target.value)}
            placeholder="Название"
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => {
              if (newCategory.trim() === '') return
              void services.categories.create({ name: newCategory.trim() }).then(async () => {
                setNewCategory('')
                await reloadCategories()
              })
            }}
          >
            Добавить
          </button>
        </div>
        <ul className="settings-category-list">
          {categories.map((category) => (
            <li key={category.id}>
              {renameId === category.id ? (
                <div className="composer-row">
                  <input
                    aria-label={`Переименовать ${category.name}`}
                    value={renameValue}
                    onChange={(event) => setRenameValue(event.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      void services.categories.rename(category.id, renameValue).then(async () => {
                        setRenameId(undefined)
                        await reloadCategories()
                      })
                    }}
                  >
                    Сохранить
                  </button>
                  <button type="button" className="btn btn-ghost" onClick={() => setRenameId(undefined)}>Отмена</button>
                </div>
              ) : (
                <div className="composer-row">
                  <span>{category.name}</span>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setRenameId(category.id)
                      setRenameValue(category.name)
                    }}
                  >
                    Переименовать
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      if (!window.confirm(`Удалить категорию «${category.name}»?`)) return
                      void services.categories.softDelete(category.id).then(reloadCategories)
                    }}
                  >
                    Удалить
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="settings-block">
        <p className="settings-label" id="theme-label">Тема оформления</p>
        <div className="theme-toggle" role="group" aria-labelledby="theme-label">
          <button
            type="button"
            className="theme-option"
            aria-pressed={theme === 'light'}
            onClick={() => onTheme('light')}
          >
            <span className="theme-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
                <circle cx="12" cy="12" r="4" />
                <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
              </svg>
            </span>
            Светлая
          </button>
          <button
            type="button"
            className="theme-option"
            aria-pressed={theme === 'dark'}
            onClick={() => onTheme('dark')}
          >
            <span className="theme-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8">
                <path d="M21 14.5A8.5 8.5 0 0 1 9.5 3 7 7 0 1 0 21 14.5Z" />
              </svg>
            </span>
            Тёмная
          </button>
        </div>
      </div>

      <div className="settings-block">
        <p className="settings-label" id="visible-hours-label">Какие часы показывать</p>
        <p className="hint">Ты сам задаёшь окно дня: остальное в «День» и «Неделя» не рисуется. Например 09:00–20:00 — без ночи и раннего утра.</p>
        <div className="visible-hours-row" role="group" aria-labelledby="visible-hours-label">
          <label>
            Показывать с
            <select
              aria-label="Показывать часы с"
              value={visibleHours.startHour}
              onChange={(event) => onVisibleHours({
                startHour: Number(event.target.value),
                endHour: visibleHours.endHour,
              })}
            >
              {HOUR_OPTIONS.map((hour) => (
                <option key={`start-${hour}`} value={hour}>{String(hour).padStart(2, '0')}:00</option>
              ))}
            </select>
          </label>
          <label>
            до
            <select
              aria-label="Показывать часы до"
              value={visibleHours.endHour}
              onChange={(event) => onVisibleHours({
                startHour: visibleHours.startHour,
                endHour: Number(event.target.value),
              })}
            >
              {HOUR_OPTIONS.map((hour) => (
                <option key={`end-${hour}`} value={hour}>{String(hour).padStart(2, '0')}:00</option>
              ))}
            </select>
          </label>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => onVisibleHours({ startHour: 0, endHour: 23 })}
        >
          Показать все 24 часа
        </button>
        <p className="hint">Если в скрытом часу уже есть событие (или сейчас этот час), строка всё равно появится, чтобы событие не пропало.</p>
      </div>

      <div className="settings-block">
        <label className="settings-check">
          <input type="checkbox" checked={notificationsEnabled} onChange={(event) => void onNotifications(event.target.checked)} />
          Уведомления браузера
        </label>
        <p className="hint">
          Пока вкладка открыта — опрос раз в ~30 сек. После установки PWA (добавить на экран) уведомления идут через service worker;
          полноценный фон как у Google на iOS Safari не обещаем.
        </p>
      </div>

      <div className="settings-block">
        <h2>Клавиатура</h2>
        <ul className="shortcut-list">
          <li><kbd>N</kbd> — новое событие</li>
          <li><kbd>T</kbd> — раздел «Задачи»</li>
          <li><kbd>A</kbd> — раздел «Ассистент»</li>
          <li><kbd>←</kbd> / <kbd>→</kbd> — соседний день (в неделе — соседняя неделя)</li>
          <li><kbd>Esc</kbd> — закрыть форму</li>
        </ul>
      </div>

      <div className="settings-block">
        <h2>Данные</h2>
        <div className="form-actions">
          <button type="button" className="btn btn-primary" onClick={() => void onExport()}>Экспорт JSON</button>
        </div>
        <label className="file-import">
          <span>Импорт JSON (замена)</span>
          <input aria-label="Импорт JSON" type="file" accept="application/json" onChange={(event) => {
            const file = event.target.files?.[0]
            if (file !== undefined) void onImport(file)
          }} />
        </label>
      </div>

      {onLogout && (
        <div className="settings-block">
          <h2>Сессия</h2>
          <button type="button" className="btn" onClick={onLogout}>
            Выйти
          </button>
        </div>
      )}
    </section>
  )
}
