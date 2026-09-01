from datetime import UTC, datetime


def utc_now() -> datetime:
    """Текущее время UTC (aware)."""
    return datetime.now(UTC)


def ensure_aware(value: datetime) -> datetime:
    """Приводит naive datetime (sqlite) к aware UTC для сравнений."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
