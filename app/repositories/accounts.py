from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account
from app.models.enums import AccountType


def list_for_user(db: Session, user_id: uuid.UUID) -> list[Account]:
    return list(
        db.scalars(
            select(Account)
            .where(Account.user_id == user_id)
            .order_by(Account.created_at, Account.name)
        ).all()
    )


def get_for_user(
    db: Session, user_id: uuid.UUID, account_id: uuid.UUID
) -> Account | None:
    return db.scalar(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    name: str,
    account_type: AccountType,
) -> Account:
    account = Account(user_id=user_id, name=name, type=account_type)
    db.add(account)
    db.flush()
    return account


def delete(db: Session, account: Account) -> None:
    db.delete(account)
    db.flush()
