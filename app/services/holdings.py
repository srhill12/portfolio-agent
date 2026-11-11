from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Lot
from app.repositories import accounts as accounts_repo
from app.repositories import lots as lots_repo
from app.services.errors import NotFoundError, ValidationError

_TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
_MAX_DECIMAL_PLACES = 8


@dataclass(frozen=True)
class AddLotResult:
    lot: Lot
    repeated: bool


def list_lots(db: Session, user_id: uuid.UUID) -> list[Lot]:
    return lots_repo.list_for_user(db, user_id)


def get_lot(db: Session, user_id: uuid.UUID, lot_id: uuid.UUID) -> Lot | None:
    return lots_repo.get_for_user(db, user_id, lot_id)


def add_lot(
    db: Session,
    user_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    ticker: str,
    quantity: str | Decimal,
    unit_cost: str | Decimal,
    purchase_date: date | str | None,
    idempotency_key: str | None,
) -> AddLotResult:
    cleaned_ticker = _validate_ticker(ticker)
    qty = _validate_positive_decimal(quantity, field="quantity", label="Quantity")
    cost = _validate_positive_decimal(unit_cost, field="unit_cost", label="Unit cost")
    purchased = _validate_purchase_date(purchase_date)
    key = (idempotency_key or "").strip() or None

    if key:
        existing = lots_repo.get_by_idempotency_key(db, user_id, key)
        if existing is not None:
            return AddLotResult(lot=existing, repeated=True)

    account = accounts_repo.get_for_user(db, user_id, account_id)
    if account is None:
        raise NotFoundError()

    try:
        with db.begin_nested():
            lot = lots_repo.create(
                db,
                user_id=user_id,
                account_id=account.id,
                ticker=cleaned_ticker,
                quantity=qty,
                unit_cost=cost,
                purchase_date=purchased,
                idempotency_key=key,
            )
    except IntegrityError:
        if key is None:
            raise
        existing = lots_repo.get_by_idempotency_key(db, user_id, key)
        if existing is None:
            raise
        db.commit()
        return AddLotResult(lot=existing, repeated=True)

    db.commit()
    db.refresh(lot)
    return AddLotResult(lot=lot, repeated=False)


def update_lot(
    db: Session,
    user_id: uuid.UUID,
    lot_id: uuid.UUID,
    *,
    account_id: uuid.UUID,
    ticker: str,
    quantity: str | Decimal,
    unit_cost: str | Decimal,
    purchase_date: date | str | None,
) -> Lot:
    lot = lots_repo.get_for_user(db, user_id, lot_id)
    if lot is None:
        raise NotFoundError()

    account = accounts_repo.get_for_user(db, user_id, account_id)
    if account is None:
        raise NotFoundError()

    lot.account_id = account.id
    lot.ticker = _validate_ticker(ticker)
    lot.quantity = _validate_positive_decimal(
        quantity, field="quantity", label="Quantity"
    )
    lot.unit_cost = _validate_positive_decimal(
        unit_cost, field="unit_cost", label="Unit cost"
    )
    lot.purchase_date = _validate_purchase_date(purchase_date)
    db.commit()
    db.refresh(lot)
    return lot


def delete_lot(db: Session, user_id: uuid.UUID, lot_id: uuid.UUID) -> None:
    lot = lots_repo.get_for_user(db, user_id, lot_id)
    if lot is None:
        raise NotFoundError()
    lots_repo.delete(db, lot)
    db.commit()


def _validate_ticker(ticker: str) -> str:
    cleaned = (ticker or "").strip().upper()
    if not _TICKER_RE.match(cleaned):
        raise ValidationError(
            "Enter a ticker like AAPL or BRK.B (letters, numbers, period, or hyphen).",
            field="ticker",
        )
    return cleaned


def _validate_positive_decimal(
    value: str | Decimal, *, field: str, label: str
) -> Decimal:
    if isinstance(value, Decimal):
        number = value
    else:
        text = (value or "").strip().replace(",", "")
        if not text:
            raise ValidationError(f"{label} is required.", field=field)
        try:
            number = Decimal(text)
        except InvalidOperation as exc:
            raise ValidationError(
                f"{label} must be a number greater than zero.",
                field=field,
            ) from exc

    if not number.is_finite() or number <= 0:
        raise ValidationError(
            f"{label} must be a number greater than zero.",
            field=field,
        )
    if abs(number.as_tuple().exponent) > _MAX_DECIMAL_PLACES:
        raise ValidationError(
            f"{label} can have at most {_MAX_DECIMAL_PLACES} decimal places.",
            field=field,
        )
    return number


def _validate_purchase_date(value: date | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        parsed = value
    else:
        try:
            parsed = date.fromisoformat(str(value).strip())
        except ValueError as exc:
            raise ValidationError(
                "Purchase date must look like YYYY-MM-DD.",
                field="purchase_date",
            ) from exc
    today = datetime.now(timezone.utc).date()
    if parsed > today:
        raise ValidationError(
            "Purchase date cannot be in the future.",
            field="purchase_date",
        )
    return parsed
