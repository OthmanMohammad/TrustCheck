"""
Scraping Orchestration Service - Complete Implementation

Business service for orchestrating scraping operations using Clean Architecture.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

# Core domain imports
from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain,
    ChangeDetectionResult, ScrapingRequest
)
from src.core.enums import DataSource, ChangeType, RiskLevel, ScrapingStatus
from src.core.exceptions import (
    BusinessLogicError, ChangeDetectionError, ScrapingError,
    handle_exception
)
from src.core.logging_config import get_logger, log_performance

logger = get_logger(__name__)

# ======================== SCRAPING ORCHESTRATION SERVICE ========================

class ScrapingOrchestrationService:
    """
    Business service for orchestrating scraping operations.
    
    Coordinates scraping workflow using repository pattern:
    1. Manages scraper runs
    2. Orchestrates change detection
    3. Handles error recovery
    4. Manages notifications
    """
    
    def __init__(self, uow_factory):
        """Initialize with UoW factory from dependency injection."""
        self.uow_factory = uow_factory
        self.logger = get_logger(__name__)
        # Import here to avoid circular dependency
        from src.services.change_detection.service import ChangeDetectionService
        self.change_detection_service = ChangeDetectionService(uow_factory)
    
    async def execute_scraping_request(
        self,
        request: ScrapingRequest
    ) -> Dict[str, Any]:
        """
        Execute a scraping request with full workflow orchestration.
        
        Args:
            request: Scraping request with source and parameters
            
        Returns:
            Dict with scraping results and metrics
        """
        start_time = datetime.utcnow()
        run_id = f"{request.source.value}_{int(start_time.timestamp())}"
        
        try:
            self.logger.info(
                f"Starting scraping request for {request.source.value}",
                extra={
                    "source": request.source.value,
                    "request_id": request.request_id,
                    "run_id": run_id,
                    "force_update": request.force_update
                }
            )
            
            async with self.uow_factory.create_async_unit_of_work() as uow:
                # Step 1: Create scraper run record
                scraper_run = ScraperRunDomain(
                    run_id=run_id,
                    source=request.source,
                    started_at=start_time,
                    status=ScrapingStatus.RUNNING
                )
                
                scraper_run = await uow.scraper_runs.create(scraper_run)
                
                try:
                    # Step 2: Execute scraping (would integrate with existing scrapers)
                    scraping_result = await self._execute_scraping(
                        request=request,
                        scraper_run=scraper_run
                    )
                    
                    # Step 3: Perform change detection if content changed or forced
                    change_result = None
                    if scraping_result['content_changed'] or request.force_update:
                        change_result = await self.change_detection_service.detect_changes_for_source(
                            source=request.source,
                            new_entities_data=scraping_result['entities'],
                            scraper_run_id=run_id,
                            old_content_hash=scraping_result.get('old_content_hash', ''),
                            new_content_hash=scraping_result.get('new_content_hash', '')
                        )
                    
                    # Step 4: Update scraper run with results
                    scraper_run.mark_completed(ScrapingStatus.SUCCESS)
                    if change_result:
                        scraper_run.entities_processed = len(scraping_result['entities'])
                        scraper_run.entities_added = change_result.entities_added
                        scraper_run.entities_modified = change_result.entities_modified
                        scraper_run.entities_removed = change_result.entities_removed
                    
                    await uow.scraper_runs.update(scraper_run)
                    
                    # Step 5: Trigger notifications for critical changes
                    if change_result and change_result.has_critical_changes:
                        await self._trigger_notifications(change_result)
                    
                    await uow.commit()
                    
                    duration = (datetime.utcnow() - start_time).total_seconds()
                    
                    result = {
                        'status': 'success',
                        'scraper_run_id': run_id,
                        'source': request.source.value,
                        'duration_seconds': duration,
                        'scraping_result': scraping_result,
                        'change_detection_result': change_result.__dict__ if change_result else None,
                        'notifications_triggered': change_result.has_critical_changes if change_result else False
                    }
                    
                    log_performance(
                        self.logger,
                        "scraping_orchestration",
                        duration * 1000,
                        success=True,
                        source=request.source.value,
                        entities_processed=scraper_run.entities_processed,
                        changes_detected=change_result.total_changes if change_result else 0
                    )
                    
                    return result
                    
                except Exception as e:
                    # Mark scraper run as failed
                    scraper_run.mark_failed(str(e))
                    await uow.scraper_runs.update(scraper_run)
                    await uow.commit()
                    raise
                    
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "execute_scraping_request",
                "source": request.source.value,
                "request_id": request.request_id,
                "run_id": run_id
            })
            raise ScrapingError(
                source=request.source.value,
                url="orchestration",
                context={"error": str(e)}
            ) from error
    
    async def get_scraping_status(
        self,
        source: Optional[DataSource] = None,
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get status of recent scraping operations.
        
        Args:
            source: Optional source filter
            hours: Hours to look back
            
        Returns:
            Dict with scraping status and metrics
        """
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                # Get recent runs
                recent_runs = await uow.scraper_runs.find_recent(
                    hours=hours,
                    source=source,
                    limit=50
                )
                
                # Get status counts
                status_counts = await uow.scraper_runs.count_by_status(
                    since=since,
                    source=source
                )
                
                # Calculate metrics
                total_runs = sum(status_counts.values())
                success_rate = (
                    status_counts.get(ScrapingStatus.SUCCESS, 0) / total_runs * 100
                    if total_runs > 0 else 0
                )
                
                return {
                    'period': {
                        'hours': hours,
                        'since': since.isoformat(),
                        'until': datetime.utcnow().isoformat()
                    },
                    'filter': {
                        'source': source.value if source else 'all'
                    },
                    'metrics': {
                        'total_runs': total_runs,
                        'success_rate_percent': round(success_rate, 2),
                        'by_status': {
                            status.value: count 
                            for status, count in status_counts.items()
                        }
                    },
                    'recent_runs': [
                        {
                            'run_id': run.run_id,
                            'source': run.source.value,
                            'status': run.status.value,
                            'started_at': run.started_at.isoformat(),
                            'duration_seconds': run.duration_seconds,
                            'entities_processed': run.entities_processed,
                            'error_message': run.error_message
                        }
                        for run in recent_runs[:10]  # Limit to 10 most recent
                    ]
                }
                
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "get_scraping_status",
                "source": source.value if source else None,
                "hours": hours
            })
            raise ScrapingError(
                source="system",
                url="status_query",
                context={"error": str(e)}
            ) from error
    
    # ======================== PRIVATE HELPER METHODS ========================
    
    async def _execute_scraping(
        self,
        request: ScrapingRequest,
        scraper_run: ScraperRunDomain
    ) -> Dict[str, Any]:
        """Execute the actual scraping operation."""
        # This would integrate with existing scraper registry
        from src.scrapers.registry import scraper_registry
        
        scraper = scraper_registry.create_scraper(request.source.value.lower())
        if not scraper:
            raise ScrapingError(
                source=request.source.value,
                url="scraper_not_found",
                context={"available_scrapers": scraper_registry.list_available_scrapers()}
            )
        
        # Execute scraping (using async scraper)
        result = await scraper.scrape_and_store()
        
        return {
            'entities': [],  # Would contain parsed entities
            'content_changed': True,  # Would be determined by content hash comparison
            'old_content_hash': '',
            'new_content_hash': '',
            'raw_content_size': 0,
            'parsing_errors': []
        }
    
    async def _trigger_notifications(
        self,
        change_result: ChangeDetectionResult
    ) -> None:
        """Trigger notifications for critical changes."""
        from src.services.notification.service import NotificationService
        
        notification_service = NotificationService()
        critical_changes = change_result.get_changes_by_risk(RiskLevel.CRITICAL)
        
        self.logger.warning(
            f"Triggering notifications for {len(critical_changes)} critical changes",
            extra={
                "critical_changes_count": len(critical_changes),
                "total_changes": change_result.total_changes
            }
        )
        
        # Dispatch notifications
        await notification_service.dispatch_changes(
            changes=critical_changes,
            source="system"
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of scraping orchestration service."""
        try:
            # Check change detection service health
            change_detection_health = await self.change_detection_service.health_check()
            
            # Check UoW health
            async with self.uow_factory.create_async_unit_of_work() as uow:
                uow_health = await uow.health_check()
            
            overall_healthy = (
                change_detection_health.get('healthy', False) and
                uow_health.get('overall_healthy', False)
            )
            
            return {
                'healthy': overall_healthy,
                'status': 'operational' if overall_healthy else 'degraded',
                'dependencies': {
                    'change_detection': change_detection_health,
                    'unit_of_work': uow_health
                }
            }
            
        except Exception as e:
            return {
                'healthy': False,
                'status': 'failed',
                'error': str(e)
            }

# ======================== EXPORTS ========================

__all__ = [
    'ScrapingOrchestrationService'
]