from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import error_body


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory local rate limit for AI endpoints (single-user MVP)."""

    def __init__(self, app, *, limit: int = 30, window_seconds: int = 60) -> None:
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if "/ai/" not in path:
            return await call_next(request)

        client = request.client.host if request.client else "local"
        now = time.time()
        bucket = self._hits[client]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return Response(
                content=str(error_body("validation_error", "Too many AI requests")).replace("'", '"'),
                status_code=429,
                media_type="application/json",
            )
        bucket.append(now)
        return await call_next(request)
