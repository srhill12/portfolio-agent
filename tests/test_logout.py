from __future__ import annotations

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from starlette.requests import Request

from app.auth import session as auth_session
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        BASE_URL="http://localhost:8000",
        ALLOWED_ORIGINS="http://localhost:8000",
        DATABASE_URL="postgresql://u:p@localhost/db?sslmode=require",
        DATABASE_URL_DIRECT="postgresql://u:p@localhost/db?sslmode=require",
        WORKOS_API_KEY="sk_test",
        WORKOS_CLIENT_ID="client_test",
        WORKOS_COOKIE_PASSWORD=Fernet.generate_key().decode(),
        AUTHKIT_DOMAIN="https://example.authkit.app",
    )


def _request_with_session(cookie_name: str, sealed: str) -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/logout",
            "raw_path": b"/logout",
            "query_string": b"",
            "headers": [(b"cookie", f"{cookie_name}={sealed}".encode())],
            "client": ("127.0.0.1", 123),
            "server": ("localhost", 8000),
        }
    )


class _FakeSession:
    def __init__(
        self,
        *,
        logout_url: str | None = None,
        logout_error: Exception | None = None,
        refresh_result: object | None = None,
        refresh_error: Exception | None = None,
    ) -> None:
        self._logout_url = logout_url
        self._logout_error = logout_error
        self._refresh_result = refresh_result
        self._refresh_error = refresh_error

    def get_logout_url(self, return_to: str | None = None) -> str:
        if self._logout_error is not None:
            raise self._logout_error
        assert self._logout_url is not None
        return self._logout_url

    def refresh(self) -> object:
        if self._refresh_error is not None:
            raise self._refresh_error
        assert self._refresh_result is not None
        return self._refresh_result


class _FakeUserManagement:
    def __init__(self, sessions: dict[str, _FakeSession]) -> None:
        self._sessions = sessions

    def load_sealed_session(
        self, *, session_data: str, cookie_password: str
    ) -> _FakeSession:
        return self._sessions[session_data]


class _FakeClient:
    def __init__(self, user_management: _FakeUserManagement) -> None:
        self.user_management = user_management


def test_get_logout_url_valid_session(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    sealed = "sealed-valid"
    logout_url = "https://api.workos.com/user_management/sessions/logout?session_id=s1"
    um = _FakeUserManagement(
        {sealed: _FakeSession(logout_url=logout_url)}
    )
    monkeypatch.setattr(auth_session, "get_workos_client", lambda: _FakeClient(um))

    request = _request_with_session(settings.session_cookie_name, sealed)
    assert auth_session.get_logout_url(request, settings) == logout_url


def test_get_logout_url_refresh_after_expired_access_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    sealed = "sealed-expired"
    refreshed_sealed = "sealed-refreshed"
    logout_url = "https://api.workos.com/user_management/sessions/logout?session_id=s2"
    um = _FakeUserManagement(
        {
            sealed: _FakeSession(
                logout_error=ValueError("access token expired"),
                refresh_result=SimpleNamespace(
                    authenticated=True,
                    sealed_session=refreshed_sealed,
                ),
            ),
            refreshed_sealed: _FakeSession(logout_url=logout_url),
        }
    )
    monkeypatch.setattr(auth_session, "get_workos_client", lambda: _FakeClient(um))

    request = _request_with_session(settings.session_cookie_name, sealed)
    assert auth_session.get_logout_url(request, settings) == logout_url


def test_get_logout_url_both_fail_returns_none_and_logs_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()
    sealed = "sealed-dead"
    um = _FakeUserManagement(
        {
            sealed: _FakeSession(
                logout_error=ValueError("access token expired"),
                refresh_error=RuntimeError("refresh failed"),
            )
        }
    )
    monkeypatch.setattr(auth_session, "get_workos_client", lambda: _FakeClient(um))
    warnings: list[str] = []
    monkeypatch.setattr(
        auth_session.logger,
        "warning",
        lambda msg, *args, **kwargs: warnings.append(msg % args if args else msg),
    )

    request = _request_with_session(settings.session_cookie_name, sealed)
    result = auth_session.get_logout_url(request, settings)

    assert result is None
    assert any("Could not build WorkOS logout URL" in message for message in warnings)
