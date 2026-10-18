from __future__ import annotations

import logging

from fastmcp import FastMCP
from fastmcp.server.auth.providers.workos import AuthKitProvider
from fastmcp.server.dependencies import get_access_token

from app.config import Settings
from app.db import SessionLocal
from app.services import users as users_service

logger = logging.getLogger(__name__)


def create_mcp_server(settings: Settings) -> FastMCP:
    auth = AuthKitProvider(
        authkit_domain=settings.authkit_domain,
        base_url=settings.base_url,
    )
    mcp = FastMCP(name="Portfolio Tracker", auth=auth)

    @mcp.tool
    def whoami() -> dict[str, str]:
        """Return the authenticated user's id and name."""
        token = get_access_token()
        if token is None or not token.subject:
            raise PermissionError("Authentication required")

        claims = token.claims or {}
        name = claims.get("name") or claims.get("email")
        email = claims.get("email")

        db = SessionLocal()
        try:
            user = users_service.resolve_user(db, token.subject)
            if user is None:
                user = users_service.upsert_user_from_workos(
                    db,
                    auth_subject=token.subject,
                    email=email,
                    name=name,
                    github_login=None,
                )
            return {
                "id": str(user.id),
                "name": user.name or "",
            }
        finally:
            db.close()

    return mcp


def build_mcp_asgi_app(settings: Settings):
    """Build the MCP ASGI app with path=/mcp (mount at / in the parent app)."""
    mcp = create_mcp_server(settings)
    return mcp.http_app(
        path="/mcp",
        host_origin_protection=True,
        allowed_hosts=settings.allowed_hosts,
        allowed_origins=settings.allowed_origins,
    )
