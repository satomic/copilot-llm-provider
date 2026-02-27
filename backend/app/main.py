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
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.dependencies import get_settings
from backend.app.core.logging import setup_logging
from backend.app.providers.copilot import CopilotProvider

# Import routers
from backend.app.api.openai.chat import router as openai_chat_router
from backend.app.api.openai.models import router as openai_models_router
from backend.app.api.anthropic.messages import router as anthropic_messages_router

logger = logging.getLogger(__name__)

APP_VERSION = "0.1.0"


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

    # Initialize the LLM provider and store it on app state for DI
    provider = CopilotProvider(github_token=settings.github_token)
    try:
        await provider.start()
        logger.info("Provider started successfully")
    except Exception:
        logger.exception("Failed to start provider")
        raise

    app.state.provider = provider

    yield

    # Graceful shutdown
    logger.info("Shutting down provider...")
    try:
        await provider.stop()
        logger.info("Provider stopped")
    except Exception:
        logger.exception("Error during provider shutdown")


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
    # OpenAI-compatible routes
    app.include_router(openai_chat_router, tags=["OpenAI"])
    app.include_router(openai_models_router, tags=["OpenAI"])

    # Anthropic-compatible routes
    app.include_router(anthropic_messages_router, tags=["Anthropic"])

    # -- Static file serving (production) --
    if settings.frontend_dir:
        frontend_path = Path(settings.frontend_dir)
        if frontend_path.is_dir():
            logger.info("Serving frontend static files from %s", frontend_path)
            app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
        else:
            logger.warning("FRONTEND_DIR=%s does not exist, skipping static file serving", settings.frontend_dir)

    return app


app = create_app()
