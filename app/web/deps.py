from __future__ import annotations

from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from app.auth import session as auth_session
from app.db import get_db
from app.models import User
from app.services import users as users_service


def get_optional_web_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User | None:
    auth_user = auth_session.authenticate_request(request)
    if auth_user is None:
        return None
    if auth_user.sealed_session:
        auth_session.set_session_cookie(response, auth_user.sealed_session)
    return users_service.resolve_user(db, auth_user.auth_subject)
