from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.snapshot_prices import run_snapshot
from app.market_data.protocol import QuoteResult
from app.models import Quote
from app.models.enums import AccountType
from app.repositories import accounts as accounts_repo
from app.repositories import lots as lots_repo
from app.repositories import users as users_repo


class FakeClient:
    def __init__(self, price: Decimal = Decimal("175.00")) -> None:
        self.price = price
        self.calls = 0

    def fetch_quote(self, ticker: str) -> QuoteResult | None:
        self.calls += 1
        return QuoteResult(
            price=self.price,
            as_of=datetime(2026, 11, 11, 21, 0, tzinfo=timezone.utc),
            source="finnhub",
        )


def test_snapshot_twice_same_day_one_row_per_ticker(db_session: Session) -> None:
    user = users_repo.create_user(
        db_session,
        auth_subject="snap-user",
        email="snap@example.com",
        name="Snap",
        github_login=None,
    )
    db_session.flush()
    account = accounts_repo.create(
        db_session,
        user_id=user.id,
        name="Brokerage",
        account_type=AccountType.investment,
    )
    lots_repo.create(
        db_session,
        user_id=user.id,
        account_id=account.id,
        ticker="GOOGL",
        quantity=Decimal("10"),
        unit_cost=Decimal("140"),
        purchase_date=None,
        idempotency_key=None,
    )
    lots_repo.create(
        db_session,
        user_id=user.id,
        account_id=account.id,
        ticker="AAPL",
        quantity=Decimal("8"),
        unit_cost=Decimal("190"),
        purchase_date=None,
        idempotency_key=None,
    )
    db_session.commit()

    client = FakeClient()
    now = datetime(2026, 11, 11, 22, 30, tzinfo=timezone.utc)
    first = run_snapshot(db_session, client=client, now=now, pause_seconds=0)
    second = run_snapshot(db_session, client=client, now=now, pause_seconds=0)

    assert first["stored"] == 2
    assert second["stored"] == 0
    assert second["already"] == 2

    count = db_session.scalar(
        select(func.count()).select_from(Quote).where(Quote.snapshot_date.is_not(None))
    )
    assert count == 2
