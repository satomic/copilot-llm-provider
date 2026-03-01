"""
FastAPI application entry point.

Creates the FastAPI app with lifespan context manager, CORS middleware,
router mounting, and optional static file serving for the frontend.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.dependencies import get_settings
from backend.app.core.logging import setup_logging
from backend.app.providers.copilot import CopilotProvider
from backend.app.services.token_pool import get_token_pool

# Import routers
from backend.app.api.openai.chat import router as openai_chat_router
from backend.app.api.openai.models import router as openai_models_router
from backend.app.api.anthropic.messages import router as anthropic_messages_router
from backend.app.api.admin import router as admin_router
from backend.app.api.auth import router as auth_router
from backend.app.api.sessions import router as sessions_router
from backend.app.api.stats import router as stats_router

logger = logging.getLogger(__name__)

APP_VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup and shutdown events:
    - Startup: Initialize logging, create and start the LLM provider.
    - Shutdown: Gracefully stop the provider and clean up resources.
    """
    settings = get_settings()

    # Set up structured logging before anything else
    setup_logging(settings.log_level)

    logger.info("Starting Copilot LLM Provider v%s", APP_VERSION)

    # Initialize the token pool (multi-token support)
    token_pool = get_token_pool()

    # If a GITHUB_TOKEN is set in env and no tokens exist in the pool yet,
    # auto-add it as the "default" token for backward compatibility.
    if settings.github_token and token_pool.token_count() == 0:
        logger.info("Auto-adding GITHUB_TOKEN from environment as default token")
        await token_pool.add_token(alias="default", token=settings.github_token)
    elif token_pool.token_count() > 0:
        await token_pool.start_all()

    # Also create a single "primary" provider for backward compat.
    # This uses the first active token from the pool, or env token as fallback.
    active_tokens = token_pool.get_active_tokens()
    if active_tokens:
        provider = active_tokens[0].provider
        logger.info("Primary provider set from token pool (%s)", active_tokens[0].alias)
    else:
        # Fallback: try starting a provider with the env token directly
        provider = CopilotProvider(github_token=settings.github_token)
        try:
            await provider.start()
            logger.info("Fallback provider started with env GITHUB_TOKEN")
        except Exception:
            logger.exception("Failed to start fallback provider")
            raise

    app.state.provider = provider
    app.state.token_pool = token_pool

    yield

    # Graceful shutdown
    logger.info("Shutting down token pool...")
    try:
        await token_pool.stop_all()
        logger.info("Token pool stopped")
    except Exception:
        logger.exception("Error during token pool shutdown")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    settings = get_settings()

    app = FastAPI(
        title="Copilot LLM Provider",
        description="OpenAI/Anthropic-compatible LLM API server powered by GitHub Copilot",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    # -- CORS middleware --
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Validation error handler (422 → Anthropic/OpenAI error format) --
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        """Convert FastAPI 422 validation errors to API-compatible error format."""
        msg = "; ".join(f"{'.'.join(str(l) for l in e['loc'])}: {e['msg']}" for e in exc.errors())
        logger.warning("Validation error on %s %s: %s", request.method, request.url.path, msg)
        # Anthropic-style error for /v1/messages, OpenAI-style for others
        if "/v1/messages" in request.url.path:
            return JSONResponse(
                status_code=400,
                content={"type": "error", "error": {"type": "invalid_request_error", "message": msg}},
            )
        return JSONResponse(
            status_code=400,
            content={"error": {"message": msg, "type": "invalid_request_error", "code": "400"}},
        )

    # -- Global exception handler --
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch unhandled exceptions and return OpenAI-style error format."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "Internal server error.",
                    "type": "server_error",
                    "code": 500,
                }
            },
        )

    # -- Health endpoint --
    @app.get("/health", summary="Health check")
    async def health() -> dict:
        """Return service health status."""
        return {"status": "ok", "version": APP_VERSION}

    # -- Router mounting --
    # OpenAI-compatible routes: /openai/v1/... (primary) and /v1/... (compat)
    app.include_router(openai_chat_router, prefix="/openai", tags=["OpenAI"])
    app.include_router(openai_models_router, prefix="/openai", tags=["OpenAI"])
    app.include_router(openai_chat_router, tags=["OpenAI (compat)"])
    app.include_router(openai_models_router, tags=["OpenAI (compat)"])

    # Anthropic-compatible routes: /anthropic/v1/... (primary) and /v1/... (compat)
    app.include_router(anthropic_messages_router, prefix="/anthropic", tags=["Anthropic"])
    app.include_router(anthropic_messages_router, tags=["Anthropic (compat)"])

    # Auth, admin, sessions, and stats routes
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(sessions_router)
    app.include_router(stats_router)

    # -- Static file serving (production) --
    if settings.frontend_dir:
        frontend_path = Path(settings.frontend_dir)
        if frontend_path.is_dir():
            logger.info("Serving frontend static files from %s", frontend_path)
            # Serve static assets (JS, CSS, images)
            app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="assets")

            # SPA catch-all: serve index.html for any non-API route
            index_html = frontend_path / "index.html"

            @app.get("/{full_path:path}", include_in_schema=False)
            async def spa_fallback(full_path: str) -> FileResponse:
                """Serve index.html for SPA client-side routing."""
                # Try to serve the exact file first
                file_path = frontend_path / full_path
                if full_path and file_path.is_file():
                    return FileResponse(str(file_path))
                return FileResponse(str(index_html))
        else:
            logger.warning("FRONTEND_DIR=%s does not exist, skipping static file serving", settings.frontend_dir)

    return app


app = create_app()
