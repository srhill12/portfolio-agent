from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import session as auth_session
from app.config import get_settings
from app.db import get_db
from app.models import User
from app.services import users as users_service
from app.web.deps import get_optional_web_user

router = APIRouter(tags=["web"])
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "templates")
)


@router.get("/", response_class=HTMLResponse, response_model=None)
def home(
    request: Request,
    user: User | None = Depends(get_optional_web_user),
) -> HTMLResponse | RedirectResponse:
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "landing.html", {"user": None})


@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
def dashboard(
    request: Request,
    user: User | None = Depends(get_optional_web_user),
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse(url="/", status_code=303)

    settings = get_settings()
    csrf_token = request.cookies.get(settings.csrf_cookie_name)
    set_csrf = False
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        set_csrf = True

    response = templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "csrf_token": csrf_token},
    )
    if set_csrf:
        response.set_cookie(
            key=settings.csrf_cookie_name,
            value=csrf_token,
            max_age=60 * 60 * 24 * 14,
            httponly=True,
            samesite="lax",
            secure=settings.cookie_secure,
            path="/",
        )
    return response


@router.get("/login")
def login() -> RedirectResponse:
    settings = get_settings()
    state_value = secrets.token_urlsafe(32)
    authorization_url = auth_session.build_authorization_url(state_value, settings)
    response = RedirectResponse(url=authorization_url, status_code=303)
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=state_value,
        max_age=600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return response


@router.get("/callback")
def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = get_settings()
    expected = request.cookies.get(settings.oauth_state_cookie_name)
    if not code or not state or not expected or state != expected:
        response = RedirectResponse(url="/?error=oauth_state", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    try:
        sealed, user_dict = auth_session.exchange_code_for_sealed_session(code, settings)
    except Exception:
        response = RedirectResponse(url="/?error=auth_failed", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    auth_subject = str(user_dict.get("id") or "")
    if not auth_subject:
        response = RedirectResponse(url="/?error=auth_failed", status_code=303)
        auth_session.clear_oauth_state_cookie(response, settings)
        return response

    name = user_dict.get("name")
    if not name:
        first = user_dict.get("first_name") or ""
        last = user_dict.get("last_name") or ""
        name = f"{first} {last}".strip() or user_dict.get("email")

    users_service.upsert_user_from_workos(
        db,
        auth_subject=auth_subject,
        email=user_dict.get("email"),
        name=name,
        github_login=None,
    )

    response = RedirectResponse(url="/dashboard", status_code=303)
    auth_session.set_session_cookie(response, sealed, settings)
    auth_session.set_csrf_cookie(response, settings)
    auth_session.clear_oauth_state_cookie(response, settings)
    return response


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(...),
) -> RedirectResponse:
    settings = get_settings()
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    if not cookie_token or csrf_token != cookie_token:
        return RedirectResponse(url="/dashboard?error=csrf", status_code=303)

    logout_url = auth_session.get_logout_url(request, settings)
    response = RedirectResponse(url=logout_url or "/", status_code=303)
    auth_session.clear_session_cookie(response, settings)
    auth_session.clear_csrf_cookie(response, settings)
    return response
