"""In-process limit on failed logins (single API instance, D18)."""
import time
from collections import defaultdict, deque
from threading import Lock

from app.core.errors import AppError

WINDOW_SECONDS = 15 * 60
MAX_PER_LOGIN = 5
MAX_PER_IP = 20

_failures: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _recent(key: str, now: float) -> deque:
    bucket = _failures[key]
    while bucket and bucket[0] <= now - WINDOW_SECONDS:
        bucket.popleft()
    return bucket


def check(login: str, ip: str) -> None:
    now = time.monotonic()
    with _lock:
        if len(_recent("login:" + login, now)) >= MAX_PER_LOGIN or len(_recent("ip:" + ip, now)) >= MAX_PER_IP:
            raise AppError("rate_limited", "Слишком много попыток входа, попробуйте позже", status_code=429)


def record_failure(login: str, ip: str) -> None:
    now = time.monotonic()
    with _lock:
        _failures["login:" + login].append(now)
        _failures["ip:" + ip].append(now)


def record_success(login: str) -> None:
    with _lock:
        _failures.pop("login:" + login, None)


def reset() -> None:
    with _lock:
        _failures.clear()
