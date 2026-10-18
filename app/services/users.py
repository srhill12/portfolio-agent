from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User
from app.repositories import users as users_repo


def resolve_user(db: Session, auth_subject: str) -> User | None:
    """Resolve the local user for a verified WorkOS subject (web session or MCP token)."""
    if not auth_subject:
        return None
    return users_repo.get_by_auth_subject(db, auth_subject)


def upsert_user_from_workos(
    db: Session,
    *,
    auth_subject: str,
    email: str | None,
    name: str | None,
    github_login: str | None = None,
) -> User:
    """Create the users row on first sign-in; refresh profile fields on later visits."""
    user = users_repo.get_by_auth_subject(db, auth_subject)
    if user is None:
        user = users_repo.create_user(
            db,
            auth_subject=auth_subject,
            email=email,
            name=name,
            github_login=github_login,
        )
    else:
        user.email = email
        user.name = name
        if github_login:
            user.github_login = github_login
    db.commit()
    db.refresh(user)
    return user
