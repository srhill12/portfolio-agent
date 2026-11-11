from __future__ import annotations

from cryptography.fernet import Fernet

from app.config import Settings


def test_settings_strips_trailing_whitespace_on_workos_client_id() -> None:
    cookie = Fernet.generate_key().decode()
    settings = Settings(
        _env_file=None,
        BASE_URL="http://localhost:8000",
        ALLOWED_ORIGINS="http://localhost:8000",
        DATABASE_URL="postgresql://u:p@localhost/db?sslmode=require",
        DATABASE_URL_DIRECT="postgresql://u:p@localhost/db?sslmode=require",
        WORKOS_API_KEY="sk_test",
        WORKOS_CLIENT_ID="client_test ",
        WORKOS_COOKIE_PASSWORD=cookie,
        AUTHKIT_DOMAIN="https://example.authkit.app",
        FINNHUB_API_KEY="finnhub_test_key",
    )
    assert settings.workos_client_id == "client_test"
    assert not settings.workos_client_id.endswith(" ")
