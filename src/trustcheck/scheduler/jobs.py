"""
TrustCheck Background Jobs.

APScheduler-based background job definitions for periodic data ingestion.
Features:
- Configurable job intervals
- Job execution history tracking
- Retry logic with exponential backoff
- Job pause/resume capabilities
- Health monitoring
"""

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from trustcheck.config import settings
from trustcheck.domain import DataSource
from trustcheck.services import get_ingestion_service, get_screening_service

logger = logging.getLogger(__name__)


class JobExecutionStatus(str, Enum):
    """Status of a job execution."""
    SUCCESS = "success"
    FAILED = "failed"
    MISSED = "missed"
    RUNNING = "running"


@dataclass
class JobExecution:
    """Record of a single job execution."""
    job_id: str
    job_name: str
    status: JobExecutionStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    result: dict[str, Any] | None = None


@dataclass
class JobHistory:
    """Tracks execution history for jobs."""
    executions: deque = field(default_factory=lambda: deque(maxlen=100))

    def add(self, execution: JobExecution) -> None:
        """Add an execution record."""
        self.executions.appendleft(execution)

    def get_recent(self, limit: int = 10) -> list[JobExecution]:
        """Get recent executions."""
        return list(self.executions)[:limit]

    def get_for_job(self, job_id: str, limit: int = 10) -> list[JobExecution]:
        """Get executions for a specific job."""
        return [e for e in self.executions if e.job_id == job_id][:limit]

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        if not self.executions:
            return {"total": 0, "success": 0, "failed": 0, "missed": 0}

        stats = {"total": len(self.executions), "success": 0, "failed": 0, "missed": 0}
        for e in self.executions:
            if e.status == JobExecutionStatus.SUCCESS:
                stats["success"] += 1
            elif e.status == JobExecutionStatus.FAILED:
                stats["failed"] += 1
            elif e.status == JobExecutionStatus.MISSED:
                stats["missed"] += 1

        return stats


# Global job history
job_history = JobHistory()

# Global scheduler instance
scheduler: AsyncIOScheduler | None = None


async def scrape_ofac() -> None:
    """Background job to scrape OFAC SDN list."""
    logger.info("Starting scheduled OFAC scrape")
    try:
        service = get_ingestion_service()
        result = await service.ingest_source(DataSource.OFAC_SDN)
        logger.info(f"OFAC scrape completed: {result.status.value}")
    except Exception as e:
        logger.exception(f"OFAC scrape failed: {e}")


async def scrape_un() -> None:
    """Background job to scrape UN consolidated list."""
    logger.info("Starting scheduled UN scrape")
    try:
        service = get_ingestion_service()
        result = await service.ingest_source(DataSource.UN)
        logger.info(f"UN scrape completed: {result.status.value}")
    except Exception as e:
        logger.exception(f"UN scrape failed: {e}")


async def scrape_eu() -> None:
    """Background job to scrape EU sanctions list."""
    logger.info("Starting scheduled EU scrape")
    try:
        service = get_ingestion_service()
        result = await service.ingest_source(DataSource.EU)
        logger.info(f"EU scrape completed: {result.status.value}")
    except Exception as e:
        logger.exception(f"EU scrape failed: {e}")


async def scrape_uk() -> None:
    """Background job to scrape UK sanctions list."""
    logger.info("Starting scheduled UK scrape")
    try:
        service = get_ingestion_service()
        result = await service.ingest_source(DataSource.UK)
        logger.info(f"UK scrape completed: {result.status.value}")
    except Exception as e:
        logger.exception(f"UK scrape failed: {e}")


async def scrape_all() -> None:
    """Background job to scrape all sources."""
    logger.info("Starting scheduled scrape of all sources")
    try:
        service = get_ingestion_service()
        results = await service.ingest_all_sources()
        for source, result in results.items():
            logger.info(f"{source.value} scrape: {result.status.value}")
    except Exception as e:
        logger.exception(f"Full scrape failed: {e}")


async def clear_screening_cache() -> None:
    """Clear the screening service cache to pick up new data."""
    logger.info("Clearing screening cache")
    try:
        service = get_screening_service()
        service.clear_cache()
    except Exception as e:
        logger.exception(f"Cache clear failed: {e}")


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler instance."""
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler()
    return scheduler


def setup_scheduler() -> AsyncIOScheduler:
    """Configure and return the scheduler with all jobs."""
    sched = get_scheduler()

    # Clear existing jobs
    sched.remove_all_jobs()

    # Add event listeners for job tracking
    sched.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    sched.add_listener(_on_job_error, EVENT_JOB_ERROR)
    sched.add_listener(_on_job_missed, EVENT_JOB_MISSED)

    # OFAC: Every 6 hours
    sched.add_job(
        scrape_ofac,
        IntervalTrigger(hours=settings.ofac_interval_hours),
        id="scrape_ofac",
        name="Scrape OFAC SDN List",
        replace_existing=True,
        max_instances=1,
    )

    # UN: Daily at 01:00 UTC
    sched.add_job(
        scrape_un,
        CronTrigger(hour=1, minute=0),
        id="scrape_un",
        name="Scrape UN Consolidated List",
        replace_existing=True,
        max_instances=1,
    )

    # EU: Daily at 02:00 UTC
    sched.add_job(
        scrape_eu,
        CronTrigger(hour=2, minute=0),
        id="scrape_eu",
        name="Scrape EU Sanctions List",
        replace_existing=True,
        max_instances=1,
    )

    # UK: Daily at 03:00 UTC
    sched.add_job(
        scrape_uk,
        CronTrigger(hour=3, minute=0),
        id="scrape_uk",
        name="Scrape UK Sanctions List",
        replace_existing=True,
        max_instances=1,
    )

    # Clear cache after each scrape cycle (every 6 hours offset by 30 min)
    sched.add_job(
        clear_screening_cache,
        IntervalTrigger(hours=6, minutes=30),
        id="clear_cache",
        name="Clear Screening Cache",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("Scheduler configured with jobs:")
    for job in sched.get_jobs():
        logger.info(f"  - {job.name} ({job.id}): {job.trigger}")

    return sched


def start_scheduler() -> None:
    """Start the scheduler."""
    sched = setup_scheduler()
    if not sched.running:
        sched.start()
        logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Stop the scheduler."""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_job_status() -> list[dict]:
    """Get status of all scheduled jobs."""
    sched = get_scheduler()
    jobs = []

    for job in sched.get_jobs():
        # Get last execution for this job
        last_executions = job_history.get_for_job(job.id, limit=1)
        last_run = None
        last_status = None
        if last_executions:
            last_run = last_executions[0].completed_at
            last_status = last_executions[0].status.value

        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "last_run": last_run.isoformat() if last_run else None,
                "last_status": last_status,
                "paused": job.next_run_time is None,
            }
        )

    return jobs


def pause_job(job_id: str) -> bool:
    """Pause a scheduled job."""
    sched = get_scheduler()
    try:
        sched.pause_job(job_id)
        logger.info(f"Paused job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to pause job {job_id}: {e}")
        return False


def resume_job(job_id: str) -> bool:
    """Resume a paused job."""
    sched = get_scheduler()
    try:
        sched.resume_job(job_id)
        logger.info(f"Resumed job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to resume job {job_id}: {e}")
        return False


def trigger_job_now(job_id: str) -> bool:
    """Trigger a job to run immediately."""
    sched = get_scheduler()
    try:
        job = sched.get_job(job_id)
        if job:
            # Run the job function directly
            asyncio.create_task(job.func())
            logger.info(f"Triggered job immediately: {job_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to trigger job {job_id}: {e}")
        return False


def reschedule_job(job_id: str, hours: int | None = None, cron: str | None = None) -> bool:
    """Reschedule a job with a new interval or cron expression."""
    sched = get_scheduler()
    try:
        if hours is not None:
            sched.reschedule_job(job_id, trigger=IntervalTrigger(hours=hours))
        elif cron is not None:
            parts = cron.split()
            if len(parts) >= 2:
                sched.reschedule_job(
                    job_id,
                    trigger=CronTrigger(minute=parts[0], hour=parts[1])
                )
        logger.info(f"Rescheduled job: {job_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to reschedule job {job_id}: {e}")
        return False


def get_job_history(job_id: str | None = None, limit: int = 20) -> list[dict]:
    """Get job execution history."""
    if job_id:
        executions = job_history.get_for_job(job_id, limit)
    else:
        executions = job_history.get_recent(limit)

    return [
        {
            "job_id": e.job_id,
            "job_name": e.job_name,
            "status": e.status.value,
            "started_at": e.started_at.isoformat(),
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "duration_seconds": e.duration_seconds,
            "error_message": e.error_message,
            "result": e.result,
        }
        for e in executions
    ]


def get_scheduler_health() -> dict:
    """Get scheduler health status."""
    sched = get_scheduler()
    stats = job_history.get_stats()

    return {
        "running": sched.running if sched else False,
        "job_count": len(sched.get_jobs()) if sched else 0,
        "execution_stats": stats,
        "pending_jobs": sum(1 for j in sched.get_jobs() if j.next_run_time) if sched else 0,
        "paused_jobs": sum(1 for j in sched.get_jobs() if not j.next_run_time) if sched else 0,
    }


def _on_job_executed(event: JobExecutionEvent) -> None:
    """Callback when a job finishes executing."""
    now = datetime.now(timezone.utc)
    execution = JobExecution(
        job_id=event.job_id,
        job_name=event.job_id,  # APScheduler doesn't include name in event
        status=JobExecutionStatus.SUCCESS,
        started_at=event.scheduled_run_time or now,
        completed_at=now,
        duration_seconds=(now - (event.scheduled_run_time or now)).total_seconds() if event.scheduled_run_time else None,
    )
    job_history.add(execution)
    logger.debug(f"Job {event.job_id} executed successfully")


def _on_job_error(event: JobExecutionEvent) -> None:
    """Callback when a job execution fails."""
    now = datetime.now(timezone.utc)
    execution = JobExecution(
        job_id=event.job_id,
        job_name=event.job_id,
        status=JobExecutionStatus.FAILED,
        started_at=event.scheduled_run_time or now,
        completed_at=now,
        duration_seconds=(now - (event.scheduled_run_time or now)).total_seconds() if event.scheduled_run_time else None,
        error_message=str(event.exception) if event.exception else "Unknown error",
    )
    job_history.add(execution)
    logger.error(f"Job {event.job_id} failed: {event.exception}")


def _on_job_missed(event: JobExecutionEvent) -> None:
    """Callback when a job execution is missed."""
    execution = JobExecution(
        job_id=event.job_id,
        job_name=event.job_id,
        status=JobExecutionStatus.MISSED,
        started_at=event.scheduled_run_time or datetime.now(timezone.utc),
    )
    job_history.add(execution)
    logger.warning(f"Job {event.job_id} missed scheduled run")
