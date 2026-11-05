"""Read-only reconciliation; optional legacy import is outside the clone rollout."""
from sqlalchemy import select
from app.infrastructure.db import models as m


def ownership_dry_run(db):
    conflicts=[]
    calendars={r.id:r for r in db.scalars(select(m.CalendarModel))}
    for row in calendars.values():
        if row.owner_id is None:
            conflicts.append({'kind':'unknown_owner','entity_id':row.id})
    models=[m.EventModel,m.PlanModel,m.TaskModel,m.TaskListModel,m.CategoryModel]
    references={}
    for model in models:
        for row in db.scalars(select(model)):
            cal=calendars.get(row.calendar_id)
            if cal is None:
                conflicts.append({'kind':'orphan','entity_id':row.id})
            rule_id=getattr(row,'recurrence_rule_id',None)
            if rule_id:
                rule=db.get(m.RecurrenceRuleModel,rule_id)
                if rule is None:
                    conflicts.append({'kind':'orphan_rule','entity_id':row.id})
                references.setdefault(rule_id,set()).add(cal.owner_id if cal else None)
    for rule_id,owners in references.items():
        if len(owners)>1 or None in owners:
            conflicts.append({'kind':'shared_or_unknown_rule_owner','entity_id':rule_id})
    for model,key,parent in [(m.EventExceptionModel,'event_id',m.EventModel),(m.ReminderModel,'event_id',m.EventModel),(m.PlanTaskModel,'plan_id',m.PlanModel),(m.TaskListItemModel,'list_id',m.TaskListModel)]:
        for row in db.scalars(select(model)):
            if db.get(parent,getattr(row,key)) is None:
                conflicts.append({'kind':'orphan','entity_id':row.id})
    for model in [m.SettingModel,m.DraftModel]:
        for row in db.scalars(select(model)):
            if row.owner_id is None:
                conflicts.append({'kind':'unknown_owner','entity_id':row.id})
    return {'dry_run':True,'ready':not conflicts,'conflicts':conflicts,'assigned':0}
