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
from trustcheck.progress import progress_tracker, TaskStatus
from trustcheck.scheduler import (
    get_job_history,
    get_job_status,
    get_scheduler,
    get_scheduler_health,
    pause_job,
    reschedule_job,
    resume_job,
    trigger_job_now,
)
from trustcheck.services import get_ingestion_service

router = APIRouter(prefix="/api/admin", tags=["Admin"])


async def run_scraper_with_progress(source: DataSource, task_id: str) -> None:
    """Background task to run a scraper with progress tracking."""
    try:
        await progress_tracker.start_task(task_id, f"Downloading {source.value} data...")
        service = get_ingestion_service()
        result = await service.ingest_source(source, task_id=task_id)

        success = result.status.value == "SUCCESS"
        message = (
            f"Completed: {result.entities_processed} processed, "
            f"{result.entities_added} added, {result.entities_modified} modified"
            if success else f"Failed: {result.error_message}"
        )

        await progress_tracker.complete_task(
            task_id,
            success=success,
            message=message,
            details={
                "entities_processed": result.entities_processed,
                "entities_added": result.entities_added,
                "entities_modified": result.entities_modified,
                "entities_removed": result.entities_removed,
            }
        )
    except Exception as e:
        await progress_tracker.complete_task(task_id, success=False, message=str(e))


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status() -> SystemStatusResponse:
    """
    Get system status including scheduler and scraper information.
    """
    from trustcheck.database import check_db_connection

    # Check database
    db_status = await check_db_connection()
    db_connected = db_status.get("connected", False)

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

    # Create tracked task
    task_id = await progress_tracker.create_task(
        task_name=f"Scraping {source.value}",
        total_steps=100,  # Will be updated during scraping
    )

    # Add to background tasks
    background_tasks.add_task(run_scraper_with_progress, source, task_id)

    return ScraperTriggerResponse(
        success=True,
        message=f"Scrape triggered for {source.value}",
        job_id=task_id,
        source=source.value,
        status="STARTED",
    )


@router.post("/scrape/all", response_model=ScraperTriggerResponse)
async def trigger_all_scrapers(background_tasks: BackgroundTasks) -> ScraperTriggerResponse:
    """
    Trigger a manual scrape for all sources.
    """
    task_ids = []

    # Create tracked tasks for all sources
    for source in [DataSource.OFAC_SDN, DataSource.UN, DataSource.EU, DataSource.UK]:
        task_id = await progress_tracker.create_task(
            task_name=f"Scraping {source.value}",
            total_steps=100,
        )
        task_ids.append(task_id)
        background_tasks.add_task(run_scraper_with_progress, source, task_id)

    return ScraperTriggerResponse(
        success=True,
        message="Scrape triggered for all sources",
        job_id=",".join(task_ids),  # Return all task IDs
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


@router.get("/jobs")
async def list_jobs() -> dict:
    """
    List all scheduled jobs with their status.
    """
    jobs = get_job_status()
    health = get_scheduler_health()

    return {
        "success": True,
        "scheduler": health,
        "jobs": jobs,
    }


@router.get("/jobs/history")
async def get_jobs_history(job_id: str | None = None, limit: int = 20) -> dict:
    """
    Get job execution history.
    """
    history = get_job_history(job_id, limit)

    return {
        "success": True,
        "job_id": job_id,
        "executions": history,
    }


@router.post("/jobs/{job_id}/pause")
async def pause_scheduled_job(job_id: str) -> dict:
    """
    Pause a scheduled job.
    """
    success = pause_job(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "success": True,
        "message": f"Job {job_id} paused",
    }


@router.post("/jobs/{job_id}/resume")
async def resume_scheduled_job(job_id: str) -> dict:
    """
    Resume a paused job.
    """
    success = resume_job(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "success": True,
        "message": f"Job {job_id} resumed",
    }


@router.post("/jobs/{job_id}/trigger")
async def trigger_scheduled_job(job_id: str) -> dict:
    """
    Trigger a job to run immediately.
    """
    success = trigger_job_now(job_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "success": True,
        "message": f"Job {job_id} triggered",
    }


@router.post("/jobs/{job_id}/reschedule")
async def reschedule_scheduled_job(
    job_id: str,
    hours: int | None = None,
    cron: str | None = None,
) -> dict:
    """
    Reschedule a job with a new interval.

    - hours: New interval in hours (for interval-based jobs)
    - cron: New cron expression "minute hour" (for cron-based jobs)
    """
    if hours is None and cron is None:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'hours' or 'cron' parameter",
        )

    success = reschedule_job(job_id, hours=hours, cron=cron)

    if not success:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return {
        "success": True,
        "message": f"Job {job_id} rescheduled",
    }
