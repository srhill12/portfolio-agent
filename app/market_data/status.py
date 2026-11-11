"""Pure market-hours and quote-status helpers (fixed datetimes for tests)."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
_MARKET_OPEN = time(9, 30)
_MARKET_CLOSE = time(16, 0)
_LIVE_MAX_AGE = timedelta(minutes=20)


def is_us_equity_market_open(now: datetime) -> bool:
    """Weekdays 9:30 to 16:00 America/New_York. Holidays are not modeled."""
    local = now.astimezone(ET)
    if local.weekday() >= 5:
        return False
    current = local.time()
    return _MARKET_OPEN <= current < _MARKET_CLOSE


def classify_quote_status(
    *,
    now: datetime,
    as_of: datetime | None,
    has_price: bool,
    from_provider_failure: bool = False,
) -> str:
    """Return live, closed, stale, or unavailable."""
    if not has_price or as_of is None:
        return "unavailable"

    market_open = is_us_equity_market_open(now)
    age = now - as_of.astimezone(now.tzinfo)

    if not market_open:
        return "closed"

    if from_provider_failure or age > _LIVE_MAX_AGE:
        return "stale"
    return "live"


def format_et_stamp(as_of: datetime) -> str:
    local = as_of.astimezone(ET)
    month = local.strftime("%b")
    day = str(local.day)
    hour12 = local.hour % 12 or 12
    minute = f"{local.minute:02d}"
    ampm = "AM" if local.hour < 12 else "PM"
    return f"{month} {day}, {hour12}:{minute} {ampm} ET"


def format_status_label(
    status: str,
    *,
    as_of: datetime | None,
) -> str:
    if status == "live":
        return "Live"
    if status == "unavailable" or as_of is None:
        return "Price unavailable"
    stamped = format_et_stamp(as_of)
    if status == "closed":
        return f"Market closed, as of {stamped}"
    if status == "stale":
        return f"Delayed: showing last saved price from {stamped}"
    return "Price unavailable"
