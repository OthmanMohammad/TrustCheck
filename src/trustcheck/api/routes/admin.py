"""
TrustCheck Admin Routes.

API endpoints for administration and monitoring.
"""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from trustcheck.api.schemas import (
    DashboardResponse,
    DashboardStatsSchema,
    ScheduledJobSchema,
    ScraperStatusSchema,
    ScraperTriggerRequest,
    ScraperTriggerResponse,
    SystemStatusResponse,
)
from trustcheck.config import settings
from trustcheck.database import DashboardRepository, ScraperRunRepository, get_session_context
from trustcheck.domain import DataSource
from trustcheck.scheduler import get_job_status, get_scheduler
from trustcheck.services import get_ingestion_service

router = APIRouter(prefix="/api/admin", tags=["Admin"])


async def run_scraper(source: DataSource) -> None:
    """Background task to run a scraper."""
    service = get_ingestion_service()
    await service.ingest_source(source)


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """
    Get system status including scheduler and scraper information.
    """
    from trustcheck.database import check_db_connection

    # Check database
    db_connected = await check_db_connection()

    # Check scheduler
    scheduler = get_scheduler()
    scheduler_running = scheduler.running if scheduler else False

    # Get job status
    jobs = get_job_status()
    job_schemas = [
        ScheduledJobSchema(
            id=j["id"],
            name=j["name"],
            trigger=j["trigger"],
            next_run=j["next_run"],
        )
        for j in jobs
    ]

    # Get scraper statuses
    scraper_statuses = []
    async with get_session_context() as session:
        repo = ScraperRunRepository(session)
        latest_runs = await repo.get_all_latest()

        for source, run in latest_runs.items():
            scraper_statuses.append(
                ScraperStatusSchema(
                    source=source,
                    status=run.status.value,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    entities_processed=run.entities_processed,
                    entities_added=run.entities_added,
                    entities_modified=run.entities_modified,
                    entities_removed=run.entities_removed,
                    error_message=run.error_message,
                )
            )

    return SystemStatusResponse(
        success=True,
        version=settings.app_version,
        environment=settings.environment,
        database_connected=db_connected,
        scheduler_running=scheduler_running,
        jobs=job_schemas,
        scraper_statuses=scraper_statuses,
    )


@router.post("/scrape", response_model=ScraperTriggerResponse)
async def trigger_scraper(
    request: ScraperTriggerRequest,
    background_tasks: BackgroundTasks,
) -> ScraperTriggerResponse:
    """
    Trigger a manual scrape for a specific source.
    """
    # Validate source
    try:
        source = DataSource(request.source.upper())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {request.source}. Valid sources: OFAC_SDN, UN, EU, UK",
        )

    # Generate job ID
    job_id = str(uuid4())

    # Add to background tasks
    background_tasks.add_task(run_scraper, source)

    return ScraperTriggerResponse(
        success=True,
        message=f"Scrape triggered for {source.value}",
        job_id=job_id,
        source=source.value,
        status="STARTED",
    )


@router.post("/scrape/all", response_model=ScraperTriggerResponse)
async def trigger_all_scrapers(background_tasks: BackgroundTasks) -> ScraperTriggerResponse:
    """
    Trigger a manual scrape for all sources.
    """
    job_id = str(uuid4())

    # Add tasks for all sources
    for source in [DataSource.OFAC_SDN, DataSource.UN, DataSource.EU, DataSource.UK]:
        background_tasks.add_task(run_scraper, source)

    return ScraperTriggerResponse(
        success=True,
        message="Scrape triggered for all sources",
        job_id=job_id,
        source="ALL",
        status="STARTED",
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard() -> DashboardResponse:
    """
    Get dashboard statistics.
    """
    async with get_session_context() as session:
        repo = DashboardRepository(session)
        stats = await repo.get_stats()

    return DashboardResponse(
        success=True,
        data=DashboardStatsSchema(
            total_entities=stats.total_entities,
            active_entities=stats.active_entities,
            entities_by_source=stats.entities_by_source,
            entities_by_type=stats.entities_by_type,
            changes_last_24h=stats.changes_last_24h,
            changes_last_7d=stats.changes_last_7d,
            last_scrape_times=stats.last_scrape_times,
            scraper_statuses=stats.scraper_statuses,
        ),
    )


@router.post("/cache/clear")
async def clear_cache() -> dict:
    """
    Clear the screening cache.
    """
    from trustcheck.services import get_screening_service

    service = get_screening_service()
    service.clear_cache()

    return {
        "success": True,
        "message": "Screening cache cleared",
    }
