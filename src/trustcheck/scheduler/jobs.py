"""
TrustCheck Background Jobs.

APScheduler-based background job definitions for periodic data ingestion.
"""

import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from trustcheck.config import settings
from trustcheck.domain import DataSource
from trustcheck.services import get_ingestion_service, get_screening_service

logger = logging.getLogger(__name__)

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
        jobs.append(
            {
                "id": job.id,
                "name": job.name,
                "trigger": str(job.trigger),
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
        )

    return jobs
