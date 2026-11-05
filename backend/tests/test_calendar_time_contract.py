from datetime import date, datetime
import pytest
from app.core.errors import AppError


def test_berlin_dst_week_and_range_limit():
    from app.application.calendar_time import range_bounds
    lo, hi = range_bounds(date(2026,10,19),date(2026,10,25),'Europe/Berlin')
    assert (hi-lo).total_seconds()/3600 == 169
    with pytest.raises(AppError):
        range_bounds(date(2026,1,1),date(2026,2,1),'UTC')


def test_naive_timed_input_rejected():
    from app.application.calendar_time import validate_timed_input
    with pytest.raises(AppError):
        validate_timed_input(datetime(2026,10,8,9),datetime(2026,10,8,10),'UTC')
