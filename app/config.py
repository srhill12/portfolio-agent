from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def _ensure_sslmode_require(url: str) -> str:
    """Ensure sslmode=require is present on a Postgres URL."""
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


def to_sqlalchemy_url(url: str) -> str:
    """Normalize a Neon/Postgres URL for SQLAlchemy + psycopg 3."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql+psycopg://"):
        return _ensure_sslmode_require(url)
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return _ensure_sslmode_require(url)
    raise ValueError(
        "DATABASE_URL must start with postgresql://, postgres://, "
        "or postgresql+psycopg://"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = Field(alias="BASE_URL")
    allowed_origins: Annotated[list[str], NoDecode] = Field(alias="ALLOWED_ORIGINS")

    database_url: str = Field(alias="DATABASE_URL")
    database_url_direct: str = Field(alias="DATABASE_URL_DIRECT")

    workos_api_key: str = Field(alias="WORKOS_API_KEY")
    workos_client_id: str = Field(alias="WORKOS_CLIENT_ID")
    workos_cookie_password: str = Field(alias="WORKOS_COOKIE_PASSWORD")
    authkit_domain: str = Field(alias="AUTHKIT_DOMAIN")

    session_cookie_name: str = "wos_session"
    oauth_state_cookie_name: str = "oauth_state"
    csrf_cookie_name: str = "csrf_token"

    @field_validator("base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("authkit_domain")
    @classmethod
    def normalize_authkit_domain(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value.startswith(("http://", "https://")):
            value = f"https://{value}"
        return value

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item).rstrip("/") for item in value]
        if isinstance(value, str):
            parts = [part.strip().rstrip("/") for part in value.split(",")]
            return [part for part in parts if part]
        raise TypeError("ALLOWED_ORIGINS must be a comma-separated string or list")

    @field_validator("workos_cookie_password")
    @classmethod
    def cookie_password_is_fernet_key(cls, value: str) -> str:
        _hint = (
            'python3 -c "import base64,os; '
            'print(base64.urlsafe_b64encode(os.urandom(32)).decode())"'
        )
        if len(value) < 32:
            raise ValueError(
                "WORKOS_COOKIE_PASSWORD must be at least 32 characters "
                f"(generate with: {_hint})"
            )
        try:
            Fernet(value.encode("utf-8"))
        except Exception as exc:
            raise ValueError(
                "WORKOS_COOKIE_PASSWORD must be a valid Fernet key "
                f"(generate with: {_hint})"
            ) from exc
        return value

    @model_validator(mode="after")
    def validate_urls(self) -> Settings:
        # Fail fast if DB URLs cannot be normalized for psycopg.
        to_sqlalchemy_url(self.database_url)
        to_sqlalchemy_url(self.database_url_direct)
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        return to_sqlalchemy_url(self.database_url)

    @property
    def sqlalchemy_database_url_direct(self) -> str:
        return to_sqlalchemy_url(self.database_url_direct)

    @property
    def redirect_uri(self) -> str:
        return f"{self.base_url}/callback"

    @property
    def mcp_resource_url(self) -> str:
        return f"{self.base_url}/mcp"

    @property
    def cookie_secure(self) -> bool:
        return self.base_url.startswith("https://")

    @property
    def allowed_hosts(self) -> list[str]:
        host = urlparse(self.base_url).hostname
        return [host] if host else []


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
