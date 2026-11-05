"""Own calendar accounts: login + password (D34). No email anywhere."""
import re
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.infrastructure.db.models import CalendarModel, CalendarPrincipalModel, CalendarSessionModel

LOGIN_RE = re.compile(r"^[a-z0-9_.-]{3,32}$")
PASSWORD_MIN, PASSWORD_MAX = 8, 256
PERSONAL_CALENDAR_NAME = "Личное"

_hasher = PasswordHasher()
# Verified when the login does not exist so both failures cost the same time.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-password")


def normalize_login(login: str) -> str:
    return (login or "").strip().lower()


def _validate_login(login: str) -> str:
    value = normalize_login(login)
    if not LOGIN_RE.fullmatch(value):
        raise AppError("validation_error", "Логин: 3–32 символа, латиница, цифры, _ . -", status_code=422)
    return value


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise AppError("validation_error", f"Пароль: от {PASSWORD_MIN} до {PASSWORD_MAX} символов", status_code=422)


def account_read(row: CalendarPrincipalModel) -> dict:
    return {"id": row.id, "login": row.login, "display_name": row.display_name}


def find_by_login(db: Session, login: str) -> CalendarPrincipalModel | None:
    value = normalize_login(login)
    if not value:
        return None
    return db.scalar(select(CalendarPrincipalModel).where(CalendarPrincipalModel.login == value))


def create_account(db: Session, login: str, password: str, display_name: str | None = None,
                   timezone: str = "UTC") -> CalendarPrincipalModel:
    value = _validate_login(login)
    _validate_password(password)
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise AppError("validation_error", "Invalid timezone", status_code=422) from None
    if find_by_login(db, value) is not None:
        raise AppError("conflict", "Логин занят", status_code=409)
    principal = CalendarPrincipalModel(id=str(uuid4()), login=value, password_hash=_hasher.hash(password),
                                       display_name=(display_name or "").strip() or value, active=True)
    try:
        with db.begin_nested():
            db.add(principal)
            db.flush()
            db.add(CalendarModel(id=str(uuid4()), name=PERSONAL_CALENDAR_NAME, timezone=timezone,
                                 owner_id=principal.id, default_owner=principal.id, kind="personal"))
            db.flush()
    except IntegrityError:
        raise AppError("conflict", "Логин занят", status_code=409) from None
    return principal


def _verify(row_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(row_hash or _DUMMY_HASH, password) and row_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def authenticate(db: Session, login: str, password: str) -> CalendarPrincipalModel | None:
    """Returns the active account or None; never says which part was wrong."""
    row = find_by_login(db, login)
    if row is None or not row.password_hash:
        _verify(None, password)
        return None
    if not _verify(row.password_hash, password) or not row.active:
        return None
    if _hasher.check_needs_rehash(row.password_hash):
        row.password_hash = _hasher.hash(password)
    return row


def revoke_sessions(db: Session, principal_id: str, keep_session_id: str | None = None) -> int:
    stmt = update(CalendarSessionModel).where(CalendarSessionModel.principal_id == principal_id,
                                             CalendarSessionModel.revoked_at.is_(None))
    if keep_session_id:
        stmt = stmt.where(CalendarSessionModel.id != keep_session_id)
    return db.execute(stmt.values(revoked_at=datetime.utcnow())).rowcount


def change_password(db: Session, principal_id: str, current: str, new: str, keep_session_id: str) -> None:
    row = db.get(CalendarPrincipalModel, principal_id)
    if row is None or not row.password_hash or not _verify(row.password_hash, current):
        raise AppError("unauthorized", "Неверный текущий пароль", status_code=401)
    _validate_password(new)
    row.password_hash = _hasher.hash(new)
    revoke_sessions(db, row.id, keep_session_id)


def reset_password(db: Session, login: str, new: str) -> CalendarPrincipalModel:
    """Owner-only path (script): no email exists, so the owner issues a temporary password."""
    row = find_by_login(db, login)
    if row is None:
        raise AppError("not_found", "Нет такого логина", status_code=404)
    _validate_password(new)
    row.password_hash = _hasher.hash(new)
    revoke_sessions(db, row.id)
    return row
