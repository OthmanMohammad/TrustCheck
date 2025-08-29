"""
Production Celery tasks for scraping operations.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio
from celery import shared_task, Task
from celery.utils.log import get_task_logger

from src.core.enums import DataSource, ScrapingStatus
from src.core.exceptions import ScrapingError, handle_exception
from src.infrastructure.database.connection import db_manager
from src.infrastructure.database.models import ScraperRun, SanctionedEntity
from src.scrapers.registry import scraper_registry
from src.services.change_detection.service import ChangeDetectionService
from src.services.notification.service import NotificationService
from src.infrastructure.database.uow import get_uow_factory

logger = get_task_logger(__name__)

class ScraperTask(Task):
    """Base class for scraper tasks with retry logic."""
    
    autoretry_for = (ScrapingError, ConnectionError, TimeoutError)
    retry_kwargs = {
        'max_retries': 3,
        'countdown': 60,  # Wait 60 seconds between retries
        'retry_jitter': True  # Add random jitter to prevent thundering herd
    }
    
    def before_start(self, task_id, args, kwargs):
        """Log task start."""
        logger.info(f"Starting scraper task {task_id} with args {args}")
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Log retry attempts."""
        logger.warning(
            f"Retrying scraper task {task_id} due to {exc}. "
            f"Retry {self.request.retries}/{self.max_retries}"
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle and log failures."""
        logger.error(
            f"Scraper task {task_id} failed after {self.request.retries} retries: {exc}",
            exc_info=True
        )
        
        # Update scraper run status in database
        if 'run_id' in kwargs:
            asyncio.run(self._mark_run_failed(kwargs['run_id'], str(exc)))
    
    async def _mark_run_failed(self, run_id: str, error_message: str):
        """Mark scraper run as failed in database."""
        async with db_manager.get_session() as session:
            from sqlalchemy import update
            stmt = update(ScraperRun).where(
                ScraperRun.run_id == run_id
            ).values(
                status='FAILED',
                completed_at=datetime.utcnow(),
                error_message=error_message
            )
            await session.execute(stmt)
            await session.commit()

@shared_task(bind=True, base=ScraperTask, name='src.tasks.scraping_tasks.run_scraper_task')
def run_scraper_task(self, source: str, force_update: bool = False) -> Dict[str, Any]:
    """
    Main Celery task for running scrapers.
    
    Args:
        source: Data source name (OFAC, UN, EU, etc.)
        force_update: Force update even if content unchanged
        
    Returns:
        Dict with scraping results and metrics
    """
    run_id = f"{source}_{self.request.id}_{int(datetime.utcnow().timestamp())}"
    start_time = datetime.utcnow()
    
    try:
        logger.info(
            f"[{run_id}] Starting scraper for {source}",
            extra={
                "task_id": self.request.id,
                "source": source,
                "force_update": force_update
            }
        )
        
        # Run async scraping in sync context
        result = asyncio.run(
            _run_scraper_async(
                source=source,
                run_id=run_id,
                task_id=self.request.id,
                force_update=force_update
            )
        )
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        logger.info(
            f"[{run_id}] Scraper completed successfully in {duration:.2f}s",
            extra={
                "task_id": self.request.id,
                "duration_seconds": duration,
                **result
            }
        )
        
        return result
        
    except Exception as exc:
        duration = (datetime.utcnow() - start_time).total_seconds()
        error_result = {
            'run_id': run_id,
            'source': source,
            'status': 'FAILED',
            'error': str(exc),
            'duration_seconds': duration
        }
        
        logger.error(
            f"[{run_id}] Scraper failed: {exc}",
            extra={
                "task_id": self.request.id,
                **error_result
            },
            exc_info=True
        )
        
        # Retry the task with exponential backoff
        raise self.retry(exc=exc, countdown=min(60 * (2 ** self.request.retries), 3600))

async def _run_scraper_async(
    source: str,
    run_id: str,
    task_id: str,
    force_update: bool = False
) -> Dict[str, Any]:
    """
    Async implementation of scraper execution.
    """
    scraper_run = None
    
    try:
        # Step 1: Create scraper run record
        async with db_manager.get_session() as session:
            scraper_run = ScraperRun(
                run_id=run_id,
                source=source,
                started_at=datetime.utcnow(),
                status='RUNNING',
                celery_task_id=task_id
            )
            session.add(scraper_run)
            await session.commit()
        
        # Step 2: Get and execute scraper
        scraper = scraper_registry.create_scraper(f"us_{source.lower()}")
        if not scraper:
            raise ScrapingError(
                source=source,
                url="",
                context={"error": f"No scraper registered for {source}"}
            )
        
        # Step 3: Run scraper (with integrated change detection)
        scraping_result = await scraper.scrape_and_store()
        
        # Step 4: Update scraper run with results
        async with db_manager.get_session() as session:
            from sqlalchemy import update
            stmt = update(ScraperRun).where(
                ScraperRun.run_id == run_id
            ).values(
                completed_at=datetime.utcnow(),
                status=scraping_result.status,
                entities_processed=scraping_result.entities_processed,
                entities_added=scraping_result.entities_added,
                entities_modified=scraping_result.entities_updated,
                entities_removed=scraping_result.entities_removed,
                duration_seconds=int(scraping_result.duration_seconds),
                error_message=scraping_result.error_message
            )
            await session.execute(stmt)
            await session.commit()
        
        # Step 5: Trigger notifications for critical changes
        if scraping_result.status == "SUCCESS" and (
            scraping_result.entities_added > 0 or
            scraping_result.entities_removed > 0 or
            scraping_result.entities_updated > 0
        ):
            # Queue notification task
            from src.tasks.notification_tasks import send_change_notifications_task
            send_change_notifications_task.delay(
                run_id=run_id,
                source=source,
                changes_summary={
                    'added': scraping_result.entities_added,
                    'modified': scraping_result.entities_updated,
                    'removed': scraping_result.entities_removed
                }
            )
        
        return {
            'run_id': run_id,
            'source': source,
            'status': scraping_result.status,
            'entities_processed': scraping_result.entities_processed,
            'entities_added': scraping_result.entities_added,
            'entities_modified': scraping_result.entities_updated,
            'entities_removed': scraping_result.entities_removed,
            'duration_seconds': scraping_result.duration_seconds
        }
        
    except Exception as exc:
        # Update scraper run as failed
        if scraper_run:
            async with db_manager.get_session() as session:
                from sqlalchemy import update
                stmt = update(ScraperRun).where(
                    ScraperRun.run_id == run_id
                ).values(
                    completed_at=datetime.utcnow(),
                    status='FAILED',
                    error_message=str(exc)
                )
                await session.execute(stmt)
                await session.commit()
        raise

@shared_task(name='src.tasks.scraping_tasks.scrape_all_sources_task')
def scrape_all_sources_task() -> Dict[str, Any]:
    """
    Task to scrape all configured sources.
    """
    sources = ['OFAC', 'UN', 'EU', 'UK_HMT']
    results = {}
    
    for source in sources:
        try:
            # Use apply_async to run in parallel with different queues
            result = run_scraper_task.apply_async(
                args=[source],
                queue='scraping',
                priority=5
            )
            results[source] = {
                'task_id': result.id,
                'status': 'QUEUED'
            }
        except Exception as exc:
            results[source] = {
                'status': 'FAILED',
                'error': str(exc)
            }
            logger.error(f"Failed to queue scraper for {source}: {exc}")
    
    return results

@shared_task(name='src.tasks.scraping_tasks.check_scraper_health_task')
def check_scraper_health_task() -> Dict[str, Any]:
    """
    Health check task for scraping system.
    """
    health_status = {
        'timestamp': datetime.utcnow().isoformat(),
        'sources': {}
    }
    
    # Check last run for each source
    asyncio.run(_check_scraper_health_async(health_status))
    
    return health_status

async def _check_scraper_health_async(health_status: Dict[str, Any]):
    """
    Async implementation of health check.
    """
    async with db_manager.get_session() as session:
        from sqlalchemy import select, func
        
        # Get last run for each source
        stmt = select(
            ScraperRun.source,
            func.max(ScraperRun.started_at).label('last_run'),
            func.count(ScraperRun.run_id).label('total_runs')
        ).group_by(ScraperRun.source)
        
        result = await session.execute(stmt)
        
        for row in result:
            last_run_time = row.last_run
            hours_since_last = (
                (datetime.utcnow() - last_run_time).total_seconds() / 3600
                if last_run_time else None
            )
            
            health_status['sources'][row.source] = {
                'last_run': last_run_time.isoformat() if last_run_time else None,
                'hours_since_last': hours_since_last,
                'total_runs': row.total_runs,
                'status': 'HEALTHY' if hours_since_last and hours_since_last < 24 else 'WARNING'
            }

# ======================== EXPORTS ========================

__all__ = [
    'run_scraper_task',
    'scrape_all_sources_task',
    'check_scraper_health_task'
]