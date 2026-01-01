from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta

from app.utils.time import utc_now


class LoginRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)
        self.attempts: dict[str, deque[datetime]] = {}

    def allow(self, key: str) -> bool:
        now = utc_now()
        bucket = self.attempts.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.max_attempts:
            return False
        bucket.append(now)
        return True
