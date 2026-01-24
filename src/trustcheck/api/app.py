"""
TrustCheck FastAPI Application Factory.

Creates and configures the FastAPI application.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from trustcheck.api.routes import (
    admin_router,
    alerts_router,
    audit_router,
    batch_router,
    changes_router,
    entities_router,
    health_router,
    screening_router,
    search_router,
    watchlists_router,
    websocket_router,
)
from trustcheck.config import settings
from trustcheck.database import close_db, init_db
from trustcheck.domain import TrustCheckError
from trustcheck.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)

# Templates directory
TEMPLATES_DIR = Path(__file__).parent.parent / "web" / "templates"
STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start scheduler
    start_scheduler()
    logger.info("Scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")

    # Stop scheduler
    stop_scheduler()

    # Close database
    await close_db()

    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app_name,
        description="Sanctions screening and monitoring platform",
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure properly for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(health_router)
    app.include_router(entities_router)
    app.include_router(screening_router)
    app.include_router(changes_router)
    app.include_router(admin_router)
    app.include_router(websocket_router)
    app.include_router(batch_router)
    app.include_router(watchlists_router)
    app.include_router(alerts_router)
    app.include_router(audit_router)
    app.include_router(search_router)

    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Register web UI routes
    register_web_routes(app)

    # Add root redirect to UI
    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        """Redirect root to web UI dashboard."""
        return RedirectResponse(url="/ui/")

    # Register exception handlers
    register_exception_handlers(app)

    return app


def register_web_routes(app: FastAPI) -> None:
    """Register web UI routes."""
    from trustcheck.web import router as web_router

    app.include_router(web_router, prefix="/ui")


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(TrustCheckError)
    async def trustcheck_error_handler(request: Request, exc: TrustCheckError) -> JSONResponse:
        """Handle TrustCheck-specific errors."""
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                },
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        logger.exception(f"Unhandled error: {exc}")

        if settings.debug:
            detail = str(exc)
        else:
            detail = "An unexpected error occurred"

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": detail,
                },
            },
        )


# Application instance
app = create_app()
