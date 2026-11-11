from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models import Account, Lot, User
from app.models.enums import AccountType
from app.repositories import accounts as accounts_repo
from app.repositories import lots as lots_repo
from app.repositories import users as users_repo
from app.services import accounts as accounts_service
from app.services import holdings as holdings_service
from app.web.deps import get_current_web_user


def _create_user(db: Session, subject: str) -> User:
    user = users_repo.create_user(
        db,
        auth_subject=subject,
        email=f"{subject}@example.com",
        name=subject,
        github_login=None,
    )
    db.commit()
    db.refresh(user)
    return user


def test_delete_account_with_holdings_cascades(db_session: Session) -> None:
    owner = _create_user(db_session, f"owner-{uuid.uuid4()}")
    other = _create_user(db_session, f"other-{uuid.uuid4()}")

    account = accounts_repo.create(
        db_session,
        user_id=owner.id,
        name="To Delete",
        account_type=AccountType.investment,
    )
    lots_repo.create(
        db_session,
        user_id=owner.id,
        account_id=account.id,
        ticker="AAPL",
        quantity=Decimal("10"),
        unit_cost=Decimal("100"),
        purchase_date=None,
        idempotency_key=None,
    )
    lots_repo.create(
        db_session,
        user_id=owner.id,
        account_id=account.id,
        ticker="GOOGL",
        quantity=Decimal("5"),
        unit_cost=Decimal("140"),
        purchase_date=None,
        idempotency_key=None,
    )

    other_account = accounts_repo.create(
        db_session,
        user_id=other.id,
        name="Keep",
        account_type=AccountType.investment,
    )
    other_lot = lots_repo.create(
        db_session,
        user_id=other.id,
        account_id=other_account.id,
        ticker="MSFT",
        quantity=Decimal("3"),
        unit_cost=Decimal("300"),
        purchase_date=None,
        idempotency_key=None,
    )
    db_session.commit()
    account_id = account.id
    other_account_id = other_account.id
    other_lot_id = other_lot.id

    accounts_service.delete_account(db_session, owner.id, account_id)

    assert accounts_service.get_account(db_session, owner.id, account_id) is None
    assert holdings_service.list_lots(db_session, owner.id) == []
    assert (
        db_session.scalar(select(func.count()).select_from(Lot).where(Lot.user_id == owner.id))
        == 0
    )
    assert (
        db_session.scalar(
            select(func.count()).select_from(Account).where(Account.user_id == owner.id)
        )
        == 0
    )

    assert accounts_service.get_account(db_session, other.id, other_account_id) is not None
    assert holdings_service.get_lot(db_session, other.id, other_lot_id) is not None


def test_owner_delete_account_route_redirects(db_session: Session) -> None:
    owner = _create_user(db_session, f"route-owner-{uuid.uuid4()}")
    account = accounts_service.create_account(
        db_session,
        owner.id,
        name="Route Delete",
        account_type=AccountType.investment.value,
    )

    app = create_app()

    def override_user() -> User:
        return owner

    def override_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_current_web_user] = override_user
    app.dependency_overrides[get_db] = override_db

    csrf = "test-csrf-token"
    with TestClient(app) as client:
        client.cookies.set("csrf_token", csrf)
        response = client.post(
            f"/accounts/{account.id}/delete",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert response.headers.get("location") == "/dashboard"

    assert accounts_service.get_account(db_session, owner.id, account.id) is None
    app.dependency_overrides.clear()
