from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastmcp.utilities.lifespan import combine_lifespans

from app.config import get_settings
from app.mcp.server import build_mcp_asgi_app
from app.web.routes import router as web_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    mcp_app = build_mcp_asgi_app(settings)

    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        logger.info("WorkOS redirect URI: %s", settings.redirect_uri)
        logger.info("MCP resource URL: %s", settings.mcp_resource_url)
        print(f"WorkOS redirect URI: {settings.redirect_uri}")
        print(f"MCP resource URL: {settings.mcp_resource_url}")
        yield

    app = FastAPI(
        title="Portfolio Tracker",
        lifespan=combine_lifespans(app_lifespan, mcp_app.lifespan),
    )
    app.include_router(web_router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    # MCP app serves /mcp and /.well-known/*; mount at / so those paths stay
    # at the site root. Do not add app-wide CORS middleware.
    app.mount("/", mcp_app)
    return app


app = create_app()
