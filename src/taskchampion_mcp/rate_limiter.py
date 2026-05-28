"""Sliding-window rate limiter for MCP operations (ADR 9)."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


class RateLimitError(Exception):
    """Raised when an operation exceeds the configured rate limit."""

    def __init__(self, bucket: str, limit: int, window_seconds: int) -> None:
        self.bucket = bucket
        self.limit = limit
        self.window_seconds = window_seconds
        super().__init__(
            f"Rate limit exceeded for '{bucket}': {limit} operations per {window_seconds}s."
        )


@dataclass
class _Bucket:
    limit: int
    window_seconds: int
    timestamps: deque[float] = field(default_factory=deque)

    def allow(self, now: float | None = None) -> bool:
        now = now or time.monotonic()
        cutoff = now - self.window_seconds
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
        return len(self.timestamps) < self.limit

    def record(self, now: float | None = None) -> None:
        now = now or time.monotonic()
        self.timestamps.append(now)

    def remaining(self, now: float | None = None) -> int:
        now = now or time.monotonic()
        cutoff = now - self.window_seconds
        while self.timestamps and self.timestamps[0] < cutoff:
            self.timestamps.popleft()
        return max(0, self.limit - len(self.timestamps))


class RateLimiter:
    """Sliding-window rate limiter with per-minute and per-hour buckets."""

    def __init__(
        self,
        ops_per_minute: int = 30,
        ops_per_hour: int = 200,
        creates_per_hour: int = 50,
    ) -> None:
        self._minute = _Bucket(limit=ops_per_minute, window_seconds=60)
        self._hour = _Bucket(limit=ops_per_hour, window_seconds=3600)
        self._creates = _Bucket(limit=creates_per_hour, window_seconds=3600)

    def check_and_record(self, *, is_create: bool = False) -> None:
        """Check all applicable buckets and record the operation.

        Raises RateLimitError if any bucket is full.
        """
        now = time.monotonic()

        if not self._minute.allow(now):
            raise RateLimitError("ops_per_minute", self._minute.limit, 60)
        if not self._hour.allow(now):
            raise RateLimitError("ops_per_hour", self._hour.limit, 3600)
        if is_create and not self._creates.allow(now):
            raise RateLimitError("creates_per_hour", self._creates.limit, 3600)

        self._minute.record(now)
        self._hour.record(now)
        if is_create:
            self._creates.record(now)

    def status(self) -> dict[str, int]:
        """Return remaining capacity for each bucket."""
        now = time.monotonic()
        return {
            "ops_per_minute_remaining": self._minute.remaining(now),
            "ops_per_hour_remaining": self._hour.remaining(now),
            "creates_per_hour_remaining": self._creates.remaining(now),
        }
