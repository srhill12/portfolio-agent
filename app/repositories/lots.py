from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Lot


def list_for_user(db: Session, user_id: uuid.UUID) -> list[Lot]:
    return list(
        db.scalars(
            select(Lot)
            .options(joinedload(Lot.account))
            .where(Lot.user_id == user_id)
            .order_by(Lot.ticker, Lot.created_at)
        ).unique().all()
    )


def get_for_user(db: Session, user_id: uuid.UUID, lot_id: uuid.UUID) -> Lot | None:
    return db.scalar(
        select(Lot)
        .options(joinedload(Lot.account))
        .where(Lot.id == lot_id, Lot.user_id == user_id)
    )


def get_by_idempotency_key(
    db: Session, user_id: uuid.UUID, idempotency_key: str
) -> Lot | None:
    return db.scalar(
        select(Lot).where(
            Lot.user_id == user_id,
            Lot.idempotency_key == idempotency_key,
        )
    )


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    ticker: str,
    quantity: Decimal,
    unit_cost: Decimal,
    purchase_date: date | None,
    idempotency_key: str | None,
) -> Lot:
    lot = Lot(
        user_id=user_id,
        account_id=account_id,
        ticker=ticker,
        quantity=quantity,
        unit_cost=unit_cost,
        purchase_date=purchase_date,
        idempotency_key=idempotency_key,
    )
    db.add(lot)
    db.flush()
    return lot


def delete(db: Session, lot: Lot) -> None:
    db.delete(lot)
    db.flush()
