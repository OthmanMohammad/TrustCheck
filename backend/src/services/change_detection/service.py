"""
Change Detection Service - Complete Implementation

Business service for change detection operations using Clean Architecture patterns.
Uses repository interfaces through Unit of Work for data access.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

# Core domain imports (no infrastructure dependencies)
from src.core.uow import UnitOfWork
from src.core.domain.entities import (
    SanctionedEntityDomain, ChangeEventDomain, ScraperRunDomain,
    ChangeDetectionResult, ScrapingRequest, create_sanctioned_entity,
    create_change_event, FieldChange
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
            self.logger.error(f"Change detection failed: {e}", exc_info=True)
            raise ChangeDetectionError(source.value, "change_detection", cause=e) from e
            
    async def get_change_summary(
        self,
        days: int = 7,
        source: Optional[DataSource] = None,
        risk_level: Optional[RiskLevel] = None
    ) -> Dict[str, Any]:
        """Get summary of changes over time period."""
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                since = datetime.utcnow() - timedelta(days=days)
                
                # Get recent changes with filters
                changes = await uow.change_events.find_recent(
                    days=days,
                    source=source,
                    risk_level=risk_level
                )
                
                # FIXED: Handle None/empty results
                if not changes:
                    changes = []
                
                # Get change counts by risk level
                risk_counts = await uow.change_events.count_by_risk_level(
                    since=since,
                    source=source
                )
                
                # FIXED: Ensure risk_counts is never None
                if not risk_counts:
                    risk_counts = {}
                
                # Get change counts by type
                type_counts = await uow.change_events.count_by_change_type(
                    since=since,
                    source=source
                )
                
                # FIXED: Ensure type_counts is never None
                if not type_counts:
                    type_counts = {}
                
                # Calculate summary metrics with safe defaults
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
                        'critical_changes': risk_counts.get(RiskLevel.CRITICAL, 0) if risk_counts else 0,
                        'high_risk_changes': risk_counts.get(RiskLevel.HIGH, 0) if risk_counts else 0,
                        'medium_risk_changes': risk_counts.get(RiskLevel.MEDIUM, 0) if risk_counts else 0,
                        'low_risk_changes': risk_counts.get(RiskLevel.LOW, 0) if risk_counts else 0
                    },
                    'by_type': {
                        'added': type_counts.get(ChangeType.ADDED, 0) if type_counts else 0,
                        'modified': type_counts.get(ChangeType.MODIFIED, 0) if type_counts else 0,
                        'removed': type_counts.get(ChangeType.REMOVED, 0) if type_counts else 0
                    },
                    'by_risk_level': {
                        risk_level.value: count 
                        for risk_level, count in risk_counts.items()
                    } if risk_counts else {}
                }
                
                return summary
                
        except Exception as e:
            self.logger.error(f"Failed to get change summary: {e}", exc_info=True)
            # FIXED: Return empty summary structure on error
            return {
                'period': {
                    'days': days,
                    'start_date': datetime.utcnow().isoformat(),
                    'end_date': datetime.utcnow().isoformat()
                },
                'filters': {
                    'source': source.value if source else None,
                    'risk_level': risk_level.value if risk_level else None
                },
                'totals': {
                    'total_changes': 0,
                    'critical_changes': 0,
                    'high_risk_changes': 0,
                    'medium_risk_changes': 0,
                    'low_risk_changes': 0
                },
                'by_type': {
                    'added': 0,
                    'modified': 0,
                    'removed': 0
                },
                'by_risk_level': {}
            }
    
    async def get_critical_changes(
        self,
        hours: int = 24,
        source: Optional[DataSource] = None
    ) -> List[ChangeEventDomain]:
        """Get critical changes requiring immediate attention."""
        try:
            async with self.uow_factory.create_async_unit_of_work() as uow:
                since = datetime.utcnow() - timedelta(hours=hours)
                
                critical_changes = await uow.change_events.find_by_risk_level(
                    risk_level=RiskLevel.CRITICAL,
                    since=since,
                    limit=100
                )
                
                # Filter by source if provided
                if source and critical_changes:
                    critical_changes = [
                        change for change in critical_changes 
                        if change.source == source
                    ]
                
                # FIXED: Always return a list, even if empty
                if not critical_changes:
                    critical_changes = []
                
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
            self.logger.error(f"Failed to get critical changes: {e}", exc_info=True)
            # FIXED: Return empty list on error instead of raising
            return []
    
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
    
    def _compare_entities(self, old_entity: Dict[str, Any], new_entity: Dict[str, Any]) -> List[FieldChange]:
        """Compare two entities and return list of field changes."""
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

# ======================== EXPORTS ========================

__all__ = [
    'ChangeDetectionService'
]