"""Sliding-window rate limiter for Telegram message ingestion."""

from __future__ import annotations

import time
from collections import defaultdict


class RateLimiter:
    """Token-bucket rate limiter keyed by identifier (chat_id, user_id, etc.).

    Uses a sliding window to track request timestamps. O(1) amortized
    via lazy cleanup of expired entries.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._windows: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        """Return True if the request is within rate limits."""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        window = self._windows[key]
        self._windows[key] = [t for t in window if t > cutoff]

        if len(self._windows[key]) >= self._max_requests:
            return False

        self._windows[key].append(now)
        return True

    def reset(self, key: str) -> None:
        """Clear rate limit state for a specific key."""
        self._windows.pop(key, None)

    def remaining(self, key: str) -> int:
        """Return number of remaining requests in the current window."""
        now = time.monotonic()
        cutoff = now - self._window_seconds
        window = [t for t in self._windows.get(key, []) if t > cutoff]
        return max(0, self._max_requests - len(window))
