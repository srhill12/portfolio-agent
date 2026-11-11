from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import Account
from app.models.enums import AccountType
from app.repositories import accounts as accounts_repo
from app.services.errors import NotFoundError, ValidationError


def list_accounts(db: Session, user_id: uuid.UUID) -> list[Account]:
    return accounts_repo.list_for_user(db, user_id)


def get_account(
    db: Session, user_id: uuid.UUID, account_id: uuid.UUID
) -> Account | None:
    return accounts_repo.get_for_user(db, user_id, account_id)


def create_account(
    db: Session,
    user_id: uuid.UUID,
    *,
    name: str,
    account_type: str,
) -> Account:
    cleaned = _validate_name(name)
    typed = _validate_type(account_type)
    account = accounts_repo.create(
        db, user_id=user_id, name=cleaned, account_type=typed
    )
    db.commit()
    db.refresh(account)
    return account


def rename_account(
    db: Session,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    name: str,
) -> Account:
    account = accounts_repo.get_for_user(db, user_id, account_id)
    if account is None:
        raise NotFoundError()
    account.name = _validate_name(name)
    db.commit()
    db.refresh(account)
    return account


def _validate_name(name: str) -> str:
    cleaned = (name or "").strip()
    if len(cleaned) < 1 or len(cleaned) > 100:
        raise ValidationError(
            "Account name must be between 1 and 100 characters.",
            field="name",
        )
    return cleaned


def _validate_type(account_type: str) -> AccountType:
    try:
        return AccountType(account_type)
    except ValueError as exc:
        raise ValidationError(
            "Choose investment or retirement for the account type.",
            field="type",
        ) from exc
