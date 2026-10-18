from __future__ import annotations

from functools import lru_cache

from workos import WorkOSClient

from app.config import get_settings


@lru_cache
def get_workos_client() -> WorkOSClient:
    settings = get_settings()
    return WorkOSClient(
        api_key=settings.workos_api_key,
        client_id=settings.workos_client_id,
    )
