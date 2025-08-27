"""
Updated Service Layer Using Repository Pattern

Business logic services that depend on repository interfaces instead of direct database access.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

# Core domain imports (no infrastructure dependencies)
from src.core.uow import UnitOfWork
from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain,
    ChangeDetectionResult, ScrapingRequest, create_sanctioned_entity,
    create_change_event
)
from src.core.enums import DataSource, ChangeType, RiskLevel, ScrapingStatus
from src.core.exceptions import (
    BusinessLogicError, ChangeDetectionError, ScrapingError,
    ValidationError, handle_exception
)
from src.core.logging_config import get_logger, log_exception, log_performance

# Infrastructure interfaces (not implementations)
from src.infrastructure.database.uow import SQLAlchemyUnitOfWorkFactory

logger = get_logger(__name__)

# ======================== CHANGE DETECTION SERVICE ========================

class ChangeDetectionService:
    """
    Business service for change detection operations.
    
    Uses repository interfaces through Unit of Work for data access.
    Contains all business logic for detecting and classifying changes.
    """
    
    def __init__(self, uow_factory: SQLAlchemyUnitOfWorkFactory):
        self.uow_factory = uow_factory
        self.logger = get_logger(__name__)
    
    async def detect_changes_for_source(
        self,
        source: DataSource,
        new_entities_data: List[Dict[str, Any]],
        scraper_run_id: str,
        old_content_hash: str = "",
        new_content_hash: str = ""
    ) -> ChangeDetectionResult:
        """
        Detect changes for a specific data source.
        
        Args:
            source: Data source being processed
            new_entities_data: New entity data from scraping
            scraper_run_id: ID of the scraper run
            old_content_hash: Hash of previous content
            new_content_hash: Hash of current content
            
        Returns:
            ChangeDetectionResult with detected changes and metrics
        """
        start_time = datetime.utcnow()
        
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                self.logger.info(
                    f"Starting change detection for {source.value}",
                    extra={
                        "source": source.value,
                        "new_entities_count": len(new_entities_data),
                        "scraper_run_id": scraper_run_id
                    }
                )
                
                # Step 1: Get current entities from repository
                current_entities = await uow.sanctioned_entities.get_all_for_change_detection(source)
                
                # Step 2: Convert to comparable format
                current_entities_dict = self._entities_to_dict(current_entities)
                
                # Step 3: Detect changes
                changes = await self._detect_entity_changes(
                    old_entities=current_entities_dict,
                    new_entities=new_entities_data,
                    source=source,
                    scraper_run_id=scraper_run_id
                )
                
                # Step 4: Store change events
                if changes:
                    stored_changes = await uow.change_events.create_many(changes)
                else:
                    stored_changes = []
                
                # Step 5: Calculate metrics
                metrics = self._calculate_change_metrics(changes, current_entities_dict, new_entities_data)
                
                processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                result = ChangeDetectionResult(
                    changes_detected=stored_changes,
                    entities_added=metrics['entities_added'],
                    entities_modified=metrics['entities_modified'],
                    entities_removed=metrics['entities_removed'],
                    processing_time_ms=int(processing_time),
                    content_changed=len(changes) > 0
                )
                
                await uow.commit()
                
                log_performance(
                    self.logger,
                    "change_detection",
                    processing_time,
                    success=True,
                    source=source.value,
                    changes_detected=len(changes),
                    entities_processed=len(new_entities_data)
                )
                
                return result
                
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "detect_changes_for_source",
                "source": source.value,
                "scraper_run_id": scraper_run_id
            })
            raise ChangeDetectionError(source.value, "change_detection", cause=e) from error
    
    async def get_change_summary(
        self,
        days: int = 7,
        source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None
    ) -> Dict[str, Any]:
        """
        Get summary of changes over time period.
        
        Args:
            days: Number of days to look back
            source: Optional source filter
            risk_level: Optional risk level filter
            
        Returns:
            Dict with change summary statistics
        """
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                since = datetime.utcnow() - timedelta(days=days)
                
                # Get recent changes with filters
                changes = await uow.change_events.find_recent(
                    days=days,
                    source=source,
                    risk_level=risk_level
                )
                
                # Get change counts by risk level
                risk_counts = await uow.change_events.count_by_risk_level(
                    since=since,
                    source=source
                )
                
                # Get change counts by type
                type_counts = await uow.change_events.count_by_change_type(
                    since=since,
                    source=source
                )
                
                # Calculate summary metrics
                summary = {
                    'period': {
                        'days': days,
                        'start_date': since.isoformat(),
                        'end_date': datetime.utcnow().isoformat()
                    },
                    'filters': {
                        'source': source.value if source else None,
                        'risk_level': risk_level.value if risk_level else None
                    },
                    'totals': {
                        'total_changes': len(changes),
                        'critical_changes': risk_counts.get(RiskLevel.CRITICAL, 0),
                        'high_risk_changes': risk_counts.get(RiskLevel.HIGH, 0),
                        'medium_risk_changes': risk_counts.get(RiskLevel.MEDIUM, 0),
                        'low_risk_changes': risk_counts.get(RiskLevel.LOW, 0)
                    },
                    'by_type': {
                        'added': type_counts.get(ChangeType.ADDED, 0),
                        'modified': type_counts.get(ChangeType.MODIFIED, 0),
                        'removed': type_counts.get(ChangeType.REMOVED, 0)
                    },
                    'by_risk_level': {
                        risk_level.value: count 
                        for risk_level, count in risk_counts.items()
                    }
                }
                
                return summary
                
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "get_change_summary",
                "days": days,
                "source": source.value if source else None
            })
            raise ChangeDetectionError("system", "summary_generation", cause=e) from error
    
    async def get_critical_changes(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None
    ) -> List[ChangeEventDomain]:
        """
        Get critical changes requiring immediate attention.
        
        Args:
            hours: Hours to look back
            source: Optional source filter
            
        Returns:
            List of critical change events
        """
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                critical_changes = await uow.change_events.find_by_risk_level(
                    risk_level=RiskLevel.CRITICAL,
                    since=since,
                    limit=100  # Reasonable limit for critical changes
                )
                
                if source:
                    critical_changes = [
                        change for change in critical_changes 
                        if change.source == source
                    ]
                
                self.logger.info(
                    f"Found {len(critical_changes)} critical changes in last {hours} hours",
                    extra={
                        "critical_changes_count": len(critical_changes),
                        "hours": hours,
                        "source": source.value if source else "all"
                    }
                )
                
                return critical_changes
                
        except Exception as e:
            error = handle_exception(e, self.logger, context={
                "operation": "get_critical_changes",
                "hours": hours,
                "source": source.value if source else None
            })
            raise ChangeDetectionError("system", "critical_changes_query", cause=e) from error
    
    # ======================== PRIVATE HELPER METHODS ========================
    
    def _entities_to_dict(self, entities: List[SanctionedEntityDomain]) -> List[Dict[str, Any]]:
        """Convert domain entities to dictionary format for comparison."""
        return [
            {
                'uid': entity.uid,
                'name': entity.name,
                'entity_type': entity.entity_type.value,
                'programs': entity.programs,
                'aliases': entity.aliases,
                'addresses': [str(addr) for addr in entity.addresses],
                'nationalities': entity.nationalities,
                'remarks': entity.remarks
            }
            for entity in entities
        ]
    
    async def _detect_entity_changes(
        self,
        old_entities: List[Dict[str, Any]],
        new_entities: List[Dict[str, Any]],
        source: DataSource,
        scraper_run_id: str
    ) -> List[ChangeEventDomain]:
        """Detect changes between old and new entity sets."""
        changes = []
        
        # Create lookup maps
        old_entities_map = {entity['uid']: entity for entity in old_entities}
        new_entities_map = {entity['uid']: entity for entity in new_entities}
        
        old_uids = set(old_entities_map.keys())
        new_uids = set(new_entities_map.keys())
        
        # Detect additions
        added_uids = new_uids - old_uids
        for uid in added_uids:
            change = create_change_event(
                entity_uid=uid,
                entity_name=new_entities_map[uid]['name'],
                change_type=ChangeType.ADDED,
                field_changes=[],  # No field changes for additions
                source=source,
                scraper_run_id=scraper_run_id
            )
            changes.append(change)
        
        # Detect removals
        removed_uids = old_uids - new_uids
        for uid in removed_uids:
            change = create_change_event(
                entity_uid=uid,
                entity_name=old_entities_map[uid]['name'],
                change_type=ChangeType.REMOVED,
                field_changes=[],  # No field changes for removals
                source=source,
                scraper_run_id=scraper_run_id
            )
            changes.append(change)
        
        # Detect modifications
        common_uids = old_uids & new_uids
        for uid in common_uids:
            old_entity = old_entities_map[uid]
            new_entity = new_entities_map[uid]
            
            field_changes = self._compare_entities(old_entity, new_entity)
            if field_changes:
                change = create_change_event(
                    entity_uid=uid,
                    entity_name=new_entity['name'],
                    change_type=ChangeType.MODIFIED,
                    field_changes=field_changes,
                    source=source,
                    scraper_run_id=scraper_run_id
                )
                changes.append(change)
        
        return changes
    
    def _compare_entities(self, old_entity: Dict[str, Any], new_entity: Dict[str, Any]) -> List:
        """Compare two entities and return list of field changes."""
        from src.core.domain.entities import FieldChange
        
        changes = []
        tracked_fields = ['name', 'entity_type', 'programs', 'aliases', 'addresses', 'nationalities', 'remarks']
        
        for field in tracked_fields:
            old_value = old_entity.get(field)
            new_value = new_entity.get(field)
            
            if self._values_differ(old_value, new_value):
                change_type = 'field_modified'
                if old_value is None:
                    change_type = 'field_added'
                elif new_value is None:
                    change_type = 'field_removed'
                
                changes.append(FieldChange(
                    field_name=field,
                    old_value=old_value,
                    new_value=new_value,
                    change_type=change_type
                ))
        
        return changes
    
    def _values_differ(self, old_value: Any, new_value: Any) -> bool:
        """Check if values represent meaningful differences."""
        if old_value is None and new_value is None:
            return False
        if old_value is None or new_value is None:
            return True
        
        # Handle lists (normalize and compare as sets)
        if isinstance(old_value, list) and isinstance(new_value, list):
            old_set = set(str(item).strip() for item in old_value if item)
            new_set = set(str(item).strip() for item in new_value if item)
            return old_set != new_set
        
        # Handle strings (normalize whitespace)
        if isinstance(old_value, str) and isinstance(new_value, str):
            return old_value.strip() != new_value.strip()
        
        return old_value != new_value
    
    def _calculate_change_metrics(
        self,
        changes: List[ChangeEventDomain],
        old_entities: List[Dict[str, Any]],
        new_entities: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Calculate change metrics from detected changes."""
        old_uids = {entity['uid'] for entity in old_entities}
        new_uids = {entity['uid'] for entity in new_entities}
        
        return {
            'entities_added': len(new_uids - old_uids),
            'entities_modified': len([c for c in changes if c.change_type == ChangeType.MODIFIED]),
            'entities_removed': len(old_uids - new_uids)
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of change detection service."""
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                uow_health = await uow.health_check()
                
                return {
                    'healthy': uow_health.get('overall_healthy', False),
                    'status': 'operational' if uow_health.get('overall_healthy') else 'degraded',
                    'dependencies': {
                        'unit_of_work': uow_health
                    }
                }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'failed',
                'error': str(e)
            }

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
    
    def __init__(self, uow_factory: SQLAlchemyUnitOfWorkFactory):
        self.uow_factory = uow_factory
        self.logger = get_logger(__name__)
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
            # FIXED: Don't pass user_message when converting to ScrapingError
            raise ScrapingError(
                source=request.source.value,
                url="orchestration",
                context={"run_id": run_id, "error": str(e)}
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
            # FIXED: Don't pass user_message when converting to ScrapingError
            raise ScrapingError(
                source="system",
                url="status_query",
                context={"hours": hours, "error": str(e)}
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
        
        scraper = scraper_registry.create_scraper(request.source.value)
        if not scraper:
            raise ScrapingError(
                source=request.source.value,
                url="scraper_not_found",
                context={"error": f"No scraper found for source: {request.source.value}"}
            )
        
        # Execute scraping (this would be adapted to return proper format)
        result = scraper.scrape_and_store()
        
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
        # This would integrate with notification service
        critical_changes = change_result.get_changes_by_risk(RiskLevel.CRITICAL)
        
        self.logger.warning(
            f"Triggering notifications for {len(critical_changes)} critical changes",
            extra={
                "critical_changes_count": len(critical_changes),
                "total_changes": change_result.total_changes
            }
        )
        
        # Would implement actual notification dispatch
    
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
    'ChangeDetectionService',
    'ScrapingOrchestrationService'
]