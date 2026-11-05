from uuid import uuid4
from app.core.calendar_actor import CalendarActor,ensure_actor_calendar
from app.infrastructure.repositories import Repositories


def owner_entities(db,owner):
    actor=CalendarActor(owner,'folio-'+owner,frozenset({'calendar:read','calendar:write'}))
    cal=ensure_actor_calendar(db,actor,'UTC',str(uuid4()))
    repos=Repositories(db,actor)
    stamp={'createdAt':'2026-10-08T00:00:00Z','updatedAt':'2026-10-08T00:00:00Z'}
    def item(**values):
        return {'id':str(uuid4()),**stamp,**values}
    rule=repos.recurrence_rules.put(item(frequency='daily',interval=1,weekdays=[]))
    event=repos.events.put(item(calendarId=cal['id'],title='Private event',description='',startAt='2026-10-08T09:00:00Z',endAt='2026-10-08T10:00:00Z',timezone='UTC',color='#000',recurrenceRuleId=rule['id']))
    plan=repos.plans.put(item(calendarId=cal['id'],title='Private plan',startAt='2026-10-08T09:00:00Z',endAt='2026-10-08T10:00:00Z',timezone='UTC',color='#000'))
    task_list=repos.lists.put(item(calendarId=cal['id'],title='Private list'))
    return actor,{'calendars':repos.calendars.get(cal['id']),'events':event,'recurrenceRules':rule,
      'eventExceptions':repos.event_exceptions.put(item(eventId=event['id'],recurrenceRuleId=rule['id'],occurrenceKey='2026-10-08T09:00',type='cancelled')),
      'plans':plan,'planTasks':repos.plan_tasks.put(item(planId=plan['id'],title='Private step',completed=False,order=0)),
      'tasks':repos.tasks.put(item(calendarId=cal['id'],title='Private task',completed=False,recurrenceRuleId=rule['id'],dueDate='2026-10-08')),
      'lists':task_list,'listItems':repos.list_items.put(item(listId=task_list['id'],title='Private item',completed=False,order=0)),
      'categories':repos.categories.put(item(calendarId=cal['id'],name='Private category')),
      'reminders':repos.reminders.put(item(eventId=event['id'],offsetMinutes=20))}
