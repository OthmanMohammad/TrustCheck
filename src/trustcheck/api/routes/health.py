"""
TrustCheck Health Routes.

Health check and status endpoints for enterprise monitoring.
"""

from datetime import datetime
from typing import Any

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

    Returns the status of all system components including:
    - Database connection and type
    - Required PostgreSQL extensions
    - Scheduler status
    """
    # Check database with details
    db_status = await check_db_connection()
    db_connected = db_status.get("connected", False)

    # Check scheduler
    scheduler = get_scheduler()
    scheduler_running = scheduler.running if scheduler else False

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        version=settings.app_version,
        environment=settings.environment,
        database="connected" if db_connected else "disconnected",
        scheduler="running" if scheduler_running else "stopped",
        timestamp=datetime.utcnow(),
    )


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """
    Detailed health check for monitoring systems.

    Returns comprehensive status including:
    - Database type and connection status
    - PostgreSQL extensions (pg_trgm, unaccent)
    - Scheduler jobs and status
    - Configuration summary
    """
    # Database status
    db_status = await check_db_connection()

    # Scheduler status
    scheduler = get_scheduler()
    scheduler_jobs = []
    if scheduler and scheduler.running:
        for job in scheduler.get_jobs():
            scheduler_jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })

    # Build response
    return {
        "status": "healthy" if db_status.get("connected") else "unhealthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.app_version,
        "environment": settings.environment,
        "components": {
            "database": {
                "status": "up" if db_status.get("connected") else "down",
                "type": db_status.get("database_type"),
                "extensions": db_status.get("extensions", []),
                "error": db_status.get("error"),
            },
            "scheduler": {
                "status": "running" if scheduler and scheduler.running else "stopped",
                "jobs": scheduler_jobs,
            },
        },
        "config": {
            "database_type": "postgresql" if settings.is_postgresql else "sqlite",
            "pool_size": settings.db_pool_size if settings.is_postgresql else "N/A",
            "batch_size": settings.scraping_batch_size,
            "match_threshold": settings.default_match_threshold,
            "trigram_threshold": settings.trigram_similarity_threshold,
        },
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    """
    Kubernetes-style readiness probe.

    Returns 200 if the service is ready to accept traffic.
    """
    db_status = await check_db_connection()

    if not db_status.get("connected"):
        return {
            "ready": False,
            "reason": "Database not connected",
            "error": db_status.get("error"),
        }

    # For PostgreSQL, check required extensions
    if settings.is_postgresql:
        extensions = db_status.get("extensions", [])
        if "pg_trgm" not in extensions:
            return {
                "ready": False,
                "reason": "Missing pg_trgm extension",
            }

    return {"ready": True}


@router.get("/live")
async def liveness_check() -> dict[str, bool]:
    """
    Kubernetes-style liveness probe.

    Returns 200 if the service is alive (can be restarted if not).
    """
    return {"alive": True}


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Enterprise sanctions screening platform",
        "docs": "/docs",
        "health": "/health",
        "health_detailed": "/health/detailed",
        "ready": "/ready",
        "live": "/live",
    }
