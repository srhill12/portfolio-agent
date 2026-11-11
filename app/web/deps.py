from __future__ import annotations

import secrets

from fastapi import Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.auth import session as auth_session
from app.config import get_settings
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


def get_current_web_user(
    user: User | None = Depends(get_optional_web_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=HTTP_303_SEE_OTHER,
            headers={"Location": "/"},
        )
    return user


def require_csrf(
    request: Request,
    csrf_token: str = Form(...),
) -> str:
    """Reject forged POSTs the same way /logout does (redirect on failure)."""
    settings = get_settings()
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token or csrf_token != cookie_token:
        raise HTTPException(
            status_code=HTTP_303_SEE_OTHER,
            headers={"Location": "/dashboard?error=csrf"},
        )
    return csrf_token


def ensure_csrf_cookie(request: Request, response: Response) -> str:
    settings = get_settings()
    token = request.cookies.get(settings.csrf_cookie_name)
    if token:
        return token
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=60 * 60 * 24 * 14,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return token
