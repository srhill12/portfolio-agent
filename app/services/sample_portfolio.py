from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.models.enums import AccountType
from app.repositories import accounts as accounts_repo
from app.repositories import lots as lots_repo
from app.services.errors import ValidationError

_SAMPLE_LOTS = (
    ("Sample Brokerage", AccountType.investment, "GOOGL", Decimal("10"), Decimal("140.00")),
    ("Sample Brokerage", AccountType.investment, "AAPL", Decimal("8"), Decimal("190.00")),
    ("Sample IRA", AccountType.retirement, "GOOGL", Decimal("5"), Decimal("170.00")),
    ("Sample IRA", AccountType.retirement, "AAPL", Decimal("12"), Decimal("165.00")),
)


def load_sample_portfolio(db: Session, user_id: uuid.UUID) -> bool:
    """Create the fictional sample accounts and lots if the user has none.

    Returns True when a sample was created, False when the user already had accounts.
    Locks the user row so a double click cannot create two sets.
    """
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ValidationError("User not found.")

    existing = accounts_repo.list_for_user(db, user_id)
    if existing:
        return False

    accounts: dict[str, object] = {}
    for name, account_type, ticker, quantity, unit_cost in _SAMPLE_LOTS:
        if name not in accounts:
            accounts[name] = accounts_repo.create(
                db,
                user_id=user_id,
                name=name,
                account_type=account_type,
            )
        account = accounts[name]
        lots_repo.create(
            db,
            user_id=user_id,
            account_id=account.id,  # type: ignore[attr-defined]
            ticker=ticker,
            quantity=quantity,
            unit_cost=unit_cost,
            purchase_date=None,
            idempotency_key=f"sample-{user_id}-{name}-{ticker}",
        )

    db.commit()
    return True
