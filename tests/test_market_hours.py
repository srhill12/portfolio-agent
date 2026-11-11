from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.market_data.status import classify_quote_status, is_us_equity_market_open

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def test_weekday_open() -> None:
    # Wednesday 10:00 ET
    now = datetime(2026, 11, 11, 10, 0, tzinfo=ET)
    assert is_us_equity_market_open(now) is True
    assert (
        classify_quote_status(
            now=now,
            as_of=datetime(2026, 11, 11, 9, 55, tzinfo=ET),
            has_price=True,
        )
        == "live"
    )


def test_weekday_after_close() -> None:
    now = datetime(2026, 11, 11, 16, 30, tzinfo=ET)
    assert is_us_equity_market_open(now) is False
    assert (
        classify_quote_status(
            now=now,
            as_of=datetime(2026, 11, 11, 16, 0, tzinfo=ET),
            has_price=True,
        )
        == "closed"
    )


def test_weekend_closed() -> None:
    now = datetime(2026, 11, 14, 12, 0, tzinfo=ET)  # Saturday
    assert is_us_equity_market_open(now) is False
    assert (
        classify_quote_status(
            now=now,
            as_of=datetime(2026, 11, 13, 16, 0, tzinfo=ET),
            has_price=True,
        )
        == "closed"
    )


def test_provider_failure_on_weekend_is_stale() -> None:
    now = datetime(2026, 11, 14, 12, 0, tzinfo=ET)  # Saturday
    assert (
        classify_quote_status(
            now=now,
            as_of=datetime(2026, 11, 13, 16, 0, tzinfo=ET),
            has_price=True,
            from_provider_failure=True,
        )
        == "stale"
    )


def test_twenty_minute_stale_boundary() -> None:
    now = datetime(2026, 11, 11, 11, 0, tzinfo=ET)
    fresh = datetime(2026, 11, 11, 10, 40, tzinfo=ET)
    stale = datetime(2026, 11, 11, 10, 39, tzinfo=ET)
    assert (
        classify_quote_status(now=now, as_of=fresh, has_price=True) == "live"
    )
    assert (
        classify_quote_status(now=now, as_of=stale, has_price=True) == "stale"
    )
    assert (
        classify_quote_status(
            now=now,
            as_of=fresh,
            has_price=True,
            from_provider_failure=True,
        )
        == "stale"
    )
