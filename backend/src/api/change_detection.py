"""
Updated API Endpoints Using Repository Pattern

FastAPI endpoints that use dependency injection for repositories and services.
Clean separation between API layer and business logic.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

# Core domain imports (no infrastructure dependencies)
from src.core.domain.entities import ScrapingRequest
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.exceptions import (
    TrustCheckError, ResourceNotFoundError, ValidationError,
    BusinessLogicError, create_error_response
)
from src.core.logging_config import get_logger, LoggingContext, log_performance

# Service layer (business logic)
from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService
from src.services.notification.service import NotificationService

# Dependency injection
from src.api.dependencies import (
    get_sanctioned_entity_repository, get_change_event_repository,
    get_scraper_run_repository, get_change_detection_service,
    get_scraping_service, get_unit_of_work, get_business_operations
)

# Repository interfaces
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository, ScraperRunRepository
)
from src.core.uow import UnitOfWork
from src.infrastructure.database.uow import UnitOfWorkBusinessOperations

logger = get_logger(__name__)

# ======================== ROUTER SETUP ========================

router = APIRouter(prefix="/api/v1", tags=["TrustCheck API v1"])

# ======================== ENTITY ENDPOINTS ========================

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
    List sanctioned entities with filtering and pagination.
    
    Uses repository pattern for clean data access.
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
            
            # Use repository methods based on filters
            if source:
                entities = await entity_repo.find_by_source(
                    source=source,
                    active_only=active_only,
                    limit=limit,
                    offset=offset
                )
            elif entity_type:
                entities = await entity_repo.find_by_entity_type(
                    entity_type=entity_type,
                    limit=limit,
                    offset=offset
                )
            else:
                # Get general statistics and recent entities
                stats = await entity_repo.get_statistics()
                entities = []  # Would implement find_all with pagination
            
            # Convert domain entities to API response format
            entity_results = [
                {
                    "uid": entity.uid,
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "source": entity.source.value,
                    "programs": entity.programs,
                    "aliases": entity.aliases[:3],  # Limit for response size
                    "addresses": [str(addr) for addr in entity.addresses[:2]],
                    "nationalities": entity.nationalities,
                    "is_active": entity.is_active,
                    "last_updated": entity.updated_at.isoformat(),
                    "is_high_risk": entity.is_high_risk
                }
                for entity in entities
            ]
            
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
                        "has_more": len(entity_results) == limit
                    },
                    "filters": {
                        "source": source.value if source else None,
                        "entity_type": entity_type.value if entity_type else None,
                        "active_only": active_only
                    }
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
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/entities/{entity_uid}")
async def get_entity(
    request: Request,
    entity_uid: str,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Get specific entity by UID."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(f"Getting entity {entity_uid}")
            
            entity = await entity_repo.get_by_uid(entity_uid)
            
            if not entity:
                raise ResourceNotFoundError("Entity", entity_uid)
            
            return {
                "success": True,
                "data": {
                    "entity": {
                        "uid": entity.uid,
                        "name": entity.name,
                        "type": entity.entity_type.value,
                        "source": entity.source.value,
                        "programs": entity.programs,
                        "aliases": entity.aliases,
                        "addresses": [str(addr) for addr in entity.addresses],
                        "personal_info": {
                            "dates_of_birth": [entity.personal_info.date_of_birth] if entity.personal_info else [],
                            "places_of_birth": [entity.personal_info.place_of_birth] if entity.personal_info else [],
                            "nationalities": entity.nationalities
                        },
                        "remarks": entity.remarks,
                        "is_active": entity.is_active,
                        "is_high_risk": entity.is_high_risk,
                        "created_at": entity.created_at.isoformat(),
                        "updated_at": entity.updated_at.isoformat(),
                        "last_seen": entity.last_seen.isoformat() if entity.last_seen else None
                    }
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except ResourceNotFoundError as e:
        logger.warning(f"Entity not found: {entity_uid}")
        raise HTTPException(status_code=404, detail=create_error_response(e))
    except Exception as e:
        logger.error(f"Error getting entity {entity_uid}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/entities/search")
async def search_entities(
    request: Request,
    name: str = Query(..., min_length=2, description="Name to search for"),
    fuzzy: bool = Query(False, description="Enable fuzzy matching"),
    limit: int = Query(20, description="Maximum results", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0),
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
):
    """Search entities by name with fuzzy matching support."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                f"Searching entities for '{name}'",
                extra={"search_term": name, "fuzzy": fuzzy, "limit": limit}
            )
            
            entities = await entity_repo.search_by_name(
                name=name,
                fuzzy=fuzzy,
                limit=limit,
                offset=offset
            )
            
            results = [
                {
                    "uid": entity.uid,
                    "name": entity.name,
                    "type": entity.entity_type.value,
                    "source": entity.source.value,
                    "programs": entity.programs,
                    "aliases": entity.aliases,
                    "match_score": 1.0 if not fuzzy else None,  # Would calculate actual score
                    "is_active": entity.is_active
                }
                for entity in entities
            ]
            
            return {
                "success": True,
                "data": {
                    "query": {
                        "search_term": name,
                        "fuzzy_matching": fuzzy,
                        "limit": limit,
                        "offset": offset
                    },
                    "results": results,
                    "count": len(results)
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except ValidationError as e:
        logger.warning(f"Invalid search query: {e}")
        raise HTTPException(status_code=400, detail=create_error_response(e))
    except Exception as e:
        logger.error(f"Error searching entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# ======================== CHANGE DETECTION ENDPOINTS ========================

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
            
            # Get change summary from service
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
            
            return {
                "success": True,
                "data": {
                    "summary": summary,
                    "critical_changes": [
                        {
                            "event_id": str(change.event_id),
                            "entity_name": change.entity_name,
                            "entity_uid": change.entity_uid,
                            "change_type": change.change_type.value,
                            "risk_level": change.risk_level.value,
                            "change_summary": change.change_summary,
                            "detected_at": change.detected_at.isoformat(),
                            "requires_immediate_attention": change.requires_immediate_notification
                        }
                        for change in critical_changes[:10]  # Limit critical changes in response
                    ]
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except Exception as e:
        logger.error(f"Error listing changes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/changes/critical")
async def get_critical_changes(
    request: Request,
    hours: int = Query(24, description="Hours to look back", ge=1, le=168),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get critical changes requiring immediate attention."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            critical_changes = await change_detection_service.get_critical_changes(
                hours=hours,
                source=source
            )
            
            return {
                "success": True,
                "data": {
                    "critical_changes": [
                        {
                            "event_id": str(change.event_id),
                            "entity_name": change.entity_name,
                            "entity_uid": change.entity_uid,
                            "source": change.source.value,
                            "change_type": change.change_type.value,
                            "change_summary": change.change_summary,
                            "field_changes": [
                                {
                                    "field": fc.field_name,
                                    "old_value": fc.old_value,
                                    "new_value": fc.new_value,
                                    "change_type": fc.change_type
                                }
                                for fc in change.field_changes
                            ],
                            "detected_at": change.detected_at.isoformat(),
                            "notification_sent": change.notification_sent_at.isoformat() if change.notification_sent_at else None
                        }
                        for change in critical_changes
                    ],
                    "count": len(critical_changes),
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
        raise HTTPException(status_code=500, detail="Internal server error")

# ======================== SCRAPING ENDPOINTS ========================

@router.post("/scraping/{source}/trigger")
async def trigger_scraping(
    request: Request,
    source: DataSource,
    force: bool = Query(False, description="Force scraping even if content unchanged"),
    timeout: int = Query(120, description="Timeout in seconds", ge=30, le=3600),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
):
    """
    Trigger scraping for a specific source.
    
    Uses service layer for business logic orchestration.
    """
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                f"Triggering scraping for {source.value}",
                extra={"source": source.value, "force": force, "timeout": timeout}
            )
            
            # Create scraping request
            scraping_request = ScrapingRequest(
                source=source,
                force_update=force,
                timeout_seconds=timeout,
                requested_by="api",  # Would extract from auth context
                request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))
            )
            
            # Execute scraping through service
            result = await scraping_service.execute_scraping_request(scraping_request)
            
            return {
                "success": True,
                "data": {
                    "scraping_result": {
                        "scraper_run_id": result["scraper_run_id"],
                        "source": result["source"],
                        "status": result["status"],
                        "duration_seconds": result["duration_seconds"],
                        "entities_processed": result.get("scraping_result", {}).get("entities_count", 0),
                        "content_changed": result.get("scraping_result", {}).get("content_changed", False)
                    },
                    "change_detection": {
                        "changes_detected": result.get("change_detection_result", {}).get("total_changes", 0) if result.get("change_detection_result") else 0,
                        "entities_added": result.get("change_detection_result", {}).get("entities_added", 0) if result.get("change_detection_result") else 0,
                        "entities_modified": result.get("change_detection_result", {}).get("entities_modified", 0) if result.get("change_detection_result") else 0,
                        "entities_removed": result.get("change_detection_result", {}).get("entities_removed", 0) if result.get("change_detection_result") else 0,
                        "critical_changes": result.get("change_detection_result", {}).get("has_critical_changes", False) if result.get("change_detection_result") else False
                    },
                    "notifications": {
                        "triggered": result.get("notifications_triggered", False)
                    }
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except ValidationError as e:
        logger.warning(f"Invalid scraping request: {e}")
        raise HTTPException(status_code=400, detail=create_error_response(e))
    except BusinessLogicError as e:
        logger.error(f"Scraping business logic error: {e}")
        raise HTTPException(status_code=422, detail=create_error_response(e))
    except Exception as e:
        logger.error(f"Error triggering scraping: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/scraping/status")
async def get_scraping_status(
    request: Request,
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    hours: int = Query(24, description="Hours to look back", ge=1, le=168),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
):
    """Get status of recent scraping operations."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
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
        raise HTTPException(status_code=500, detail="Internal server error")

# ======================== STATISTICS ENDPOINTS ========================

@router.get("/statistics")
async def get_statistics(
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_repo: ChangeEventRepository = Depends(get_change_event_repository),
    scraper_repo: ScraperRunRepository = Depends(get_scraper_run_repository)
):
    """Get comprehensive system statistics using repository pattern."""
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info("Getting system statistics")
            
            # Get statistics from each repository
            entity_stats = await entity_repo.get_statistics()
            
            # Get recent change summary
            since_24h = datetime.utcnow() - timedelta(hours=24)
            recent_changes = await change_repo.count_by_risk_level(since=since_24h)
            
            # Get scraping statistics
            scraping_stats = await scraper_repo.get_run_statistics(days=7)
            
            return {
                "success": True,
                "data": {
                    "entities": entity_stats,
                    "recent_changes": {
                        "last_24_hours": sum(recent_changes.values()),
                        "by_risk_level": {
                            risk_level.value: count 
                            for risk_level, count in recent_changes.items()
                        }
                    },
                    "scraping": scraping_stats,
                    "system": {
                        "features": [
                            "Repository pattern architecture",
                            "Domain-driven design",
                            "Unit of Work transactions",
                            "Dependency injection",
                            "Clean separation of concerns"
                        ]
                    }
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# ======================== COMPLEX BUSINESS OPERATIONS ========================

@router.post("/operations/bulk-update")
async def bulk_entity_update(
    request: Request,
    source: DataSource,
    force_update: bool = Query(False, description="Force update even without changes"),
    business_ops: UnitOfWorkBusinessOperations = Depends(get_business_operations)
):
    """
    Perform bulk entity update with change detection.
    
    Example of complex business operation using Unit of Work pattern.
    """
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                f"Starting bulk update for {source.value}",
                extra={"source": source.value, "force_update": force_update}
            )
            
            # This would get entities from scraper or external source
            entities_data = []  # Would be populated with real data
            scraper_run_id = f"bulk_{source.value}_{int(datetime.utcnow().timestamp())}"
            
            # Use business operations service for complex workflow
            result = await business_ops.bulk_entity_update(
                source=source,
                entities=entities_data,
                scraper_run_id=scraper_run_id
            )
            
            return {
                "success": True,
                "data": {
                    "operation": "bulk_entity_update",
                    "source": source.value,
                    "results": result,
                    "scraper_run_id": scraper_run_id
                },
                "metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "request_id": getattr(request.state, 'request_id', None)
                }
            }
            
    except Exception as e:
        logger.error(f"Error in bulk update: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# ======================== SYSTEM HEALTH WITH REPOSITORIES ========================

@router.get("/health/detailed")
async def detailed_health_check(
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
):
    """
    Detailed health check using repository pattern.
    
    Checks health of all system components through their interfaces.
    """
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            health_status = {
                "overall_healthy": True,
                "timestamp": datetime.utcnow().isoformat(),
                "request_id": getattr(request.state, 'request_id', None),
                "components": {}
            }
            
            # Check repository health
            try:
                repo_healthy = await entity_repo.health_check()
                health_status["components"]["entity_repository"] = {
                    "healthy": repo_healthy,
                    "type": "repository"
                }
                if not repo_healthy:
                    health_status["overall_healthy"] = False
            except Exception as e:
                health_status["components"]["entity_repository"] = {
                    "healthy": False,
                    "error": str(e),
                    "type": "repository"
                }
                health_status["overall_healthy"] = False
            
            # Check service health
            services = {
                "change_detection": change_detection_service,
                "scraping": scraping_service
            }
            
            for service_name, service in services.items():
                try:
                    service_health = await service.health_check()
                    health_status["components"][service_name] = {
                        **service_health,
                        "type": "service"
                    }
                    if not service_health.get("healthy", False):
                        health_status["overall_healthy"] = False
                except Exception as e:
                    health_status["components"][service_name] = {
                        "healthy": False,
                        "error": str(e),
                        "type": "service"
                    }
                    health_status["overall_healthy"] = False
            
            # Set HTTP status based on health
            status_code = 200 if health_status["overall_healthy"] else 503
            
            return health_status
            
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "overall_healthy": False,
            "timestamp": datetime.utcnow().isoformat(),
            "error": "Health check system failure",
            "components": {}
        }

# ======================== EXPORTS ========================

__all__ = ['router']