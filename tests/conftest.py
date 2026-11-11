from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings, to_sqlalchemy_url

_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"


def _load_dotenv_file() -> dict[str, str]:
    values: dict[str, str] = {}
    if not _ENV_PATH.is_file():
        return values
    for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _hostname(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host.replace("-pooler", "")


def pytest_configure() -> None:
    # Load .env into the process for TEST_DATABASE_URL when present.
    for key, value in _load_dotenv_file().items():
        os.environ.setdefault(key, value)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = (os.environ.get("TEST_DATABASE_URL") or "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    return url


@pytest.fixture(scope="session")
def migrated_test_engine(test_database_url: str) -> Generator[Engine, None, None]:
    # Tests must never reach the production branch. Compare Neon hosts after
    # stripping the "-pooler" suffix so pooled and direct URLs for the same
    # production branch are both blocked.
    env_file = _load_dotenv_file()
    production_hosts = {
        _hostname(env_file.get("DATABASE_URL", "")),
        _hostname(env_file.get("DATABASE_URL_DIRECT", "")),
    }
    production_hosts.discard("")
    test_host = _hostname(test_database_url)
    if test_host and test_host in production_hosts:
        pytest.exit(
            "TEST_DATABASE_URL host matches DATABASE_URL or DATABASE_URL_DIRECT "
            f"from .env ({test_host}). Refusing to run migrations against production.",
            returncode=1,
        )

    os.environ["DATABASE_URL_DIRECT"] = test_database_url
    os.environ["DATABASE_URL"] = test_database_url
    get_settings.cache_clear()

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")

    engine = create_engine(to_sqlalchemy_url(test_database_url), pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def db_session(migrated_test_engine: Engine) -> Generator[Session, None, None]:
    connection = migrated_test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, autoflush=False, autocommit=False)()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # type: ignore[no-untyped-def]
        if connection.closed:
            return
        if not connection.in_nested_transaction():
            connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
