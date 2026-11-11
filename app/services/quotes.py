from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.market_data.finnhub import FinnhubClient
from app.market_data.protocol import QuoteClient
from app.market_data.status import classify_quote_status, format_status_label
from app.repositories import quotes as quotes_repo
from app.services.errors import ProviderUnavailable

logger = logging.getLogger(__name__)

CACHE_TTL = timedelta(minutes=5)
_INTER_CALL_PAUSE_SECONDS = 0.6


@dataclass(frozen=True)
class TickerQuote:
    ticker: str
    price: Decimal | None
    as_of: datetime | None
    fetched_at: datetime | None
    status: str
    status_label: str
    source: str | None


def get_prices(
    db: Session,
    tickers: list[str],
    *,
    client: QuoteClient | None = None,
    now: datetime | None = None,
    force_refresh: bool = False,
    pause_seconds: float = _INTER_CALL_PAUSE_SECONDS,
) -> dict[str, TickerQuote]:
    """Resolve prices for tickers with cache, status labels, and fallbacks."""
    clock = now or datetime.now(timezone.utc)
    unique: list[str] = []
    seen: set[str] = set()
    for raw in tickers:
        ticker = (raw or "").strip().upper()
        if ticker and ticker not in seen:
            seen.add(ticker)
            unique.append(ticker)

    owns_client = client is None
    quote_client: QuoteClient = client or FinnhubClient(_require_api_key())
    results: dict[str, TickerQuote] = {}
    try:
        for index, ticker in enumerate(unique):
            if index > 0 and pause_seconds > 0:
                time.sleep(pause_seconds)
            results[ticker] = _resolve_one(
                db,
                ticker,
                client=quote_client,
                now=clock,
                force_refresh=force_refresh,
            )
    finally:
        close = getattr(quote_client, "close", None)
        if owns_client and callable(close):
            close()
    return results


def _require_api_key() -> str:
    from app.config import get_settings

    return get_settings().finnhub_api_key


def _resolve_one(
    db: Session,
    ticker: str,
    *,
    client: QuoteClient,
    now: datetime,
    force_refresh: bool,
) -> TickerQuote:
    if not force_refresh:
        cached = quotes_repo.get_recent_cache(
            db, ticker, newer_than=now - CACHE_TTL
        )
        if cached is not None:
            return _from_stored(ticker, cached, now=now, provider_failure=False)

    provider_failure = False
    fetched = None
    try:
        fetched = client.fetch_quote(ticker)
    except ProviderUnavailable:
        provider_failure = True
        logger.warning("Quote provider unavailable for ticker %s", ticker)
    except Exception:
        provider_failure = True
        logger.exception("Unexpected quote provider error for ticker %s", ticker)

    if fetched is not None:
        row = quotes_repo.create(
            db,
            ticker=ticker,
            price=fetched.price,
            as_of=fetched.as_of,
            fetched_at=now,
            source=fetched.source,
            snapshot_date=None,
        )
        db.commit()
        return _from_stored(ticker, row, now=now, provider_failure=False)

    stored = quotes_repo.get_latest_for_ticker(db, ticker)
    if stored is not None:
        # Miss (unknown symbol) or provider failure: never invent a zero price.
        return _from_stored(
            ticker,
            stored,
            now=now,
            provider_failure=True,
        )

    return TickerQuote(
        ticker=ticker,
        price=None,
        as_of=None,
        fetched_at=None,
        status="unavailable",
        status_label=format_status_label("unavailable", as_of=None),
        source=None,
    )


def _from_stored(
    ticker: str,
    row: object,
    *,
    now: datetime,
    provider_failure: bool,
) -> TickerQuote:
    price = getattr(row, "price")
    as_of = getattr(row, "as_of")
    fetched_at = getattr(row, "fetched_at")
    source = getattr(row, "source")
    status = classify_quote_status(
        now=now,
        as_of=as_of,
        has_price=price is not None,
        from_provider_failure=provider_failure,
    )
    return TickerQuote(
        ticker=ticker,
        price=price,
        as_of=as_of,
        fetched_at=fetched_at,
        status=status,
        status_label=format_status_label(status, as_of=as_of),
        source=source,
    )
