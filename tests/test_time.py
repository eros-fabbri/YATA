from datetime import UTC, datetime, timedelta, timezone

import pytest

from smarttrading.common.time import require_utc


def test_require_utc_converts_offset() -> None:
    source = datetime(2025, 1, 1, 2, tzinfo=timezone(timedelta(hours=2)))
    assert require_utc(source) == datetime(2025, 1, 1, tzinfo=UTC)


def test_require_utc_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        require_utc(datetime(2025, 1, 1))
