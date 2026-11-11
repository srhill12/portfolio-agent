from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session

from app.market_data.protocol import QuoteResult
from app.repositories import quotes as quotes_repo
from app.services import quotes as quotes_service
from app.services.errors import ProviderUnavailable


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.responses: dict[str, QuoteResult | None | Exception] = {}

    def fetch_quote(self, ticker: str) -> QuoteResult | None:
        self.calls.append(ticker)
        value = self.responses.get(ticker, None)
        if isinstance(value, Exception):
            raise value
        return value


@pytest.fixture
def open_now() -> datetime:
    # Wednesday 11:00 America/New_York = 16:00 UTC during EST
    return datetime(2026, 11, 11, 16, 0, tzinfo=timezone.utc)


def test_cache_hit_makes_no_provider_call(
    db_session: Session, open_now: datetime
) -> None:
    quotes_repo.create(
        db_session,
        ticker="AAPL",
        price=Decimal("210.00"),
        as_of=open_now - timedelta(minutes=1),
        fetched_at=open_now - timedelta(minutes=1),
        source="finnhub",
        snapshot_date=None,
    )
    db_session.commit()

    client = FakeClient()
    client.responses["AAPL"] = QuoteResult(
        price=Decimal("999"), as_of=open_now, source="finnhub"
    )
    results = quotes_service.get_prices(
        db_session,
        ["AAPL"],
        client=client,
        now=open_now,
        pause_seconds=0,
    )
    assert client.calls == []
    assert results["AAPL"].price == Decimal("210.00")
    assert results["AAPL"].status == "live"


def test_provider_failure_falls_back_to_stored_stale(
    db_session: Session, open_now: datetime
) -> None:
    quotes_repo.create(
        db_session,
        ticker="AAPL",
        price=Decimal("200.00"),
        as_of=open_now - timedelta(hours=2),
        fetched_at=open_now - timedelta(hours=2),
        source="finnhub",
        snapshot_date=None,
    )
    db_session.commit()

    client = FakeClient()
    client.responses["AAPL"] = ProviderUnavailable("down")
    results = quotes_service.get_prices(
        db_session,
        ["AAPL"],
        client=client,
        now=open_now,
        force_refresh=True,
        pause_seconds=0,
    )
    assert results["AAPL"].price == Decimal("200.00")
    assert results["AAPL"].status == "stale"
    assert "Delayed" in results["AAPL"].status_label


def test_no_stored_quote_and_provider_failure_unavailable(
    db_session: Session, open_now: datetime
) -> None:
    client = FakeClient()
    client.responses["MSFT"] = ProviderUnavailable("down")
    results = quotes_service.get_prices(
        db_session,
        ["MSFT"],
        client=client,
        now=open_now,
        force_refresh=True,
        pause_seconds=0,
    )
    assert results["MSFT"].price is None
    assert results["MSFT"].status == "unavailable"


def test_unknown_symbol_unavailable_never_zero(
    db_session: Session, open_now: datetime
) -> None:
    client = FakeClient()
    client.responses["ZZZZ"] = None
    results = quotes_service.get_prices(
        db_session,
        ["ZZZZ"],
        client=client,
        now=open_now,
        force_refresh=True,
        pause_seconds=0,
    )
    assert results["ZZZZ"].price is None
    assert results["ZZZZ"].price != Decimal("0")
    assert results["ZZZZ"].status == "unavailable"


def test_forced_refresh_respects_sixty_second_floor(
    db_session: Session, open_now: datetime
) -> None:
    fetched_at = open_now - timedelta(seconds=90)
    quotes_repo.create(
        db_session,
        ticker="AAPL",
        price=Decimal("210.00"),
        as_of=fetched_at,
        fetched_at=fetched_at,
        source="finnhub",
        snapshot_date=None,
    )
    db_session.commit()

    client = FakeClient()
    client.responses["AAPL"] = QuoteResult(
        price=Decimal("211.00"), as_of=open_now, source="finnhub"
    )

    at_30s = fetched_at + timedelta(seconds=30)
    early = quotes_service.get_prices(
        db_session,
        ["AAPL"],
        client=client,
        now=at_30s,
        force_refresh=True,
        pause_seconds=0,
    )
    assert client.calls == []
    assert early["AAPL"].price == Decimal("210.00")
    assert quotes_service.any_ticker_needs_forced_refresh(
        db_session, ["AAPL"], now=at_30s
    ) is False

    at_90s = fetched_at + timedelta(seconds=90)
    later = quotes_service.get_prices(
        db_session,
        ["AAPL"],
        client=client,
        now=at_90s,
        force_refresh=True,
        pause_seconds=0,
    )
    assert client.calls == ["AAPL"]
    assert later["AAPL"].price == Decimal("211.00")
    assert quotes_service.any_ticker_needs_forced_refresh(
        db_session, ["AAPL"], now=at_90s
    ) is False
