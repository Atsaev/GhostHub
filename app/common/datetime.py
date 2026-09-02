from datetime import UTC, datetime


def utc_now() -> datetime:
    """Текущее время UTC (aware)."""
    return datetime.now(UTC)
