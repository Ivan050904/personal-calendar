from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.errors import AppError


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise AppError('validation_error', 'Invalid IANA timezone', status_code=422) from None


def range_bounds(from_day: date, to_day: date, display_zone: str):
    if to_day < from_day or (to_day-from_day).days >= 31:
        raise AppError('validation_error', 'Range must contain 1–31 days', status_code=422)
    tz = zone(display_zone)
    return (datetime.combine(from_day,time(),tz).astimezone(timezone.utc),
            datetime.combine(to_day+timedelta(days=1),time(),tz).astimezone(timezone.utc))


def validate_timed_input(start: datetime, end: datetime, name: str) -> None:
    zone(name)
    if start.tzinfo is None or end.tzinfo is None or start.utcoffset() is None or end.utcoffset() is None or end <= start:
        raise AppError('validation_error', 'Aware start/end with positive duration required', status_code=422)


def normalize_all_day(row):
    if row.start_date is not None and row.end_date_exclusive is not None:
        return row.start_date, row.end_date_exclusive
    if row.start_at is None or row.end_at is None:
        raise AppError('all_day_bounds_unknown', 'Legacy all-day bounds require verified migration', status_code=409)
    tz = zone(row.timezone)
    start = row.start_at.replace(tzinfo=timezone.utc).astimezone(tz)
    end = row.end_at.replace(tzinfo=timezone.utc).astimezone(tz)
    if start.time() != time() or end.time() not in {time(23,59),time()}:
        raise AppError('all_day_bounds_unknown', 'Legacy all-day bounds require verified migration', status_code=409)
    return start.date(), end.date() + (timedelta(days=1) if end.time() == time(23,59) else timedelta())
