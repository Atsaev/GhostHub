from datetime import UTC, datetime


def utc_now() -> datetime:
    """Текущее время UTC без tzinfo.

    SQLite (aiosqlite) хранит и возвращает naive datetime,
    поэтому для сравнений используем naive UTC.
    """
    return datetime.now(UTC).replace(tzinfo=None)
