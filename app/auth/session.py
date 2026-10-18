from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Any

from fastapi import Request, Response
from workos.session import seal_session_from_auth_response

from app.auth.workos_client import get_workos_client
from app.config import Settings, get_settings


@dataclass
class AuthenticatedWebUser:
    auth_subject: str
    email: str | None
    name: str | None
    sealed_session: str | None = None


def _cookie_kwargs(settings: Settings) -> dict[str, Any]:
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/",
    }


def set_oauth_state_cookie(response: Response, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    state = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.oauth_state_cookie_name,
        value=state,
        max_age=600,
        **_cookie_kwargs(settings),
    )
    return state


def clear_oauth_state_cookie(response: Response, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    response.delete_cookie(
        key=settings.oauth_state_cookie_name,
        path="/",
        samesite="lax",
        secure=settings.cookie_secure,
        httponly=True,
    )


def set_session_cookie(
    response: Response, sealed_session: str, settings: Settings | None = None
) -> None:
    settings = settings or get_settings()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sealed_session,
        max_age=60 * 60 * 24 * 14,
        **_cookie_kwargs(settings),
    )


def clear_session_cookie(response: Response, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        samesite="lax",
        secure=settings.cookie_secure,
        httponly=True,
    )


def set_csrf_cookie(response: Response, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=60 * 60 * 24 * 14,
        **_cookie_kwargs(settings),
    )
    return token


def clear_csrf_cookie(response: Response, settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        samesite="lax",
        secure=settings.cookie_secure,
        httponly=True,
    )


def build_authorization_url(state: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    client = get_workos_client()
    return client.user_management.get_authorization_url(
        provider="authkit",
        redirect_uri=settings.redirect_uri,
        state=state,
    )


def exchange_code_for_sealed_session(
    code: str, settings: Settings | None = None
) -> tuple[str, dict[str, Any]]:
    """Exchange the AuthKit code and return (sealed_session, user_dict)."""
    settings = settings or get_settings()
    client = get_workos_client()
    auth_response = client.user_management.authenticate_with_code(code=code)

    user_obj = auth_response.user
    if hasattr(user_obj, "to_dict"):
        user_dict = user_obj.to_dict()
    elif isinstance(user_obj, dict):
        user_dict = user_obj
    else:
        user_dict = {
            "id": getattr(user_obj, "id", None),
            "email": getattr(user_obj, "email", None),
            "first_name": getattr(user_obj, "first_name", None),
            "last_name": getattr(user_obj, "last_name", None),
            "name": getattr(user_obj, "name", None),
        }

    impersonator = getattr(auth_response, "impersonator", None)
    impersonator_dict = None
    if impersonator is not None:
        impersonator_dict = (
            impersonator.to_dict()
            if hasattr(impersonator, "to_dict")
            else dict(impersonator)
        )

    sealed = seal_session_from_auth_response(
        access_token=auth_response.access_token,
        refresh_token=auth_response.refresh_token,
        user=user_dict,
        impersonator=impersonator_dict,
        cookie_password=settings.workos_cookie_password,
    )
    return sealed, user_dict


def authenticate_request(
    request: Request, settings: Settings | None = None
) -> AuthenticatedWebUser | None:
    """Validate the sealed session cookie; refresh when needed."""
    settings = settings or get_settings()
    sealed = request.cookies.get(settings.session_cookie_name)
    if not sealed:
        return None

    client = get_workos_client()
    session = client.user_management.load_sealed_session(
        session_data=sealed,
        cookie_password=settings.workos_cookie_password,
    )
    result = session.authenticate()
    if getattr(result, "authenticated", False):
        user = getattr(result, "user", None) or {}
        auth_subject = _user_id(user)
        if auth_subject:
            return AuthenticatedWebUser(
                auth_subject=auth_subject,
                email=_user_email(user),
                name=_display_name(user),
            )

    try:
        refreshed = session.refresh()
    except Exception:
        return None

    if not getattr(refreshed, "authenticated", False):
        return None

    user = getattr(refreshed, "user", None) or {}
    auth_subject = _user_id(user)
    if not auth_subject:
        return None
    return AuthenticatedWebUser(
        auth_subject=auth_subject,
        email=_user_email(user),
        name=_display_name(user),
        sealed_session=getattr(refreshed, "sealed_session", None),
    )


def get_logout_url(
    request: Request,
    settings: Settings | None = None,
    return_to: str | None = None,
) -> str | None:
    settings = settings or get_settings()
    sealed = request.cookies.get(settings.session_cookie_name)
    if not sealed:
        return None
    client = get_workos_client()
    session = client.user_management.load_sealed_session(
        session_data=sealed,
        cookie_password=settings.workos_cookie_password,
    )
    try:
        return session.get_logout_url(return_to=return_to or settings.base_url)
    except Exception:
        return None


def _user_id(user: Any) -> str | None:
    if isinstance(user, dict):
        value = user.get("id")
        return str(value) if value else None
    value = getattr(user, "id", None)
    return str(value) if value else None


def _user_email(user: Any) -> str | None:
    if isinstance(user, dict):
        return user.get("email")
    return getattr(user, "email", None)


def _display_name(user: Any) -> str | None:
    if isinstance(user, dict):
        name = user.get("name")
        if name:
            return name
        first = user.get("first_name") or ""
        last = user.get("last_name") or ""
        combined = f"{first} {last}".strip()
        return combined or user.get("email")
    name = getattr(user, "name", None)
    if name:
        return name
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    combined = f"{first} {last}".strip()
    return combined or getattr(user, "email", None)
