"""
TrustCheck Health Routes.

Health check and status endpoints.
"""

from datetime import datetime

from fastapi import APIRouter

from trustcheck.api.schemas import HealthCheckResponse
from trustcheck.config import settings
from trustcheck.database import check_db_connection
from trustcheck.scheduler import get_scheduler

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Returns the status of all system components.
    """
    # Check database
    db_ok = await check_db_connection()

    # Check scheduler
    scheduler = get_scheduler()
    scheduler_running = scheduler.running if scheduler else False

    return HealthCheckResponse(
        status="healthy" if db_ok else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        database="connected" if db_ok else "disconnected",
        scheduler="running" if scheduler_running else "stopped",
        timestamp=datetime.utcnow(),
    )


@router.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Sanctions screening and monitoring platform",
        "docs": "/docs",
        "health": "/health",
    }
