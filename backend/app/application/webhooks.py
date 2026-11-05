"""Webhooks (D37, wave 4): a signed hint «there are changes»; the changes feed is the source of truth.

One pending flag per subscription coalesces any number of changes into one notification. A failed
delivery is retried with growing pauses for up to 24 hours, then dropped (the feed still has it all).
"""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from sqlalchemy import select

from app.core.errors import AppError
from app.infrastructure.db import models as m

MAX_PER_GRANT = 5
RETRY_WINDOW = timedelta(hours=24)
BACKOFF_SECONDS = (30, 60, 300, 900, 1800, 3600)  # the last pause repeats
TIMEOUT_SECONDS = 5.0
BATCH = 50
log = logging.getLogger(__name__)


def validate_url(url: str) -> str:
    parts = urlsplit(url or "")
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.fragment
            or len(url) > 2048):
        raise AppError("validation_error", "Webhook URL must be https, without credentials or #fragment",
                       status_code=422)
    return url


def public_address(host: str) -> bool:
    """Never call into localhost or a private network (SSRF): every resolved address must be global."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except (OSError, UnicodeError):
        return False
    addresses = {ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos}
    return bool(addresses) and all(a.is_global for a in addresses)


def sign(secret: str, timestamp: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def send(url: str, secret: str, payload: dict) -> str | None:
    """POST one notification; returns None on 2xx, otherwise a short error."""
    if not public_address(urlsplit(url).hostname or ""):
        return "address is not public"
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    headers = {"Content-Type": "application/json", "User-Agent": "PersonalCalendar-Webhooks/1",
               "X-Calendar-Timestamp": timestamp, "X-Calendar-Signature": sign(secret, timestamp, body)}
    try:
        response = httpx.post(url, content=body, headers=headers, timeout=TIMEOUT_SECONDS, follow_redirects=False)
    except httpx.HTTPError as exc:
        return type(exc).__name__
    return None if 200 <= response.status_code < 300 else f"HTTP {response.status_code}"


def create(db, grant: m.OAuthGrantModel, url: str) -> tuple[m.WebhookSubscriptionModel, str]:
    count = len(db.scalars(select(m.WebhookSubscriptionModel.id).where(
        m.WebhookSubscriptionModel.grant_id == grant.id, m.WebhookSubscriptionModel.active.is_(True))).all())
    if count >= MAX_PER_GRANT:
        raise AppError("conflict", f"At most {MAX_PER_GRANT} webhooks per connection", status_code=409)
    secret = "pcw_" + secrets.token_urlsafe(32)
    row = m.WebhookSubscriptionModel(id=str(uuid4()), grant_id=grant.id, url=validate_url(url), secret=secret,
                                     active=True, pending=False, failures=0)
    db.add(row)
    db.flush()
    return row, secret


def mark_pending(db, owner_id: str, calendar_id: str, actor_client_id: str | None) -> None:
    """Called for every recorded change. The app that made the change is not notified about it."""
    from app.application.oauth import grant_calendar_ids
    rows = db.execute(select(m.WebhookSubscriptionModel, m.OAuthGrantModel)
                      .join(m.OAuthGrantModel, m.OAuthGrantModel.id == m.WebhookSubscriptionModel.grant_id)
                      .where(m.OAuthGrantModel.principal_id == owner_id, m.OAuthGrantModel.revoked_at.is_(None),
                             m.WebhookSubscriptionModel.active.is_(True))).all()
    now = datetime.utcnow()
    calendar = db.get(m.CalendarModel, calendar_id)
    foreign = calendar is not None and calendar.owner_id != owner_id  # an event this account was invited to
    for sub, grant in rows:
        sees = calendar_id in grant_calendar_ids(db, grant) or (foreign and "sharing.invite" in grant.scopes)
        if grant.client_id == actor_client_id or not sees:
            continue
        if not sub.pending:
            sub.pending, sub.next_attempt_at = True, now


def dispatch_due(db, now: datetime | None = None, sender=None) -> int:
    """Deliver due notifications once; returns how many were attempted."""
    from app.application.changes_feed import feed_cursor
    from app.application.oauth import grant_calendar_ids
    sender = sender or send
    now = now or datetime.utcnow()
    due = db.scalars(select(m.WebhookSubscriptionModel).where(
        m.WebhookSubscriptionModel.active.is_(True), m.WebhookSubscriptionModel.pending.is_(True),
        m.WebhookSubscriptionModel.next_attempt_at <= now).limit(BATCH)).all()
    for sub in due:
        grant = db.get(m.OAuthGrantModel, sub.grant_id)
        # Claim first: a change that lands during delivery sets pending again and is not lost.
        sub.pending = False
        db.commit()
        if grant is None or grant.revoked_at is not None:
            continue
        cursor = feed_cursor(db, grant.principal_id, grant.id, grant_calendar_ids(db, grant),
                             "sharing.invite" in grant.scopes)
        error = sender(sub.url, sub.secret, {"type": "changes", "webhook_id": sub.id, "change_cursor": cursor})
        if error is None:
            sub.failures, sub.first_failed_at, sub.last_error, sub.last_delivered_at = 0, None, None, now
        else:
            sub.failures += 1
            sub.first_failed_at = sub.first_failed_at or now
            sub.last_error = error[:255]
            if now - sub.first_failed_at >= RETRY_WINDOW:
                log.warning("webhook %s dropped a notification after 24h of failures: %s", sub.id, error)
                sub.failures, sub.first_failed_at = 0, None
            else:
                sub.pending = True
                sub.next_attempt_at = now + timedelta(seconds=BACKOFF_SECONDS[min(sub.failures, len(BACKOFF_SECONDS)) - 1])
        db.commit()
    return len(due)


async def run_forever(interval_seconds: float = 5.0) -> None:
    from app.infrastructure.db.session import SessionLocal

    def once():
        with SessionLocal() as db:
            dispatch_due(db)

    while True:
        try:
            await asyncio.to_thread(once)
        except Exception:  # noqa: BLE001 — the loop must survive any single failure
            log.exception("webhook dispatch failed")
        await asyncio.sleep(interval_seconds)
