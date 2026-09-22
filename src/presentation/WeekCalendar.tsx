import { useEffect, useState } from 'react'
import type { Event } from '../domain/models'
import { addDays, mondayOf, weekSegments } from '../application/week-calendar'
import type { DayCalendarService } from '../application/day-calendar'
import './week-calendar.css'

const HOURS = Array.from({ length: 24 }, (_, value) => value)

export function WeekCalendar({
  calendar,
  selectedDate,
  onSelectDate,
  onEditEvent,
}: {
  calendar: DayCalendarService
  selectedDate: string
  onSelectDate: (date: string) => void
  onEditEvent: (event: Event) => void
  now?: () => Date
}) {
  const weekStart = mondayOf(selectedDate)
  const [segments, setSegments] = useState<ReturnType<typeof weekSegments>>([])

  useEffect(() => {
    let cancelled = false
    const weekEnd = addDays(weekStart, 6)
    void calendar.listEventsInRange(weekStart, weekEnd).then((events) => {
      if (!cancelled) setSegments(weekSegments(events, weekStart, calendar.calendar.timezone))
    })
    return () => { cancelled = true }
  }, [calendar, weekStart])

  const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))

  return (
    <section className="week-calendar" aria-label="Календарь недели">
      <div className="week-grid">
        <div className="week-time-head" />
        {days.map((day) => (
          <button
            type="button"
            className={`week-day-head${day === selectedDate ? ' is-selected' : ''}`}
            key={day}
            onClick={() => onSelectDate(day)}
          >
            {new Intl.DateTimeFormat('ru-RU', { weekday: 'short', day: 'numeric', timeZone: calendar.calendar.timezone }).format(new Date(`${day}T12:00:00Z`))}
          </button>
        ))}
        {HOURS.map((hour) => (
          <div className="week-row" key={hour}>
            <span>{String(hour).padStart(2, '0')}:00</span>
            {days.map((day) => (
              <div className="week-cell" key={day}>
                {segments
                  .filter((segment) => segment.date === day && Math.floor(segment.top / 64) === hour)
                  .map((segment) => (
                    <article
                      className="week-event"
                      key={`${segment.event.id}-${day}`}
                      role="button"
                      tabIndex={0}
                      style={{
                        top: `${segment.top % 64}px`,
                        height: `${segment.height}px`,
                        left: `${segment.column / segment.columns * 100}%`,
                        width: `${100 / segment.columns}%`,
                        ['--event-bg' as string]: segment.event.color,
                      }}
                      onClick={() => onEditEvent(segment.event)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          onEditEvent(segment.event)
                        }
                      }}
                    >
                      {segment.event.title}
                    </article>
                  ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}
