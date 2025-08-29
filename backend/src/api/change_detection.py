"""
API v1 - Now Fully Async with Proper Await Calls
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.logging_config import get_logger

from src.api.dependencies import (
    get_sanctioned_entity_repository,
    get_change_event_repository,
    get_change_detection_service
)

from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.services.change_detection.service import ChangeDetectionService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["TrustCheck API v1"])

@router.get("/entities")
async def list_entities(
    request: Request,
    source: Optional[DataSource] = Query(None),
    entity_type: Optional[EntityType] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """List sanctioned entities."""
    try:
        # FIXED: Now properly awaiting async repository methods
        if source:
            entities = await entity_repo.find_by_source(source, active_only, limit, offset)
        elif entity_type:
            entities = await entity_repo.find_by_entity_type(entity_type, limit, offset)
        else:
            entities = await entity_repo.find_all(active_only, limit, offset)
        
        # FIXED: Await the async get_statistics call
        stats = await entity_repo.get_statistics()
        
        # Convert to response format
        entity_results = []
        for entity in entities:
            entity_dict = {
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                "source": entity.source.value if hasattr(entity.source, 'value') else str(entity.source),
                "programs": entity.programs,
                "aliases": entity.aliases[:3] if entity.aliases else [],
                "is_active": entity.is_active,
                "last_updated": entity.updated_at.isoformat() if entity.updated_at else None
            }
            entity_results.append(entity_dict)
        
        return {
            "success": True,
            "data": {
                "entities": entity_results,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned": len(entity_results),
                    "has_more": len(entity_results) == limit
                },
                "statistics": stats
            },
            "metadata": {
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        }
    except Exception as e:
        logger.error(f"Error in list_entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/entities/search")
async def search_entities(
    request: Request,
    name: str = Query(..., min_length=2),
    fuzzy: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Search entities by name."""
    try:
        # FIXED: Await the async search_by_name call
        entities = await entity_repo.search_by_name(name, fuzzy=fuzzy, limit=limit)
        
        results = []
        for entity in entities:
            results.append({
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
                "source": entity.source.value if hasattr(entity.source, 'value') else str(entity.source),
                "programs": entity.programs
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
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Get entity by UID."""
    try:
        # FIXED: Await the async get_by_uid call
        entity = await entity_repo.get_by_uid(uid)
        
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {uid} not found")
        
        # Convert addresses to string format
        address_strings = []
        if entity.addresses:
            for addr in entity.addresses:
                if hasattr(addr, 'to_string'):
                    address_strings.append(addr.to_string())
                else:
                    address_strings.append(str(addr))
        
        entity_dict = {
            "uid": entity.uid,
            "name": entity.name,
            "type": entity.entity_type.value if hasattr(entity.entity_type, 'value') else str(entity.entity_type),
            "source": entity.source.value if hasattr(entity.source, 'value') else str(entity.source),
            "programs": entity.programs,
            "aliases": entity.aliases,
            "addresses": address_strings,
            "nationalities": entity.nationalities,
            "is_active": entity.is_active,
            "last_updated": entity.updated_at.isoformat() if entity.updated_at else None
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

@router.get("/changes")
async def list_changes(
    request: Request,
    source: Optional[DataSource] = Query(None),
    risk_level: Optional[RiskLevel] = Query(None),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    change_repo: SQLAlchemyChangeEventRepository = Depends(get_change_event_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """List recent changes."""
    try:
        # FIXED: Await all async calls
        changes = await change_repo.find_recent(
            days=days,
            source=source,
            risk_level=risk_level,
            limit=limit,
            offset=offset
        )
        
        # FIXED: Await the async service call
        summary = await change_detection_service.get_change_summary(
            days=days,
            source=source,
            risk_level=risk_level
        )
        
        # FIXED: Await the async get_critical_changes call
        critical_changes = []
        if not risk_level or risk_level == RiskLevel.CRITICAL:
            critical_changes = await change_detection_service.get_critical_changes(
                hours=days * 24,
                source=source
            )
        
        # Format changes for response
        changes_formatted = []
        for change in changes:
            try:
                change_dict = {
                    "event_id": str(change.event_id) if change.event_id else None,
                    "entity_name": change.entity_name,
                    "entity_uid": change.entity_uid,
                    "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                    "risk_level": change.risk_level.value if hasattr(change.risk_level, 'value') else str(change.risk_level),
                    "change_summary": change.change_summary,
                    "detected_at": change.detected_at.isoformat() if change.detected_at else None
                }
                changes_formatted.append(change_dict)
            except Exception as e:
                logger.warning(f"Error formatting change: {e}")
        
        # Format critical changes for response
        critical_changes_formatted = []
        for change in critical_changes[:10]:  # Limit to 10 for response size
            try:
                change_dict = {
                    "event_id": str(change.event_id) if change.event_id else None,
                    "entity_name": change.entity_name,
                    "entity_uid": change.entity_uid,
                    "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                    "risk_level": change.risk_level.value if hasattr(change.risk_level, 'value') else str(change.risk_level),
                    "change_summary": change.change_summary,
                    "detected_at": change.detected_at.isoformat() if change.detected_at else None
                }
                critical_changes_formatted.append(change_dict)
            except Exception as e:
                logger.warning(f"Error formatting critical change: {e}")
        
        return {
            "success": True,
            "data": {
                "changes": changes_formatted,
                "summary": summary,
                "critical_changes": critical_changes_formatted,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "returned": len(changes_formatted),
                    "has_more": len(changes_formatted) == limit
                }
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
    hours: int = Query(24, ge=1, le=168),
    source: Optional[DataSource] = Query(None),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get critical changes requiring immediate attention."""
    try:
        # FIXED: Await the async service call
        critical_changes = await change_detection_service.get_critical_changes(
            hours=hours,
            source=source
        )
        
        # Format changes for response
        changes_formatted = []
        for change in critical_changes:
            try:
                change_dict = {
                    "event_id": str(change.event_id) if change.event_id else None,
                    "entity_name": change.entity_name,
                    "entity_uid": change.entity_uid,
                    "change_type": change.change_type.value if hasattr(change.change_type, 'value') else str(change.change_type),
                    "risk_level": change.risk_level.value if hasattr(change.risk_level, 'value') else str(change.risk_level),
                    "change_summary": change.change_summary,
                    "detected_at": change.detected_at.isoformat() if change.detected_at else None,
                    "field_changes": [
                        {
                            "field_name": fc.field_name,
                            "old_value": str(fc.old_value) if fc.old_value else None,
                            "new_value": str(fc.new_value) if fc.new_value else None,
                            "change_type": fc.change_type
                        }
                        for fc in (change.field_changes or [])
                    ]
                }
                changes_formatted.append(change_dict)
            except Exception as e:
                logger.warning(f"Error formatting critical change: {e}")
        
        return {
            "success": True,
            "data": {
                "critical_changes": changes_formatted,
                "count": len(changes_formatted),
                "period": {
                    "hours": hours,
                    "since": (datetime.utcnow() - timedelta(hours=hours)).isoformat(),
                    "until": datetime.utcnow().isoformat()
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

@router.get("/statistics")
async def get_statistics(
    request: Request,
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get statistics."""
    try:
        # FIXED: Await all async calls
        entity_stats = await entity_repo.get_statistics()
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

@router.get("/health")
async def health_check(
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_repo: SQLAlchemyChangeEventRepository = Depends(get_change_event_repository)
):
    """Health check endpoint."""
    try:
        # FIXED: Await the async health_check calls
        entity_health = await entity_repo.health_check()
        change_health = await change_repo.health_check()
        
        all_healthy = entity_health and change_health
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "checks": {
                "entities_repository": "ok" if entity_health else "failed",
                "changes_repository": "ok" if change_health else "failed"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

__all__ = ['router']