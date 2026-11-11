from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.enums import AccountType
from app.repositories import users as users_repo
from app.services import accounts as accounts_service
from app.services import holdings as holdings_service
from app.services import sample_portfolio as sample_service


def _user(db: Session, subject: str | None = None):
    user = users_repo.create_user(
        db,
        auth_subject=subject or f"sample-{uuid.uuid4()}",
        email="sample@example.com",
        name="Sample",
        github_login=None,
    )
    db.commit()
    db.refresh(user)
    return user


def test_sample_portfolio_twice_creates_exactly_two_accounts_and_four_lots(
    db_session: Session,
) -> None:
    user = _user(db_session)
    assert sample_service.load_sample_portfolio(db_session, user.id) is True
    assert sample_service.load_sample_portfolio(db_session, user.id) is False

    accounts = accounts_service.list_accounts(db_session, user.id)
    lots = holdings_service.list_lots(db_session, user.id)
    assert len(accounts) == 2
    assert len(lots) == 4


def test_sample_portfolio_skipped_when_user_already_has_account(
    db_session: Session,
) -> None:
    user = _user(db_session)
    accounts_service.create_account(
        db_session,
        user.id,
        name="Existing",
        account_type=AccountType.investment.value,
    )
    assert sample_service.load_sample_portfolio(db_session, user.id) is False
    assert len(accounts_service.list_accounts(db_session, user.id)) == 1
    assert holdings_service.list_lots(db_session, user.id) == []
