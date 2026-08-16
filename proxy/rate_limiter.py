"""In-process sliding-window limiter for provider API calls."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable

from .exceptions import ProxyRateLimitError


class DualWindowRateLimiter:
    """Enforce both a short and long sliding-window request quota."""

    def __init__(
        self,
        *,
        per_second: int = 10,
        per_minute: int = 120,
        second_window: float = 1.0,
        minute_window: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if per_second <= 0 or per_minute <= 0:
            raise ValueError("rate limits must be greater than zero")
        if second_window <= 0 or minute_window <= 0:
            raise ValueError("rate-limit windows must be greater than zero")
        self.per_second = per_second
        self.per_minute = per_minute
        self.second_window = second_window
        self.minute_window = minute_window
        self._clock = clock
        self._short_events: deque[float] = deque()
        self._long_events: deque[float] = deque()
        self._lock = asyncio.Lock()

    def _prune(self, now: float) -> None:
        while self._short_events and now - self._short_events[0] >= self.second_window:
            self._short_events.popleft()
        while self._long_events and now - self._long_events[0] >= self.minute_window:
            self._long_events.popleft()

    def _wait_seconds(self, now: float) -> float:
        waits = [0.0]
        if len(self._short_events) >= self.per_second:
            waits.append(self.second_window - (now - self._short_events[0]))
        if len(self._long_events) >= self.per_minute:
            waits.append(self.minute_window - (now - self._long_events[0]))
        return max(waits)

    async def acquire(self, *, timeout: float | None = None) -> None:
        started = self._clock()
        while True:
            async with self._lock:
                now = self._clock()
                self._prune(now)
                wait_for = self._wait_seconds(now)
                if wait_for <= 0:
                    self._short_events.append(now)
                    self._long_events.append(now)
                    return
            if timeout is not None:
                elapsed = self._clock() - started
                if elapsed + wait_for > timeout:
                    raise ProxyRateLimitError("timed out waiting for provider API rate limit")
            await asyncio.sleep(max(wait_for, 0.001))
