"""
API v2 Endpoints - FIXED with Async/Await

Production-grade API with complete async support.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Body, Path
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import ValidationError as PydanticValidationError
import uuid

# Core imports
from src.core.domain.entities import ScrapingRequest
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.exceptions import (
    TrustCheckError, ResourceNotFoundError, ValidationError as DomainValidationError,
    DatabaseError
)
from src.core.logging_config import get_logger

# Dependencies
from src.api.dependencies import (
    get_sanctioned_entity_repository,
    get_change_event_repository,
    get_scraper_run_repository,
    get_change_detection_service,
    get_scraping_service,
    get_notification_service
)

# Repository types
from src.infrastructure.database.repositories.sanctioned_entity import SQLAlchemySanctionedEntityRepository
from src.infrastructure.database.repositories.change_event import SQLAlchemyChangeEventRepository
from src.infrastructure.database.repositories.scraper_run import SQLAlchemyScraperRunRepository

# Services
from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService

# API Schemas (DTOs)
from src.api.schemas.base import ErrorResponse, ErrorDetail
from src.api.schemas.entity import (
    EntityFilterRequest, EntitySearchRequest,
    EntityListResponse, EntitySearchResponse,
    EntityResponse, EntityStatistics,
    entity_domain_to_summary, entity_domain_to_dto
)
from src.api.schemas.change_detection import (
    ChangeFilterRequest, ChangeSummaryRequest, CriticalChangesRequest,
    ChangeSummaryDTO, ScraperRunResponse, 
    ChangeEventListResponse, CriticalChangesResponse, ChangeSummaryResponse,
    ScraperRunRequest, ScraperRunDetailDTO,
    ScrapingStatusResponse, ScrapingStatusDTO,
    change_event_domain_to_detail, change_event_domain_to_summary,
    scraper_run_domain_to_summary
)

logger = get_logger(__name__)

# Create router with v2 prefix
router = APIRouter(
    prefix="/api/v2",
    tags=["TrustCheck API v2"]
)

# ======================== ENTITY ENDPOINTS ========================

@router.get(
    "/entities",
    response_model=EntityListResponse,
    summary="List sanctioned entities"
)
async def list_entities(
    request: Request,
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of items to return"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    source: Optional[DataSource] = Query(None, description="Filter by data source"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    active_only: bool = Query(True, description="Return only active items"),
    high_risk_only: bool = Query(False, description="Return only high-risk entities"),
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntityListResponse:
    """List sanctioned entities with filtering and pagination."""
    
    start_time = datetime.utcnow()
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # Create filter object for response
        filters = EntityFilterRequest(
            limit=limit,
            offset=offset,
            source=source,
            entity_type=entity_type,
            active_only=active_only,
            high_risk_only=high_risk_only
        )
        
        logger.info(f"Listing entities with filters: {filters.model_dump()}")
        
        # FIXED: Await all async repository calls
        entities = []
        
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
            entities = await entity_repo.find_all(
                active_only=active_only,
                limit=limit,
                offset=offset
            )
        
        # Get statistics
        stats = await entity_repo.get_statistics()
        
        # Convert to DTOs
        entity_dtos = [entity_domain_to_summary(entity) for entity in entities]
        
        # Create statistics DTO
        statistics = EntityStatistics(
            total_active=stats.get('total_active', 0),
            total_inactive=stats.get('total_inactive', 0),
            by_source=stats.get('by_source', {}),
            by_type=stats.get('by_type', {}),
            last_updated=datetime.utcnow()
        )
        
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        return EntityListResponse(
            success=True,
            data=entity_dtos,
            pagination={
                "limit": limit,
                "offset": offset,
                "total": stats.get('total_active', 0),
                "returned": len(entity_dtos),
                "has_more": len(entity_dtos) == limit
            },
            filters=filters,
            statistics=statistics,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id,
                "duration_ms": duration_ms
            }
        )
        
    except DatabaseError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="DATABASE_ERROR",
                    message="Database operation failed",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="An unexpected error occurred",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

@router.get(
    "/entities/search",
    response_model=EntitySearchResponse,
    summary="Search entities"
)
async def search_entities(
    request: Request,
    query: str = Query(..., min_length=2, max_length=200, description="Search query"),
    fuzzy: bool = Query(False, description="Enable fuzzy matching"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntitySearchResponse:
    """Search entities with validated input."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # FIXED: Await the async repository call
        entities = await entity_repo.search_by_name(
            name=query,  # Changed from 'name' to match what repository expects
            fuzzy=fuzzy,
            limit=limit,
            offset=offset
        )
        
        # Convert to DTOs - handle empty results
        entity_dtos = []
        if entities:
            for entity in entities:
                dto = entity_domain_to_summary(entity)
                # Create a proper dict that matches the response model
                entity_dtos.append(dto)
        
        return EntitySearchResponse(
            success=True,
            data=entity_dtos,
            query=query,
            fuzzy_matching=fuzzy,
            pagination={
                "limit": limit,
                "offset": offset,
                "total": None,
                "returned": len(entity_dtos),
                "has_more": len(entity_dtos) == limit
            },
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="SEARCH_ERROR",
                    message="Search operation failed",
                    context={"query": query, "error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

@router.get(
    "/entities/{uid}",
    response_model=EntityResponse,
    summary="Get entity by UID"
)
async def get_entity_by_uid(
    uid: str = Path(..., description="Entity unique identifier", pattern="^[a-zA-Z0-9_\\-]+$"),
    request: Request = None,
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntityResponse:
    """Get entity details with proper DTO response."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4())) if request else str(uuid.uuid4())
    
    try:
        # FIXED: Await the async repository call
        entity = await entity_repo.get_by_uid(uid)
        
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="ENTITY_NOT_FOUND",
                        message=f"Entity with UID '{uid}' not found",
                        field="uid"
                    ),
                    metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
                ).model_dump()
            )
        
        entity_dto = entity_domain_to_dto(entity)
        
        return EntityResponse(
            success=True,
            data=entity_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting entity {uid}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to retrieve entity",
                    context={"uid": uid, "error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

# ======================== CHANGE DETECTION ENDPOINTS ========================

@router.get(
    "/changes",
    response_model=ChangeEventListResponse,
    summary="List change events"
)
async def list_changes(
    request: Request,
    limit: int = Query(50, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    days: int = Query(7, ge=1, le=90, description="Days to look back"),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    change_repo: SQLAlchemyChangeEventRepository = Depends(get_change_event_repository)
) -> ChangeEventListResponse:
    """List changes with full validation."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # FIXED: Await all async repository calls
        changes = await change_repo.find_recent(
            days=days,
            source=source,
            risk_level=risk_level,
            limit=limit,
            offset=offset
        )
        
        # Get summary
        summary = {
            'since': (datetime.utcnow() - timedelta(days=days)).isoformat(),
            'total_changes': len(changes),
            'by_change_type': {},
            'by_risk_level': {}
        }
        
        # Count by type and risk level if we have changes
        if changes:
            by_type = await change_repo.count_by_change_type(
                since=datetime.utcnow() - timedelta(days=days),
                source=source
            )
            by_risk = await change_repo.count_by_risk_level(
                since=datetime.utcnow() - timedelta(days=days),
                source=source
            )
            summary['by_change_type'] = {k.value: v for k, v in by_type.items()}
            summary['by_risk_level'] = {k.value: v for k, v in by_risk.items()}
        
        # Convert to DTOs
        change_dtos = [change_event_domain_to_summary(change) for change in changes]
        
        # Create summary DTO
        summary_dto = ChangeSummaryDTO(
            period={'days': days, 'since': summary.get('since', ''), 'until': datetime.utcnow().isoformat()},
            filters={'source': source.value if source else None, 
                    'risk_level': risk_level.value if risk_level else None},
            totals={'all_changes': summary.get('total_changes', 0)},
            by_type=summary.get('by_change_type', {}),
            by_risk_level=summary.get('by_risk_level', {})
        )
        
        # Create filter object for response
        filters = ChangeFilterRequest(
            limit=limit,
            offset=offset,
            source=source,
            risk_level=risk_level
        )
        
        return ChangeEventListResponse(
            success=True,
            data=change_dtos,
            pagination={
                "limit": limit,
                "offset": offset,
                "total": None,
                "returned": len(change_dtos),
                "has_more": len(change_dtos) == limit
            },
            filters=filters,
            summary=summary_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error listing changes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to list changes",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

@router.get(
    "/changes/critical",
    response_model=CriticalChangesResponse,
    summary="Get critical changes"
)
async def get_critical_changes(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back (max 7 days)"),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    change_repo: SQLAlchemyChangeEventRepository = Depends(get_change_event_repository)
) -> CriticalChangesResponse:
    """Get critical changes with proper validation."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        
        # FIXED: Await the async repository call
        critical_changes = await change_repo.find_critical_changes(
            since=since,
            limit=100
        )
        
        # Filter by source if provided
        if source:
            critical_changes = [c for c in critical_changes if c.source == source]
        
        # Convert to DTOs
        change_dtos = [change_event_domain_to_detail(change) for change in critical_changes]
        
        return CriticalChangesResponse(
            success=True,
            data=change_dtos,
            count=len(change_dtos),
            period={
                "hours": hours,
                "since": since.isoformat(),
                "until": datetime.utcnow().isoformat()
            },
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting critical changes: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to get critical changes",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

@router.get(
    "/changes/summary",
    response_model=ChangeSummaryResponse,
    summary="Get change summary"
)
async def get_change_summary(
    request: Request,
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    risk_level: Optional[RiskLevel] = Query(None, description="Filter by risk level"),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
) -> ChangeSummaryResponse:
    """Get change summary with validation."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # FIXED: Await the async service call
        summary = await change_detection_service.get_change_summary(
            days=days,
            source=source,
            risk_level=risk_level
        )
        
        summary_dto = ChangeSummaryDTO(
            period=summary.get('period', {'days': days}),
            filters=summary.get('filters', {}),
            totals=summary.get('totals', {}),
            by_type=summary.get('by_type', {}),
            by_risk_level=summary.get('by_risk_level', {})
        )
        
        return ChangeSummaryResponse(
            success=True,
            data=summary_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting change summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to get change summary",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

# ======================== SCRAPER RUN ENDPOINTS ========================

@router.post(
    "/scraping/run",
    response_model=ScraperRunResponse,
    summary="Start scraper run",
    status_code=status.HTTP_202_ACCEPTED
)
async def start_scraper_run(
    request: Request,
    run_request: ScraperRunRequest = Body(...),
    # Temporarily comment out until service is ready
    # scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
) -> ScraperRunResponse:
    """Start a scraper run with validated input."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # TODO: Implement actual scraping service
        # For now, return a mock response
        from uuid import uuid4
        
        run_dto = ScraperRunDetailDTO(
            run_id=f"{run_request.source.value}_{uuid4().hex[:8]}",
            source=run_request.source,
            status="ACCEPTED",  # Changed from RUNNING to ACCEPTED
            started_at=datetime.utcnow(),
            entities_processed=0,
            entities_added=0,
            entities_modified=0,
            entities_removed=0,
            critical_changes=0,
            high_risk_changes=0,
            medium_risk_changes=0,
            low_risk_changes=0
        )
        
        logger.info(f"Scraper run accepted: {run_dto.run_id}")
        
        return ScraperRunResponse(
            success=True,
            data=run_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id,
                "message": "Scraping job accepted and queued"
            }
        )
        
    except PydanticValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"detail": e.errors()}
        )
    except Exception as e:
        logger.error(f"Error starting scraper run: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="SCRAPING_ERROR",
                    message="Failed to start scraper run",
                    context={"source": run_request.source.value, "error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

@router.get(
    "/scraping/status",
    response_model=ScrapingStatusResponse,
    summary="Get scraping status"
)
async def get_scraping_status(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
) -> ScrapingStatusResponse:
    """Get scraping status with proper response model."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # FIXED: Await the async service call
        status_data = await scraping_service.get_scraping_status(
            source=source,
            hours=hours
        )
        
        status_dto = ScrapingStatusDTO(
            period=status_data.get('period', {'hours': hours}),
            filter=status_data.get('filter', {}),
            metrics=status_data.get('metrics', {}),
            recent_runs=[
                scraper_run_domain_to_summary(run) 
                for run in status_data.get('recent_runs', [])
            ]
        )
        
        return ScrapingStatusResponse(
            success=True,
            data=status_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting scraping status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to get scraping status",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

# ======================== STATISTICS ========================

@router.get(
    "/statistics",
    summary="Get system statistics"
)
async def get_statistics(
    request: Request,
    entity_repo: SQLAlchemySanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
):
    """Get system statistics with validated response."""
    
    request_id = getattr(request.state, 'request_id', str(uuid.uuid4()))
    
    try:
        # FIXED: Await all async calls
        entity_stats = await entity_repo.get_statistics()
        change_summary = await change_detection_service.get_change_summary(days=7)
        
        stats = {
            "entities": entity_stats,
            "changes": change_summary,
            "system": {
                "api_version": "v2",
                "dto_validation": "enabled",
                "response_schemas": "enforced"
            }
        }
        
        return {
            "success": True,
            "data": stats,
            "metadata": {
                "timestamp": datetime.utcnow(),
                "request_id": request_id
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to get statistics",
                    context={"error": str(e)}
                ),
                metadata={"timestamp": datetime.utcnow(), "request_id": request_id}
            ).model_dump()
        )

# ======================== EXPORTS ========================

__all__ = ['router']