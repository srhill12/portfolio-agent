from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Quote


def get_latest_for_ticker(db: Session, ticker: str) -> Quote | None:
    return db.scalar(
        select(Quote)
        .where(Quote.ticker == ticker)
        .order_by(Quote.fetched_at.desc())
        .limit(1)
    )


def get_recent_cache(
    db: Session, ticker: str, *, newer_than: datetime
) -> Quote | None:
    return db.scalar(
        select(Quote)
        .where(
            Quote.ticker == ticker,
            Quote.snapshot_date.is_(None),
            Quote.fetched_at >= newer_than,
        )
        .order_by(Quote.fetched_at.desc())
        .limit(1)
    )


def create(
    db: Session,
    *,
    ticker: str,
    price: Decimal,
    as_of: datetime,
    fetched_at: datetime,
    source: str | None,
    snapshot_date: date | None = None,
) -> Quote:
    row = Quote(
        id=uuid4(),
        ticker=ticker,
        price=price,
        as_of=as_of,
        fetched_at=fetched_at,
        source=source,
        snapshot_date=snapshot_date,
    )
    db.add(row)
    db.flush()
    return row


def get_snapshot(db: Session, ticker: str, snapshot_date: date) -> Quote | None:
    return db.scalar(
        select(Quote).where(
            Quote.ticker == ticker,
            Quote.snapshot_date == snapshot_date,
        )
    )
