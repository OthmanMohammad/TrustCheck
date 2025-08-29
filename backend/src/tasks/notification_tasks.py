"""
Celery tasks for notifications.
"""

from typing import Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from celery import shared_task
from celery.utils.log import get_task_logger

from src.services.notification.service import NotificationService
from src.infrastructure.database.connection import db_manager
from src.core.enums import RiskLevel

logger = get_task_logger(__name__)

@shared_task(name='src.tasks.notification_tasks.send_change_notifications_task')
def send_change_notifications_task(
    run_id: str,
    source: str,
    changes_summary: Dict[str, int]
) -> Dict[str, Any]:
    """
    Send notifications for detected changes.
    """
    logger.info(
        f"Sending notifications for run {run_id}",
        extra={
            "run_id": run_id,
            "source": source,
            "changes": changes_summary
        }
    )
    
    result = asyncio.run(
        _send_notifications_async(run_id, source, changes_summary)
    )
    
    return result

async def _send_notifications_async(
    run_id: str,
    source: str,
    changes_summary: Dict[str, int]
) -> Dict[str, Any]:
    """
    Async implementation of notification sending.
    """
    from src.infrastructure.database.models import ChangeEvent
    from sqlalchemy import select
    
    notification_service = NotificationService()
    
    async with db_manager.get_session() as session:
        # Get critical and high-risk changes
        stmt = select(ChangeEvent).where(
            ChangeEvent.scraper_run_id == run_id,
            ChangeEvent.risk_level.in_(['CRITICAL', 'HIGH'])
        )
        
        result = await session.execute(stmt)
        changes = result.scalars().all()
        
        if changes:
            # Convert to domain objects and send notifications
            from src.core.domain.entities import ChangeEventDomain
            
            domain_changes = []
            for change in changes:
                # Convert ORM to domain (simplified)
                domain_change = ChangeEventDomain(
                    event_id=change.event_id,
                    entity_uid=change.entity_uid,
                    entity_name=change.entity_name,
                    source=source,
                    change_type=change.change_type,
                    risk_level=change.risk_level,
                    change_summary=change.change_summary,
                    detected_at=change.detected_at
                )
                domain_changes.append(domain_change)
            
            # Send notifications
            dispatch_result = await notification_service.dispatch_changes(
                changes=domain_changes,
                source=source
            )
            
            return {
                'status': 'SUCCESS',
                'notifications_sent': dispatch_result.get('immediate_sent', 0),
                'run_id': run_id
            }
    
    return {
        'status': 'NO_CRITICAL_CHANGES',
        'run_id': run_id
    }

@shared_task(name='src.tasks.notification_tasks.send_daily_digest_task')
def send_daily_digest_task() -> Dict[str, Any]:
    """
    Send daily digest of all changes.
    """
    logger.info("Preparing daily digest")
    
    result = asyncio.run(_send_daily_digest_async())
    
    return result

async def _send_daily_digest_async() -> Dict[str, Any]:
    """
    Async implementation of daily digest.
    """
    from src.infrastructure.database.models import ChangeEvent
    from sqlalchemy import select, func
    
    notification_service = NotificationService()
    
    async with db_manager.get_session() as session:
        # Get change summary for last 24 hours
        since = datetime.utcnow() - timedelta(hours=24)
        
        stmt = select(
            ChangeEvent.source,
            ChangeEvent.risk_level,
            func.count(ChangeEvent.event_id).label('count')
        ).where(
            ChangeEvent.detected_at >= since
        ).group_by(
            ChangeEvent.source,
            ChangeEvent.risk_level
        )
        
        result = await session.execute(stmt)
        
        digest_data = {
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'total_changes': 0,
            'by_source': {},
            'by_risk_level': {}
        }
        
        for row in result:
            digest_data['total_changes'] += row.count
            
            if row.source not in digest_data['by_source']:
                digest_data['by_source'][row.source] = 0
            digest_data['by_source'][row.source] += row.count
            
            if row.risk_level not in digest_data['by_risk_level']:
                digest_data['by_risk_level'][row.risk_level] = 0
            digest_data['by_risk_level'][row.risk_level] += row.count
        
        if digest_data['total_changes'] > 0:
            # Send digest
            await notification_service.send_daily_digest()
            
            return {
                'status': 'SUCCESS',
                'changes_in_digest': digest_data['total_changes'],
                'digest_data': digest_data
            }
    
    return {
        'status': 'NO_CHANGES',
        'message': 'No changes to report in daily digest'
    }

# ======================== EXPORTS ========================

__all__ = [
    'send_change_notifications_task',
    'send_daily_digest_task'
]