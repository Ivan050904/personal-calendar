import { useEffect, useMemo, useState } from 'react'
import type { Event } from '../domain/models'
import { addDays, mondayOf, weekSegments } from '../application/week-calendar'
import { dateKey, type DayCalendarService } from '../application/day-calendar'
import {
  buildVisibleHours,
  HOUR_ROW_PX,
  occupiedHours,
  type VisibleHoursPreference,
} from '../application/visible-hours'
import './week-calendar.css'

export function WeekCalendar({
  calendar,
  selectedDate,
  onSelectDate,
  onEditEvent,
  now = () => new Date(),
  visibleHoursPref,
  boardRevision = 0,
}: {
  calendar: DayCalendarService
  selectedDate: string
  onSelectDate: (date: string) => void
  onEditEvent: (event: Event) => void
  now?: () => Date
  visibleHoursPref: VisibleHoursPreference
  boardRevision?: number
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
  }, [calendar, weekStart, boardRevision])

  const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))
  const todayKey = dateKey(now(), calendar.calendar.timezone)
  const nowHour = (() => {
    const hour = new Intl.DateTimeFormat('en-US', {
      timeZone: calendar.calendar.timezone,
      hour: '2-digit',
      hourCycle: 'h23',
    }).formatToParts(now()).find((part) => part.type === 'hour')?.value
    return Number(hour ?? '0')
  })()
  const weekEnd = addDays(weekStart, 6)
  const visibleHours = useMemo(() => {
    const forced = segments.flatMap((segment) =>
      occupiedHours(segment.event.startAt, segment.event.endAt, segment.event.timezone || calendar.calendar.timezone),
    )
    if (todayKey >= weekStart && todayKey <= weekEnd) forced.push(nowHour)
    return buildVisibleHours(visibleHoursPref, forced)
  }, [segments, calendar.calendar.timezone, visibleHoursPref, weekStart, weekEnd, todayKey, nowHour])

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
        {visibleHours.map((hour) => (
          <div className="week-row" key={hour}>
            <span>{String(hour).padStart(2, '0')}:00</span>
            {days.map((day) => (
              <div className="week-cell" key={day}>
                {segments
                  .filter((segment) => segment.date === day && Math.floor(segment.top / HOUR_ROW_PX) === hour)
                  .map((segment) => (
                    <article
                      className="week-event"
                      key={`${segment.event.id}-${day}`}
                      role="button"
                      tabIndex={0}
                      style={{
                        top: `${segment.top % HOUR_ROW_PX}px`,
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
