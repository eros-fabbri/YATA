from __future__ import annotations

from datetime import UTC, datetime


def require_utc(value: datetime) -> datetime:
    """Return a UTC datetime, rejecting ambiguous naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)
