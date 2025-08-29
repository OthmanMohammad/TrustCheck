"""
Maintenance and cleanup Celery tasks.
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

from src.infrastructure.database.connection import db_manager

logger = get_task_logger(__name__)

@shared_task(name='src.tasks.maintenance_tasks.cleanup_old_data_task')
def cleanup_old_data_task(days_to_keep: int = 90) -> Dict[str, Any]:
    """
    Clean up old data from database.
    """
    logger.info(f"Starting cleanup of data older than {days_to_keep} days")
    
    result = asyncio.run(_cleanup_old_data_async(days_to_keep))
    
    return result

async def _cleanup_old_data_async(days_to_keep: int) -> Dict[str, Any]:
    """
    Async implementation of data cleanup.
    """
    from sqlalchemy import delete
    from src.infrastructure.database.models import (
        ScraperRun, ChangeEvent, ContentSnapshot
    )
    
    cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
    cleanup_stats = {}
    
    async with db_manager.get_session() as session:
        # Clean old scraper runs
        stmt = delete(ScraperRun).where(
            ScraperRun.started_at < cutoff_date
        )
        result = await session.execute(stmt)
        cleanup_stats['scraper_runs_deleted'] = result.rowcount
        
        # Clean old change events
        stmt = delete(ChangeEvent).where(
            ChangeEvent.detected_at < cutoff_date
        )
        result = await session.execute(stmt)
        cleanup_stats['change_events_deleted'] = result.rowcount
        
        # Clean old content snapshots
        stmt = delete(ContentSnapshot).where(
            ContentSnapshot.snapshot_time < cutoff_date
        )
        result = await session.execute(stmt)
        cleanup_stats['content_snapshots_deleted'] = result.rowcount
        
        await session.commit()
    
    logger.info(
        f"Cleanup completed: {cleanup_stats}",
        extra=cleanup_stats
    )
    
    return {
        'status': 'SUCCESS',
        'cutoff_date': cutoff_date.isoformat(),
        **cleanup_stats
    }

@shared_task(name='src.tasks.maintenance_tasks.health_check_task')
def health_check_task() -> Dict[str, Any]:
    """
    System health check task.
    """
    health_status = {
        'timestamp': datetime.utcnow().isoformat(),
        'status': 'HEALTHY',
        'checks': {}
    }
    
    # Database health
    try:
        asyncio.run(_check_database_health(health_status))
        health_status['checks']['database'] = 'OK'
    except Exception as exc:
        health_status['checks']['database'] = f'FAILED: {exc}'
        health_status['status'] = 'UNHEALTHY'
    
    # Redis health
    try:
        from src.celery_app import app
        app.backend.get('health_check_test')
        health_status['checks']['redis'] = 'OK'
    except Exception as exc:
        health_status['checks']['redis'] = f'FAILED: {exc}'
        health_status['status'] = 'UNHEALTHY'
    
    logger.info(
        f"Health check: {health_status['status']}",
        extra=health_status
    )
    
    return health_status

async def _check_database_health(health_status: Dict[str, Any]):
    """
    Check database connectivity.
    """
    async with db_manager.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

# ======================== EXPORTS ========================

__all__ = [
    'cleanup_old_data_task',
    'health_check_task'
]