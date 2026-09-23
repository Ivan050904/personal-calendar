import { useEffect, useMemo, useState } from 'react'
import type { Event, Plan } from '../domain/models'
import { addDays, mondayOf, weekSegments } from '../application/week-calendar'
import { dateKey, type DayCalendarService } from '../application/day-calendar'
import type { PlansService } from '../application/plans'
import {
  buildVisibleHours,
  HOUR_ROW_PX,
  occupiedHours,
  type VisibleHoursPreference,
} from '../application/visible-hours'
import './week-calendar.css'

function planAsLayoutEvent(plan: Plan): Event {
  return {
    id: `plan::${plan.id}`,
    calendarId: plan.calendarId,
    title: plan.title,
    description: plan.description ?? '',
    startAt: plan.startAt,
    endAt: plan.endAt,
    timezone: plan.timezone,
    allDay: false,
    color: plan.color,
    createdAt: plan.createdAt,
    updatedAt: plan.updatedAt,
  }
}

export function WeekCalendar({
  calendar,
  plans,
  selectedDate,
  onSelectDate,
  onEditEvent,
  onOpenPlan,
  onCreateAt,
  onMoveEvent,
  now = () => new Date(),
  visibleHoursPref,
  boardRevision = 0,
}: {
  calendar: DayCalendarService
  plans: PlansService
  selectedDate: string
  onSelectDate: (date: string) => void
  onEditEvent: (event: Event) => void
  onOpenPlan: (planId: string) => void
  onCreateAt: (date: string, hour: number) => void
  onMoveEvent?: (eventId: string, date: string, hour: number) => void
  now?: () => Date
  visibleHoursPref: VisibleHoursPreference
  boardRevision?: number
}) {
  const weekStart = mondayOf(selectedDate)
  const days = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))
  const [segments, setSegments] = useState<ReturnType<typeof weekSegments>>([])
  const [allDayByDate, setAllDayByDate] = useState<Record<string, Event[]>>({})

  useEffect(() => {
    let cancelled = false
    const weekEnd = addDays(weekStart, 6)
    void Promise.all([
      calendar.listEventsInRange(weekStart, weekEnd),
      plans.listPlansInRange(weekStart, weekEnd),
    ]).then(([events, weekPlans]) => {
      if (cancelled) return
      const timed = events.filter((event) => !event.allDay)
      const nextAllDay: Record<string, Event[]> = {}
      for (const day of Array.from({ length: 7 }, (_, index) => addDays(weekStart, index))) {
        nextAllDay[day] = events.filter((event) => {
          if (!event.allDay) return false
          const zone = event.timezone || calendar.calendar.timezone
          const start = dateKey(event.startAt, zone)
          const end = dateKey(event.endAt, zone)
          return start <= day && end >= day
        })
      }
      setAllDayByDate(nextAllDay)
      const layout = [...timed, ...weekPlans.map(planAsLayoutEvent)]
      setSegments(weekSegments(layout, weekStart, calendar.calendar.timezone))
    })
    return () => { cancelled = true }
  }, [calendar, plans, weekStart, boardRevision])

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

  const openItem = (item: Event, day: string) => {
    if (item.id.startsWith('plan::')) {
      onSelectDate(day)
      onOpenPlan(item.id.slice('plan::'.length))
      return
    }
    onEditEvent(item)
  }

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
        <div className="week-all-day-label">День</div>
        {days.map((day) => (
          <div className="week-all-day-cell" key={`allday-${day}`}>
            {(allDayByDate[day] ?? []).map((event) => (
              <button
                type="button"
                key={event.id}
                className="week-all-day-chip"
                style={{ ['--event-bg' as string]: event.color }}
                onClick={() => onEditEvent(event)}
              >
                {event.title}
              </button>
            ))}
          </div>
        ))}
        {visibleHours.map((hour) => (
          <div className="week-row" key={hour}>
            <span>{String(hour).padStart(2, '0')}:00</span>
            {days.map((day) => (
              <div className="week-cell" key={day}>
                <button
                  type="button"
                  className="week-slot"
                  aria-label={`Создать событие ${day} в ${hour}:00`}
                  onClick={() => onCreateAt(day, hour)}
                  onDragOver={(event) => {
                    if (!onMoveEvent) return
                    event.preventDefault()
                  }}
                  onDrop={(event) => {
                    if (!onMoveEvent) return
                    event.preventDefault()
                    const eventId = event.dataTransfer.getData('text/event-id')
                    if (!eventId || eventId.startsWith('plan::')) return
                    onMoveEvent(eventId, day, hour)
                  }}
                />
                {segments
                  .filter((segment) => segment.date === day && Math.floor(segment.top / HOUR_ROW_PX) === hour)
                  .map((segment) => {
                    const isPlan = segment.event.id.startsWith('plan::')
                    return (
                      <article
                        className={`week-event${isPlan ? ' is-plan' : ''}`}
                        key={`${segment.event.id}-${day}`}
                        role="button"
                        tabIndex={0}
                        draggable={!isPlan && onMoveEvent !== undefined}
                        onDragStart={(event) => {
                          if (isPlan || !onMoveEvent) return
                          event.dataTransfer.setData('text/event-id', segment.event.id)
                          event.dataTransfer.effectAllowed = 'move'
                        }}
                        style={{
                          top: `${segment.top % HOUR_ROW_PX}px`,
                          height: `${segment.height}px`,
                          left: `${segment.column / segment.columns * 100}%`,
                          width: `${100 / segment.columns}%`,
                          ['--event-bg' as string]: segment.event.color,
                        }}
                        onClick={(event) => {
                          event.stopPropagation()
                          openItem(segment.event, day)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault()
                            event.stopPropagation()
                            openItem(segment.event, day)
                          }
                        }}
                      >
                        {isPlan ? `План · ${segment.event.title}` : segment.event.title}
                      </article>
                    )
                  })}
              </div>
            ))}
          </div>
        ))}
      </div>
    </section>
  )
}
