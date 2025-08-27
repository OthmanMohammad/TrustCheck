"""
Updated API Endpoints - FIXED Empty Response Bug
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

from src.core.domain.entities import ScrapingRequest
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.exceptions import (
    TrustCheckError, ResourceNotFoundError, ValidationError,
    BusinessLogicError, create_error_response
)
from src.core.logging_config import get_logger, LoggingContext, log_performance

from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService
from src.services.notification.service import NotificationService

from src.api.dependencies import (
    get_sanctioned_entity_repository, get_change_event_repository,
    get_scraper_run_repository, get_change_detection_service,
    get_scraping_service, get_unit_of_work, get_business_operations
)

from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository, ScraperRunRepository
)
from src.core.uow import UnitOfWork
from src.infrastructure.database.uow import UnitOfWorkBusinessOperations

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["TrustCheck API v1"])

# ======================== FIXED ENTITY ENDPOINTS ========================

@router.get("/entities")
async def list_entities(
    request: Request,
    source: Optional[DataSource] = Query(None, description="Filter by data source"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    active_only: bool = Query(True, description="Only return active entities"),
    limit: int = Query(50, description="Maximum results", ge=1, le=1000),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """
    List sanctioned entities with filtering and pagination - FIXED.
    """
    start_time = datetime.utcnow()
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                "Listing entities",
                extra={
                    "source": source.value if source else None,
                    "entity_type": entity_type.value if entity_type else None,
                    "active_only": active_only,
                    "limit": limit,
                    "offset": offset
                }
            )
            
            # FIXED: Properly handle different filter combinations
            entities = []
            
            if source:
                # Filter by source
                entities = await entity_repo.find_by_source(
                    source=source,
                    active_only=active_only,
                    limit=limit,
                    offset=offset
                )
            elif entity_type:
                # Filter by entity type
                entities = await entity_repo.find_by_entity_type(
                    entity_type=entity_type,
                    limit=limit,
                    offset=offset
                )
            else:
                # FIXED: Get all entities when no filters provided
                entities = await entity_repo.find_all(
                    active_only=active_only,
                    limit=limit,
                    offset=offset
                )
            
            # Also get statistics for the response
            stats = await entity_repo.get_statistics()
            
            # Convert domain entities to API response format
            entity_results = []
            for entity in entities:
                try:
                    entity_dict = {
                        "uid": entity.uid,
                        "name": entity.name,
                        "type": entity.entity_type.value,
                        "source": entity.source.value,
                        "programs": entity.programs,
                        "aliases": entity.aliases[:3] if entity.aliases else [],
                        "addresses": [str(addr) for addr in entity.addresses[:2]] if entity.addresses else [],
                        "nationalities": entity.nationalities,
                        "is_active": entity.is_active,
                        "last_updated": entity.updated_at.isoformat() if entity.updated_at else None,
                        "is_high_risk": entity.is_high_risk
                    }
                    entity_results.append(entity_dict)
                except Exception as e:
                    logger.warning(f"Error converting entity {entity.uid}: {e}")
                    continue
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            log_performance(
                logger,
                "list_entities",
                duration_ms,
                success=True,
                results_count=len(entity_results),
                source=source.value if source else None
            )
            
            return {
                "success": True,
                "data": {
                    "entities": entity_results,
                    "pagination": {
                        "limit": limit,
                        "offset": offset,
                        "returned": len(entity_results),
                        "has_more": len(entity_results) == limit,
                        "total_active": stats.get('total_active', 0)
                    },
                    "filters": {
                        "source": source.value if source else None,
                        "entity_type": entity_type.value if entity_type else None,
                        "active_only": active_only
                    },
                    "statistics": stats
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except TrustCheckError as e:
        logger.error(f"Business error in list_entities: {e}")
        raise HTTPException(status_code=400, detail=create_error_response(e))
    except Exception as e:
        logger.error(f"Unexpected error in list_entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ======================== FIXED CHANGE DETECTION ENDPOINTS ========================

@router.get("/changes")
async def list_changes(
    request: Request,
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    change_type: Optional[ChangeType] = Query(None, description="Filter by change type"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    days: int = Query(7, description="Days to look back", ge=1, le=90),
    limit: int = Query(50, description="Maximum results", ge=1, le=1000),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """List recent changes with filtering - FIXED async/await."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                "Listing changes",
                extra={
                    "source": source.value if source else None,
                    "change_type": change_type.value if change_type else None,
                    "risk_level": risk_level.value if risk_level else None,
                    "days": days
                }
            )
            
            # FIXED: Properly await async service methods
            summary = await change_detection_service.get_change_summary(
                days=days,
                source=source,
                risk_level=risk_level
            )
            
            # Get critical changes if needed
            critical_changes = []
            if not risk_level or risk_level == RiskLevel.CRITICAL:
                critical_changes = await change_detection_service.get_critical_changes(
                    hours=days * 24,
                    source=source
                )
            
            # Format critical changes for response
            critical_changes_formatted = []
            for change in critical_changes[:10]:  # Limit to 10 for response
                try:
                    change_dict = {
                        "event_id": str(change.event_id),
                        "entity_name": change.entity_name,
                        "entity_uid": change.entity_uid,
                        "change_type": change.change_type.value,
                        "risk_level": change.risk_level.value,
                        "change_summary": change.change_summary,
                        "detected_at": change.detected_at.isoformat() if change.detected_at else None,
                        "requires_immediate_attention": change.requires_immediate_notification
                    }
                    critical_changes_formatted.append(change_dict)
                except Exception as e:
                    logger.warning(f"Error formatting change {change.event_id}: {e}")
                    continue
            
            return {
                "success": True,
                "data": {
                    "summary": summary,
                    "critical_changes": critical_changes_formatted
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except Exception as e:
        logger.error(f"Error listing changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/changes/critical")
async def get_critical_changes(
    request: Request,
    hours: int = Query(24, description="Hours to look back", ge=1, le=168),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get critical changes requiring immediate attention - FIXED."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            # FIXED: Properly await async method
            critical_changes = await change_detection_service.get_critical_changes(
                hours=hours,
                source=source
            )
            
            # Format changes for response
            formatted_changes = []
            for change in critical_changes:
                try:
                    field_changes = []
                    if change.field_changes:
                        for fc in change.field_changes:
                            field_changes.append({
                                "field": fc.field_name,
                                "old_value": fc.old_value,
                                "new_value": fc.new_value,
                                "change_type": fc.change_type
                            })
                    
                    formatted_changes.append({
                        "event_id": str(change.event_id),
                        "entity_name": change.entity_name,
                        "entity_uid": change.entity_uid,
                        "source": change.source.value,
                        "change_type": change.change_type.value,
                        "change_summary": change.change_summary,
                        "field_changes": field_changes,
                        "detected_at": change.detected_at.isoformat() if change.detected_at else None,
                        "notification_sent": change.notification_sent_at.isoformat() if change.notification_sent_at else None
                    })
                except Exception as e:
                    logger.warning(f"Error formatting critical change: {e}")
                    continue
            
            return {
                "success": True,
                "data": {
                    "critical_changes": formatted_changes,
                    "count": len(formatted_changes),
                    "period": {
                        "hours": hours,
                        "since": (datetime.utcnow() - timedelta(hours=hours)).isoformat()
                    }
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting critical changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# Keep other endpoints as they are, just ensure all async methods are properly awaited

__all__ = ['router']