import time
from collections import defaultdict, deque

from app.core.config import settings


class RateLimiter:
    """Скользящее окно лимитов в памяти (для одного процесса)."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        """Регистрирует событие и возвращает True, если лимит не превышен."""
        now = time.monotonic()
        events = self._events[key]
        while events and now - events[0] > self.window_seconds:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True


room_creation_limiter = RateLimiter(
    settings.rate_limit_create_rooms,
    settings.rate_limit_create_window_seconds,
)

join_attempt_limiter = RateLimiter(
    settings.rate_limit_join_attempts,
    settings.rate_limit_join_window_seconds,
)
