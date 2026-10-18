from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def get_by_auth_subject(db: Session, auth_subject: str) -> User | None:
    return db.scalar(select(User).where(User.auth_subject == auth_subject))


def create_user(
    db: Session,
    *,
    auth_subject: str,
    email: str | None,
    name: str | None,
    github_login: str | None,
) -> User:
    user = User(
        auth_subject=auth_subject,
        email=email,
        name=name,
        github_login=github_login,
    )
    db.add(user)
    db.flush()
    return user
