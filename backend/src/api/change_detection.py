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
    """List recent changes with filtering."""
    
    try:
        # Get change summary
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
        
        # Format response - FIXED: Handle None values properly
        critical_changes_formatted = []
        for change in critical_changes[:10]:
            try:
                change_dict = {
                    "event_id": str(change.event_id) if change.event_id else None,
                    "entity_name": change.entity_name if change.entity_name else "Unknown",
                    "entity_uid": change.entity_uid if change.entity_uid else "",
                    "change_type": change.change_type.value if change.change_type else "UNKNOWN",
                    "risk_level": change.risk_level.value if change.risk_level else "UNKNOWN",
                    "change_summary": change.change_summary if change.change_summary else "",
                    "detected_at": change.detected_at.isoformat() if change.detected_at else None
                }
                critical_changes_formatted.append(change_dict)
            except Exception as e:
                logger.warning(f"Error formatting change: {e}")
                continue
        
        return {
            "success": True,
            "data": {
                "summary": summary if summary else {},
                "critical_changes": critical_changes_formatted
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Error listing changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list changes: {str(e)}")

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
            
            # Format changes for response - FIXED: Handle empty results
            formatted_changes = []
            for change in critical_changes if critical_changes else []:
                try:
                    field_changes = []
                    if change.field_changes:
                        for fc in change.field_changes:
                            field_changes.append({
                                "field": fc.field_name if hasattr(fc, 'field_name') else "unknown",
                                "old_value": fc.old_value if hasattr(fc, 'old_value') else None,
                                "new_value": fc.new_value if hasattr(fc, 'new_value') else None,
                                "change_type": fc.change_type if hasattr(fc, 'change_type') else "unknown"
                            })
                    
                    formatted_changes.append({
                        "event_id": str(change.event_id) if change.event_id else None,
                        "entity_name": change.entity_name if change.entity_name else "Unknown",
                        "entity_uid": change.entity_uid if change.entity_uid else "",
                        "source": change.source.value if change.source else "UNKNOWN",
                        "change_type": change.change_type.value if change.change_type else "UNKNOWN",
                        "change_summary": change.change_summary if change.change_summary else "",
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
    
@router.get("/entities/search")
async def search_entities(
    request: Request,
    name: str = Query(..., description="Name to search for"),
    fuzzy: bool = Query(False, description="Use fuzzy matching"),
    limit: int = Query(20, ge=1, le=100),
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Search entities by name."""
    try:
        entities = await entity_repo.search_by_name(name, fuzzy=fuzzy, limit=limit)
        
        # Convert to response format
        results = []
        for entity in entities:
            results.append({
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type.value,
                "source": entity.source.value,
                "programs": entity.programs,
                "match_score": 1.0  # Would be calculated in fuzzy search
            })
        
        return {
            "success": True,
            "data": {
                "query": name,
                "results": results,
                "count": len(results)
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Error searching entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/entities/{uid}")
async def get_entity_by_uid(
    uid: str,
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Get entity by UID."""
    try:
        entity = await entity_repo.get_by_uid(uid)
        
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {uid} not found")
        
        # Convert to response format
        entity_dict = {
            "uid": entity.uid,
            "name": entity.name,
            "type": entity.entity_type.value,
            "source": entity.source.value,
            "programs": entity.programs,
            "aliases": entity.aliases,
            "addresses": [str(addr) for addr in entity.addresses] if entity.addresses else [],
            "nationalities": entity.nationalities,
            "is_active": entity.is_active,
            "last_updated": entity.updated_at.isoformat() if entity.updated_at else None,
            "is_high_risk": entity.is_high_risk
        }
        
        return {
            "success": True,
            "data": entity_dict,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity {uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))





@router.get("/statistics")
async def get_statistics(
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get comprehensive statistics."""
    try:
        # Get entity statistics
        entity_stats = await entity_repo.get_statistics()
        
        # Get change statistics
        change_summary = await change_detection_service.get_change_summary(days=7)
        
        return {
            "success": True,
            "data": {
                "entities": entity_stats,
                "changes": change_summary
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scraping/status")
async def get_scraping_status(
    request: Request,
    hours: int = Query(24, description="Hours to look back", ge=1, le=168),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
):
    """Get scraping status."""
    try:
        status = await scraping_service.get_scraping_status(
            source=source,
            hours=hours
        )
        
        return {
            "success": True,
            "data": status,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

__all__ = ['router']