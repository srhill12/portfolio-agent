from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import create_app
from app.models import User
from app.models.enums import AccountType
from app.repositories import users as users_repo
from app.services import accounts as accounts_service
from app.services import holdings as holdings_service
from app.services.errors import NotFoundError
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


@pytest.fixture
def users_and_lot(db_session: Session) -> dict:
    user_a = _create_user(db_session, f"user-a-{uuid.uuid4()}")
    user_b = _create_user(db_session, f"user-b-{uuid.uuid4()}")
    account_a = accounts_service.create_account(
        db_session,
        user_a.id,
        name="A Brokerage",
        account_type=AccountType.investment.value,
    )
    account_b = accounts_service.create_account(
        db_session,
        user_b.id,
        name="B Brokerage",
        account_type=AccountType.investment.value,
    )
    result = holdings_service.add_lot(
        db_session,
        user_a.id,
        account_id=account_a.id,
        ticker="AAPL",
        quantity="10",
        unit_cost="100",
        purchase_date=None,
        idempotency_key=str(uuid.uuid4()),
    )
    return {
        "db": db_session,
        "user_a": user_a,
        "user_b": user_b,
        "account_a": account_a,
        "account_b": account_b,
        "lot_a": result.lot,
    }


def test_service_b_cannot_access_a_lot(users_and_lot: dict) -> None:
    db = users_and_lot["db"]
    user_b = users_and_lot["user_b"]
    lot_a = users_and_lot["lot_a"]
    account_a = users_and_lot["account_a"]
    account_b = users_and_lot["account_b"]

    assert holdings_service.get_lot(db, user_b.id, lot_a.id) is None

    with pytest.raises(NotFoundError):
        holdings_service.update_lot(
            db,
            user_b.id,
            lot_a.id,
            account_id=account_b.id,
            ticker="MSFT",
            quantity="1",
            unit_cost="1",
            purchase_date=None,
        )

    with pytest.raises(NotFoundError):
        holdings_service.delete_lot(db, user_b.id, lot_a.id)

    assert accounts_service.get_account(db, user_b.id, account_a.id) is None

    with pytest.raises(NotFoundError):
        accounts_service.rename_account(
            db, user_b.id, account_a.id, name="Hijacked"
        )

    with pytest.raises(NotFoundError):
        holdings_service.add_lot(
            db,
            user_b.id,
            account_id=account_a.id,
            ticker="MSFT",
            quantity="1",
            unit_cost="1",
            purchase_date=None,
            idempotency_key=str(uuid.uuid4()),
        )

    lot_b = holdings_service.add_lot(
        db,
        user_b.id,
        account_id=account_b.id,
        ticker="MSFT",
        quantity="2",
        unit_cost="50",
        purchase_date=None,
        idempotency_key=str(uuid.uuid4()),
    ).lot

    with pytest.raises(NotFoundError):
        holdings_service.update_lot(
            db,
            user_b.id,
            lot_b.id,
            account_id=account_a.id,
            ticker="MSFT",
            quantity="2",
            unit_cost="50",
            purchase_date=None,
        )

    still = holdings_service.get_lot(db, users_and_lot["user_a"].id, lot_a.id)
    assert still is not None
    assert still.ticker == "AAPL"


def test_route_b_cannot_mutate_a_lot(users_and_lot: dict) -> None:
    db = users_and_lot["db"]
    user_b = users_and_lot["user_b"]
    lot_a = users_and_lot["lot_a"]

    app = create_app()

    def override_user() -> User:
        return user_b

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_current_web_user] = override_user
    app.dependency_overrides[get_db] = override_db

    csrf = "test-csrf-token"
    with TestClient(app) as client:
        client.cookies.set("csrf_token", csrf)
        edit = client.get(f"/holdings/{lot_a.id}/edit")
        assert edit.status_code == 404

        update = client.post(
            f"/holdings/{lot_a.id}",
            data={
                "csrf_token": csrf,
                "account_id": str(users_and_lot["account_b"].id),
                "ticker": "HACK",
                "quantity": "1",
                "unit_cost": "1",
                "purchase_date": "",
            },
            follow_redirects=False,
        )
        assert update.status_code == 404

        delete = client.post(
            f"/holdings/{lot_a.id}/delete",
            data={"csrf_token": csrf},
            follow_redirects=False,
        )
        assert delete.status_code == 404

    remaining = holdings_service.get_lot(db, users_and_lot["user_a"].id, lot_a.id)
    assert remaining is not None
    assert remaining.ticker == "AAPL"
    app.dependency_overrides.clear()


def test_idempotency_same_user_and_cross_user(users_and_lot: dict) -> None:
    db = users_and_lot["db"]
    user_a = users_and_lot["user_a"]
    user_b = users_and_lot["user_b"]
    account_a = users_and_lot["account_a"]
    account_b = users_and_lot["account_b"]
    shared_key = f"shared-{uuid.uuid4()}"

    first = holdings_service.add_lot(
        db,
        user_a.id,
        account_id=account_a.id,
        ticker="GOOGL",
        quantity="3",
        unit_cost="140",
        purchase_date=None,
        idempotency_key=shared_key,
    )
    second = holdings_service.add_lot(
        db,
        user_a.id,
        account_id=account_a.id,
        ticker="GOOGL",
        quantity="99",
        unit_cost="1",
        purchase_date=None,
        idempotency_key=shared_key,
    )
    assert first.repeated is False
    assert second.repeated is True
    assert first.lot.id == second.lot.id
    assert second.lot.quantity == first.lot.quantity

    other = holdings_service.add_lot(
        db,
        user_b.id,
        account_id=account_b.id,
        ticker="GOOGL",
        quantity="4",
        unit_cost="150",
        purchase_date=None,
        idempotency_key=shared_key,
    )
    assert other.repeated is False
    assert other.lot.id != first.lot.id
    assert other.lot.user_id == user_b.id
