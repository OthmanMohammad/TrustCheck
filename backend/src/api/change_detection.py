"""
API v1 - Now Fully Async
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional
from datetime import datetime
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
        if source:
            entities = await entity_repo.find_by_source(source, active_only, limit, offset)
        elif entity_type:
            entities = await entity_repo.find_by_entity_type(entity_type, limit, offset)
        else:
            entities = await entity_repo.find_all(active_only, limit, offset)
        
        stats = await entity_repo.get_statistics()
        
        # Convert to response format
        entity_results = []
        for entity in entities:
            entity_dict = {
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type.value,
                "source": entity.source.value,
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
    name: str = Query(...),
    fuzzy: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Search entities by name."""
    try:
        entities = await entity_repo.search_by_name(name, fuzzy=fuzzy, limit=limit)
        
        results = []
        for entity in entities:
            results.append({
                "uid": entity.uid,
                "name": entity.name,
                "type": entity.entity_type.value,
                "source": entity.source.value,
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
        entity = await entity_repo.get_by_uid(uid)
        
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {uid} not found")
        
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
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """List recent changes."""
    try:
        summary = await change_detection_service.get_change_summary(
            days=days,
            source=source,
            risk_level=risk_level
        )
        
        critical_changes = []
        if not risk_level or risk_level == RiskLevel.CRITICAL:
            critical_changes = await change_detection_service.get_critical_changes(
                hours=days * 24,
                source=source
            )
        
        critical_changes_formatted = []
        for change in critical_changes[:10]:
            try:
                change_dict = {
                    "event_id": str(change.event_id) if change.event_id else None,
                    "entity_name": change.entity_name,
                    "entity_uid": change.entity_uid,
                    "change_type": change.change_type.value,
                    "risk_level": change.risk_level.value,
                    "change_summary": change.change_summary,
                    "detected_at": change.detected_at.isoformat()
                }
                critical_changes_formatted.append(change_dict)
            except Exception as e:
                logger.warning(f"Error formatting change: {e}")
        
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

@router.get("/statistics")
async def get_statistics(
    request: Request,
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get statistics."""
    try:
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

__all__ = ['router']