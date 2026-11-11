"""Daily closing-price snapshot for held and favorited tickers.

Run: python -m app.jobs.snapshot_prices

Uses JobSettings (DATABASE_URL + FINNHUB_API_KEY only). Does not need WorkOS.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import JobSettings, to_sqlalchemy_url
from app.market_data.finnhub import FinnhubClient
from app.market_data.protocol import QuoteClient
from app.market_data.status import ET
from app.models import Favorite, Lot
from app.repositories import quotes as quotes_repo
from app.services.errors import ProviderUnavailable

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

_PAUSE_SECONDS = 0.6


def distinct_tickers(db: Session) -> list[str]:
    lot_tickers = set(db.scalars(select(Lot.ticker).distinct()).all())
    fav_tickers = set(db.scalars(select(Favorite.ticker).distinct()).all())
    return sorted(lot_tickers | fav_tickers)


def run_snapshot(
    db: Session,
    *,
    client: QuoteClient,
    now: datetime | None = None,
    pause_seconds: float = _PAUSE_SECONDS,
) -> dict[str, int]:
    clock = now or datetime.now(timezone.utc)
    snapshot_date = clock.astimezone(ET).date()
    tickers = distinct_tickers(db)

    attempted = 0
    stored = 0
    already = 0
    failed = 0

    for index, ticker in enumerate(tickers):
        attempted += 1
        if quotes_repo.get_snapshot(db, ticker, snapshot_date) is not None:
            already += 1
            continue

        if index > 0 and pause_seconds > 0:
            time.sleep(pause_seconds)

        try:
            result = client.fetch_quote(ticker)
        except ProviderUnavailable:
            logger.warning("snapshot failed for %s: provider unavailable", ticker)
            failed += 1
            continue
        except Exception:
            logger.exception("snapshot failed for %s", ticker)
            failed += 1
            continue

        if result is None:
            logger.warning("snapshot failed for %s: symbol not found", ticker)
            failed += 1
            continue

        try:
            with db.begin_nested():
                quotes_repo.create(
                    db,
                    ticker=ticker,
                    price=result.price,
                    as_of=result.as_of,
                    fetched_at=clock,
                    source=result.source,
                    snapshot_date=snapshot_date,
                )
            db.commit()
            stored += 1
        except IntegrityError:
            already += 1

    return {
        "attempted": attempted,
        "stored": stored,
        "already": already,
        "failed": failed,
    }


def main() -> int:
    settings = JobSettings()  # type: ignore[call-arg]
    engine = create_engine(to_sqlalchemy_url(settings.database_url), pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        with FinnhubClient(settings.finnhub_api_key) as client:
            summary = run_snapshot(db, client=client)
    finally:
        db.close()
        engine.dispose()

    logger.info(
        "snapshot tickers attempted=%s stored=%s already_present=%s failed=%s",
        summary["attempted"],
        summary["stored"],
        summary["already"],
        summary["failed"],
    )
    if summary["attempted"] > 0 and summary["failed"] == summary["attempted"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
