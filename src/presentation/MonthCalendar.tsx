import { useEffect, useState } from 'react'
import { addMonths, monthGrid } from '../application/month-calendar'
import { dateKey, type DayCalendarService } from '../application/day-calendar'
import './month-calendar.css'

export function MonthCalendar({
  calendar,
  selectedDate,
  onSelectDate,
  onOpenDay,
  now = () => new Date(),
}: {
  calendar: DayCalendarService
  selectedDate: string
  onSelectDate: (date: string) => void
  now?: () => Date
  onOpenDay: (date: string) => void
}) {
  const month = selectedDate.slice(0, 7)
  const [events, setEvents] = useState<Record<string, string[]>>({})
  const days = monthGrid(month)
  const rangeStart = days[0]!
  const rangeEnd = days[41]!
  const todayKey = dateKey(now(), calendar.calendar.timezone)

  useEffect(() => {
    let cancelled = false
    void calendar.listEventsInRange(rangeStart, rangeEnd).then((items) => {
      if (cancelled) return
      setEvents(items.reduce<Record<string, string[]>>((value, event) => {
        const key = dateKey(event.startAt, event.timezone)
        ;(value[key] ??= []).push(event.title)
        return value
      }, {}))
    })
    return () => { cancelled = true }
  }, [calendar, rangeEnd, rangeStart])

  const [year, monthNumber] = month.split('-').map(Number)
  const monthLabel = new Intl.DateTimeFormat('ru-RU', { month: 'long', year: 'numeric', timeZone: calendar.calendar.timezone })
    .format(new Date(Date.UTC(year!, monthNumber! - 1, 15)))

  return (
    <section className="month-calendar" aria-label="Календарь месяца">
      <div className="month-controls">
        <button type="button" className="btn btn-ghost" onClick={() => onSelectDate(`${addMonths(month, -1)}-01`)} aria-label="Предыдущий месяц">←</button>
        <strong style={{ textTransform: 'capitalize' }}>{monthLabel}</strong>
        <button type="button" className="btn btn-ghost" onClick={() => onSelectDate(`${addMonths(month, 1)}-01`)} aria-label="Следующий месяц">→</button>
      </div>
      <div className="month-grid">
        {['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'].map((name) => <b key={name}>{name}</b>)}
        {days.map((day) => {
          const classes = [
            day.slice(0, 7) === month ? '' : 'other-month',
            day === todayKey ? 'is-today' : '',
            day === selectedDate ? 'is-selected' : '',
          ].filter(Boolean).join(' ')
          return (
            <button
              type="button"
              className={classes}
              onClick={() => onOpenDay(day)}
              key={day}
            >
              <span>{day.slice(-2)}</span>
              {(events[day] ?? []).slice(0, 2).map((title) => <small key={title}>{title}</small>)}
            </button>
          )
        })}
      </div>
    </section>
  )
}
