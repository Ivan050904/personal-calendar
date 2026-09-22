import { useEffect, useMemo, useRef, useState } from 'react'
import type { Event, Weekday } from '../domain/models'
import {
  dateKey,
  eventHour,
  isoToZonedInput,
  zonedInputToIso,
  type DayCalendarService,
  type DeleteScope,
  type EditScope,
  type EventDraft,
  type RecurrenceDraft,
} from '../application/day-calendar'
import type { PlansService } from '../application/plans'
import type { TasksService } from '../application/tasks'
import type { LocalListsService } from '../application/lists'
import type { LocalCategoriesService } from '../application/categories'
import { searchEntities, filterEventsByCategory } from '../application/categories'
import type { LocalRemindersService } from '../application/reminders'
import { REMINDER_OFFSETS_MINUTES } from '../application/reminders'
import { collectTrash, restoreEntity, type TrashEntry } from '../application/trash'
import type { Repositories } from '../application/repositories'
import { exportBackup, importBackupReplace } from '../application/backup'
import { addDays } from '../application/week-calendar'
import { buildSmartDaySnapshot, formatDuration, type SmartDaySnapshot } from '../application/smart-day'
import './day-calendar.css'
import { WeekCalendar } from './WeekCalendar'
import { MonthCalendar } from './MonthCalendar'
import { AiChatPanel } from './AiChatPanel'
import './month-calendar.css'
import './app-shell.css'

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)
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
  const [draft, setDraft] = useState<EventDraft | undefined>()
  const [editing, setEditing] = useState<Event | undefined>()
  const [dragged, setDragged] = useState<Event | undefined>()
  const [warning, setWarning] = useState<string | undefined>()
  const [pendingScope, setPendingScope] = useState<{ kind: 'edit' | 'delete'; draft?: EventDraft; id: string } | undefined>()
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>()
  const [searchQuery, setSearchQuery] = useState('')
  const [theme, setTheme] = useState<'light' | 'dark'>(readStoredTheme)
  const [sidebarOpen, setSidebarOpen] = useState(readSidebarOpen)
  const [notificationsEnabled, setNotificationsEnabled] = useState(false)
  const [status, setStatus] = useState<string | undefined>()
  const [boardRevision, setBoardRevision] = useState(0)
  const touchStartX = useRef<number | undefined>(undefined)
  const touchStartY = useRef<number | undefined>(undefined)
  const dayTimelineRef = useRef<HTMLElement | null>(null)
  const coarsePointer = useCoarsePointer()
  const allowDayDrag = !coarsePointer

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try { localStorage.setItem(THEME_STORAGE_KEY, theme) } catch { /* ignore */ }
  }, [theme])

  useEffect(() => {
    try { localStorage.setItem(SIDEBAR_STORAGE_KEY, sidebarOpen ? '1' : '0') } catch { /* ignore */ }
  }, [sidebarOpen])

  const refresh = async () => {
    const listed = await calendar.listEvents(selectedDate)
    setEvents(filterEventsByCategory(listed, categoryFilter))
    setBoardRevision((value) => value + 1)
  }

  const createAtHour = (hour: number) => {
    const start = zonedInputToIso(`${selectedDate}T${String(hour).padStart(2, '0')}:00`, calendar.calendar.timezone)
    const end = new Date(new Date(start).getTime() + 60 * 60 * 1000).toISOString()
    setEditing(undefined)
    setDraft({ title: '', description: '', startAt: start, endAt: end, color: DEFAULT_COLOR })
  }

  useEffect(() => {
    let cancelled = false
    void calendar.listEvents(selectedDate).then((nextEvents) => {
      if (!cancelled) setEvents(filterEventsByCategory(nextEvents, categoryFilter))
    })
    return () => { cancelled = true }
  }, [calendar, selectedDate, categoryFilter])

  useEffect(() => {
    if (view !== 'day' || section !== 'calendar') return
    const todayKey = dateKey(now(), calendar.calendar.timezone)
    if (selectedDate !== todayKey) return
    const node = dayTimelineRef.current
    if (!node) return
    const hour = now().getHours()
    const target = Math.max(0, (hour - 1) * 64)
    node.scrollTop = target
  }, [view, section, selectedDate, calendar.calendar.timezone, now])

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
      if (event.key === 'n') createAtHour(now().getHours())
      if (event.key === 't') setSection('tasks')
      if (event.key === 'a') setSection('assistant')
      if (event.key === 'ArrowLeft') setSelectedDate((date) => addDays(date, -1))
      if (event.key === 'ArrowRight') setSelectedDate((date) => addDays(date, 1))
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
  const nowHour = now().getHours()
  const nowMinute = now().getMinutes()
  const showNowLine = view === 'day' && selectedDate === todayKey

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
    setDraft({ title: event.title, description: event.description, startAt: event.startAt, endAt: event.endAt, color: event.color })
  }

  return (
    <main className={`calendar-app${sidebarOpen ? '' : ' is-sidebar-collapsed'}`}>
      <aside className={`app-sidebar${sidebarOpen ? '' : ' is-collapsed'}`}>
        <p className="app-sidebar-brand">Calendar</p>
        <nav className="app-nav" aria-label="Основная навигация" id="app-primary-nav">
          {PRIMARY_NAV.map(({ id, label }) => (
            <button type="button" key={id} aria-current={section === id ? 'page' : undefined} onClick={() => setSection(id)}>{label}</button>
          ))}
        </nav>
        <button
          type="button"
          className="app-sidebar-toggle"
          aria-expanded={sidebarOpen}
          aria-controls="app-primary-nav"
          aria-label={sidebarOpen ? 'Свернуть меню' : 'Открыть меню'}
          onClick={() => setSidebarOpen((open) => !open)}
        >
          <span aria-hidden="true">{sidebarOpen ? '‹' : '›'}</span>
        </button>
      </aside>

      <div className="app-main">
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
                <button type="button" className="btn btn-ghost" onClick={() => setSelectedDate(addDays(selectedDate, -1))} aria-label="Предыдущий день">←</button>
                <button type="button" className="btn btn-ghost" onClick={() => { setSelectedDate(todayKey); setView('day') }}>Сегодня</button>
                <button type="button" className="btn btn-ghost" onClick={() => setSelectedDate(addDays(selectedDate, 1))} aria-label="Следующий день">→</button>
              </div>
              <div className="toolbar-group" role="group" aria-label="Вид">
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'now'} onClick={() => setView('now')}>Сейчас</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'day'} onClick={() => setView('day')}>День</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'week'} onClick={() => setView('week')}>Неделя</button>
                <button type="button" className="btn btn-ghost" aria-pressed={view === 'month'} onClick={() => setView('month')}>Месяц</button>
              </div>
              <button type="button" className="btn btn-primary desktop-new-event" onClick={() => createAtHour(now().getHours())}>Новое событие</button>
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
              {events.length === 0 && (
                <div className="day-empty" role="status">
                  <p className="empty-state">На этот день событий нет</p>
                  <button type="button" className="btn btn-primary desktop-new-event" onClick={() => createAtHour(now().getHours())}>Создать событие</button>
                </div>
              )}
              {HOURS.map((hour) => {
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
              {showNowLine && (
                <div
                  className="now-line"
                  style={{ top: `${nowHour * 64 + (nowMinute / 60) * 64}px` }}
                  aria-hidden="true"
                />
              )}
              <div className="events-layer">
                {events.map((event) => (
                  <EventBlock
                    event={event}
                    allowDrag={allowDayDrag}
                    onDrag={() => setDragged(event)}
                    onResize={() => { setEditing(event); setDraft({ title: event.title, description: event.description, startAt: event.startAt, endAt: new Date(Date.parse(event.endAt) + 30 * 60_000).toISOString(), color: event.color }) }}
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
              selectedDate={selectedDate}
              onSelectDate={setSelectedDate}
              onEditEvent={openEvent}
              now={now}
            />
          )}
          {view === 'month' && (
            <MonthCalendar
              calendar={calendar}
              selectedDate={selectedDate}
              now={now}
              onSelectDate={setSelectedDate}
              onOpenDay={(date) => { setSelectedDate(date); setView('day') }}
            />
          )}
          {view !== 'now' && (
            <details className="calendar-dock">
              <summary>Планы и задачи на день</summary>
              <div className="dock-body">
                <PlansPanel services={services} selectedDate={selectedDate} />
                <TodayTasksPanel services={services} selectedDate={selectedDate} boardRevision={boardRevision} />
              </div>
            </details>
          )}
          <button
            type="button"
            className="fab-new-event"
            onClick={() => createAtHour(now().getHours())}
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
          theme={theme}
          onTheme={setTheme}
          notificationsEnabled={notificationsEnabled}
          onNotifications={async (enabled) => {
            if (enabled && typeof Notification !== 'undefined' && Notification.permission === 'default') {
              await Notification.requestPermission()
            }
            setNotificationsEnabled(enabled && (typeof Notification === 'undefined' || Notification.permission === 'granted'))
            setStatus(enabled ? 'Уведомления зависят от разрешения браузера и жизненного цикла вкладки' : undefined)
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

      {draft !== undefined && <EventForm draft={draft} timezone={calendar.calendar.timezone} reminders={services.reminders} editingId={editing?.id} onCancel={() => { setDraft(undefined); setEditing(undefined) }} onSubmit={async (nextDraft, offsets) => submit(nextDraft, offsets)} />}
      {pendingScope !== undefined && <ScopeDialog kind={pendingScope.kind} onCancel={() => setPendingScope(undefined)} onChoose={(scope) => void applyScope(scope)} />}
      {warning !== undefined && <p className="status-banner" role="status">{warning}</p>}
      {status !== undefined && <p className="status-banner" role="status">{status}</p>}
      </div>
    </main>
  )
}

function EventBlock({
  event,
  allowDrag,
  onDrag,
  onResize,
  onEdit,
  onDelete,
}: {
  event: Event
  allowDrag: boolean
  onDrag: () => void
  onResize: () => void
  onEdit: () => void
  onDelete: () => void
}) {
  const duration = Math.max(56, (Date.parse(event.endAt) - Date.parse(event.startAt)) / 60_000 * 64 / 60)
  return (
    <article
      draggable={allowDrag}
      onDragStart={allowDrag ? onDrag : undefined}
      className={`event-block${allowDrag ? '' : ' no-drag'}`}
      tabIndex={0}
      style={{
        top: `${eventHour(event) * 64}px`,
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

function EventForm({ draft, timezone, reminders, editingId, onCancel, onSubmit }: {
  draft: EventDraft
  timezone: string
  reminders: LocalRemindersService
  editingId?: string
  onCancel: () => void
  onSubmit: (draft: EventDraft, reminderOffsets: number[]) => Promise<void>
}) {
  const [value, setValue] = useState(draft)
  const [repeat, setRepeat] = useState<'never' | RecurrenceDraft['frequency']>(draft.recurrence?.frequency ?? 'never')
  const [weekdays, setWeekdays] = useState<Weekday[]>(draft.recurrence?.weekdays ?? [])
  const [endMode, setEndMode] = useState<'never' | 'until' | 'count'>(
    draft.recurrence?.untilDate !== undefined ? 'until' : draft.recurrence?.occurrenceCount !== undefined ? 'count' : 'never',
  )
  const [untilDate, setUntilDate] = useState(draft.recurrence?.untilDate ?? '')
  const [occurrenceCount, setOccurrenceCount] = useState(String(draft.recurrence?.occurrenceCount ?? 10))
  const [selectedReminders, setSelectedReminders] = useState<number[]>([])

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
    const recurrence: RecurrenceDraft | undefined = repeat === 'never'
      ? undefined
      : {
          frequency: repeat,
          interval: 1,
          weekdays: repeat === 'weekdays' || repeat === 'weekly' ? weekdays : [],
          dayOfMonth: repeat === 'monthly' ? Number(isoToZonedInput(value.startAt, timezone).slice(8, 10)) : undefined,
          untilDate: endMode === 'until' && untilDate !== '' ? untilDate : undefined,
          occurrenceCount: endMode === 'count' ? Number(occurrenceCount) : undefined,
        }
    await onSubmit({ ...value, recurrence }, selectedReminders)
  }

  return (
    <div className="event-form-backdrop" role="presentation" onClick={onCancel}>
      <form className="event-form-card" onClick={(event) => event.stopPropagation()} onSubmit={(event) => { event.preventDefault(); void submit() }}>
        <h2>Событие</h2>
        <label>Название<input required value={value.title} onChange={(event) => setValue({ ...value, title: event.target.value })} /></label>
        <label>Начало<input required type="datetime-local" value={isoToZonedInput(value.startAt, timezone)} onChange={(event) => setValue({ ...value, startAt: zonedInputToIso(event.target.value, timezone) })} /></label>
        <label>Окончание<input required type="datetime-local" value={isoToZonedInput(value.endAt, timezone)} onChange={(event) => setValue({ ...value, endAt: zonedInputToIso(event.target.value, timezone) })} /></label>

        <details className="form-disclosure" open={repeat !== 'never'}>
          <summary>Повтор</summary>
          <fieldset>
            <legend className="sr-only">Повтор</legend>
            <label><input type="radio" name="repeat" checked={repeat === 'never'} onChange={() => setRepeat('never')} /> Без повтора</label>
            <label><input type="radio" name="repeat" checked={repeat === 'daily'} onChange={() => setRepeat('daily')} /> Каждый день</label>
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
  onToggle,
  onDelete,
}: {
  title: string
  completed: boolean
  dueLabel?: string
  onToggle: () => void
  onDelete?: () => void
}) {
  return (
    <li className={`task-row${completed ? ' is-completed' : ''}`}>
      <label className="task-row-main">
        <input type="checkbox" checked={completed} onChange={onToggle} />
        <span className="task-row-title">{title}</span>
      </label>
      {dueLabel !== undefined && <span className="task-row-due">{dueLabel}</span>}
      {onDelete !== undefined && (
        <button type="button" className="btn btn-ghost task-row-delete" onClick={onDelete}>
          Удалить
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
  onToggle,
  onDelete,
}: {
  heading: string
  empty: string
  tasks: Awaited<ReturnType<TasksService['listUndatedTasks']>>
  dueLabel?: string
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
              onToggle={() => onToggle(task.id)}
              onDelete={onDelete === undefined ? undefined : () => onDelete(task.id)}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function TodayTasksPanel({ services, selectedDate, boardRevision = 0 }: { services: AppServices; selectedDate: string; boardRevision?: number }) {
  const [tasks, setTasks] = useState<Awaited<ReturnType<TasksService['listTasksForDate']>>>([])
  useEffect(() => { void services.tasks.listTasksForDate(selectedDate).then(setTasks) }, [services.tasks, selectedDate, boardRevision])
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
              onToggle={() => {
                void services.tasks.toggleCompleted(task.id).then(() => services.tasks.listTasksForDate(selectedDate).then(setTasks))
              }}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function PlansPanel({ services, selectedDate }: { services: AppServices; selectedDate: string }) {
  const [plans, setPlans] = useState<Awaited<ReturnType<PlansService['listPlansInRange']>>>([])
  const [progress, setProgress] = useState<Record<string, { completed: number; total: number; percentage: number }>>({})
  useEffect(() => {
    void services.plans.listPlansInRange(selectedDate, selectedDate).then(async (items) => {
      setPlans(items)
      const next: Record<string, { completed: number; total: number; percentage: number }> = {}
      for (const plan of items) next[plan.id] = await services.plans.progress(plan.id)
      setProgress(next)
    })
  }, [services.plans, selectedDate])
  return (
      <section className="side-panel" aria-label="Планы">
      <h2>Планы</h2>
      {plans.length === 0 ? <p className="empty-state">Нет планов на эту дату</p> : plans.map((plan) => (
        <article key={plan.id} className="plan-block" style={{ borderColor: plan.color }}>
          <strong>{plan.title}</strong>
          <p>{progress[plan.id]?.completed ?? 0}/{progress[plan.id]?.total ?? 0} · {progress[plan.id]?.percentage ?? 0}%</p>
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
  const [undated, setUndated] = useState<Awaited<ReturnType<TasksService['listUndatedTasks']>>>([])
  const [todayTasks, setTodayTasks] = useState<Awaited<ReturnType<TasksService['listTasksForDate']>>>([])
  const [focusTasks, setFocusTasks] = useState<Awaited<ReturnType<TasksService['listTasksForDate']>>>([])
  const showFocusSection = dueDate !== '' && dueDate !== today

  const refresh = () => {
    void services.tasks.listUndatedTasks().then(setUndated)
    void services.tasks.listTasksForDate(today).then(setTodayTasks)
    if (showFocusSection) {
      void services.tasks.listTasksForDate(dueDate).then(setFocusTasks)
    } else {
      setFocusTasks([])
    }
  }

  useEffect(() => {
    let cancelled = false
    void Promise.all([
      services.tasks.listUndatedTasks(),
      services.tasks.listTasksForDate(today),
      showFocusSection ? services.tasks.listTasksForDate(dueDate) : Promise.resolve([]),
    ]).then(([nextUndated, nextToday, nextFocus]) => {
      if (cancelled) return
      setUndated(nextUndated)
      setTodayTasks(nextToday)
      setFocusTasks(nextFocus)
    })
    return () => { cancelled = true }
  }, [services.tasks, today, dueDate, showFocusSection, boardRevision])

  const focusHeading =
    dueDate === tomorrow ? 'Завтра' : dueDate === nextWeek ? 'Через неделю' : dueDate

  return (
    <section className="side-panel tasks-panel is-flat" aria-label="Задачи">
      <h1>Задачи</h1>

      <form
        className="task-composer is-line"
        onSubmit={(event) => {
          event.preventDefault()
          void services.tasks.createTask({ title, dueDate: dueDate === '' ? undefined : dueDate }).then(() => {
            setTitle('')
            refresh()
          })
        }}
      >
        <input
          className="task-composer-title"
          aria-label="Название"
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Что нужно сделать"
          autoComplete="off"
        />
        <div className="date-shortcuts" role="group" aria-label="Дата для новой задачи">
          <button type="button" aria-pressed={dueDate === ''} onClick={() => setDueDate('')}>Без даты</button>
          <button type="button" aria-pressed={dueDate === today} onClick={() => setDueDate(today)}>Сегодня</button>
          <button type="button" aria-pressed={dueDate === tomorrow} onClick={() => setDueDate(tomorrow)}>Завтра</button>
          <button type="button" aria-pressed={dueDate === nextWeek} onClick={() => setDueDate(nextWeek)}>Через неделю</button>
        </div>
        <input
          className="task-composer-date"
          aria-label="Дата"
          type="date"
          value={dueDate}
          onChange={(event) => setDueDate(event.target.value)}
        />
        <button type="submit" className="btn btn-primary">Добавить</button>
      </form>

      <div className="task-buckets">
        <TaskBucket
          heading="Без даты"
          empty="Пока пусто"
          tasks={undated}
          onToggle={(id) => { void services.tasks.toggleCompleted(id).then(refresh) }}
          onDelete={(id) => { void services.tasks.deleteTask(id).then(refresh) }}
        />
        <TaskBucket
          heading="Сегодня"
          empty="На сегодня задач нет"
          tasks={todayTasks}
          dueLabel="Сегодня"
          onToggle={(id) => { void services.tasks.toggleCompleted(id).then(refresh) }}
          onDelete={(id) => { void services.tasks.deleteTask(id).then(refresh) }}
        />
        {showFocusSection && (
          <TaskBucket
            heading={focusHeading}
            empty="На эту дату задач нет"
            tasks={focusTasks}
            dueLabel={focusHeading}
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
        className="task-composer is-line"
        onSubmit={(event) => {
          event.preventDefault()
          void services.lists.create({ title }).then(() => { setTitle(''); refresh() })
        }}
      >
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
                  {items.map((item) => (
                    <TaskRow
                      key={item.id}
                      title={item.title}
                      completed={item.completed}
                      onToggle={() => { void services.lists.toggleItem(item.id).then(refresh) }}
                    />
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
  theme, onTheme, notificationsEnabled, onNotifications, onExport, onImport, onLogout,
}: {
  theme: 'light' | 'dark'
  onTheme: (theme: 'light' | 'dark') => void
  notificationsEnabled: boolean
  onNotifications: (enabled: boolean) => void | Promise<void>
  onExport: () => Promise<void>
  onImport: (file: File) => Promise<void>
  onLogout?: () => void
}) {
  return (
    <section className="side-panel settings-panel">
      <h1>Настройки</h1>

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
        <label className="settings-check">
          <input type="checkbox" checked={notificationsEnabled} onChange={(event) => void onNotifications(event.target.checked)} />
          Уведомления браузера
        </label>
        <p className="hint">Доставка напоминаний в обычной вкладке не гарантируется (нужно разрешение и открытая вкладка).</p>
      </div>

      <div className="settings-block">
        <h2>Клавиатура</h2>
        <ul className="shortcut-list">
          <li><kbd>N</kbd> — новое событие</li>
          <li><kbd>T</kbd> — раздел «Задачи»</li>
          <li><kbd>A</kbd> — раздел «Ассистент»</li>
          <li><kbd>←</kbd> / <kbd>→</kbd> — соседний день</li>
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
