"""Sync API v2 (D37, wave 4): the changes feed and webhook subscriptions."""
from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.application import webhooks
from app.application.changes_feed import feed_page
from app.core.calendar_actor import CalendarActor, require_actor, require_scope
from app.core.errors import AppError
from app.infrastructure.db.models import OAuthGrantModel, WebhookSubscriptionModel
from app.infrastructure.db.session import get_db
from app.infrastructure.repositories import _iso

router = APIRouter(prefix='/v2', tags=['sync'])


@router.get('/changes')
def changes(cursor: str | None = None, limit: int = Query(default=500, ge=1, le=500),
            db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    if actor.client_id:
        require_scope(actor, 'events.read')
        return feed_page(db, actor.principal_id, actor.grant_id, actor.readable_calendar_ids, cursor, limit,
                         invited='sharing.invite' in actor.scopes)
    require_scope(actor, 'calendar:read')
    return feed_page(db, actor.principal_id, None, None, cursor, limit)


def _app_grant(db: Session, actor: CalendarActor) -> OAuthGrantModel:
    if not actor.client_id:
        raise AppError('forbidden', 'Webhooks belong to connected apps', status_code=403)
    require_scope(actor, 'events.read')
    return db.get(OAuthGrantModel, actor.grant_id)


@router.post('/webhooks', status_code=201)
def create_webhook(body: dict = Body(...), db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    grant = _app_grant(db, actor)
    if set(body) != {'url'} or not isinstance(body['url'], str):
        raise AppError('validation_error', 'Body must be {"url": "https://…"}', status_code=422)
    row, secret = webhooks.create(db, grant, body['url'])
    db.commit()
    return {'id': row.id, 'url': row.url, 'secret': secret, 'created_at': _iso(row.created_at)}


@router.delete('/webhooks/{webhook_id}')
def delete_webhook(webhook_id: str, db: Session = Depends(get_db), actor: CalendarActor = Depends(require_actor)):
    grant = _app_grant(db, actor)
    row = db.get(WebhookSubscriptionModel, webhook_id)
    if row is None or row.grant_id != grant.id or not row.active:
        raise AppError('not_found', 'Webhook not found', status_code=404)
    row.active, row.pending = False, False
    db.commit()
    return {'id': webhook_id, 'deleted': True}
