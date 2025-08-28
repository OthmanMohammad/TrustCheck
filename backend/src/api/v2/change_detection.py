"""
API v2 Endpoints with Full DTO Validation

Production-grade API with:
- Request/Response validation using Pydantic
- Type safety and automatic documentation
- Proper error handling and status codes
- Clean separation from domain layer
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid

# Core imports
from src.core.domain.entities import ScrapingRequest
from src.core.enums import DataSource, EntityType, ChangeType, RiskLevel
from src.core.exceptions import (
    TrustCheckError, ResourceNotFoundError, ValidationError,
    BusinessLogicError, create_error_response
)
from src.core.logging_config import get_logger, LoggingContext, log_performance

# Service layer
from src.services.change_detection.service import ChangeDetectionService
from src.services.scraping.service import ScrapingOrchestrationService
from src.services.notification.service import NotificationService

# API Dependencies
from src.api.dependencies import (
    get_sanctioned_entity_repository, get_change_event_repository,
    get_scraper_run_repository, get_change_detection_service,
    get_scraping_service, get_notification_service, get_unit_of_work
)

# Repository interfaces
from src.core.domain.repositories import (
    SanctionedEntityRepository, ChangeEventRepository, ScraperRunRepository
)
from src.core.uow import UnitOfWork

# API Schemas (DTOs)
from src.api.schemas.base import ErrorResponse, ErrorDetail
from src.api.schemas.entity import (
    EntityFilterRequest, EntitySearchRequest,
    EntitySummaryDTO, EntityDetailDTO, EntityListResponse, EntitySearchResponse,
    EntityResponse, EntityStatistics,
    entity_domain_to_dto, entity_domain_to_summary
)
from src.api.schemas.change_detection import (
    ChangeFilterRequest, ChangeSummaryRequest, CriticalChangesRequest,
    ChangeEventSummaryDTO, ChangeEventDetailDTO, ChangeSummaryDTO, ScraperRunResponse, 
    ChangeEventListResponse, CriticalChangesResponse, ChangeSummaryResponse,
    ScraperRunRequest, ScraperRunSummaryDTO, ScraperRunDetailDTO, BaseResponse,
    ScraperRunListResponse, ScrapingStatusDTO, ScrapingStatusResponse,
    change_event_domain_to_summary, change_event_domain_to_detail,
    scraper_run_domain_to_summary, scraper_run_domain_to_detail
)

logger = get_logger(__name__)

# Create router with v2 prefix
router = APIRouter(
    prefix="/api/v2",
    tags=["TrustCheck API v2 - With DTOs"]
)

# ======================== ENTITY ENDPOINTS ========================

@router.get(
    "/entities",
    response_model=EntityListResponse,
    summary="List sanctioned entities",
    description="Get paginated list of sanctioned entities with optional filters",
    responses={
        200: {"description": "Successful response with entity list"},
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def list_entities(
    request: Request,
    filters: EntityFilterRequest = Depends(),
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntityListResponse:
    """
    List sanctioned entities with filtering and pagination.
    
    Features:
    - Full input validation via Pydantic
    - Type-safe response
    - Automatic OpenAPI documentation
    """
    start_time = datetime.utcnow()
    
    try:
        with LoggingContext(request_id=getattr(request.state, 'request_id', str(uuid.uuid4()))):
            logger.info(
                "Listing entities with validated filters",
                extra={
                    "source": filters.source.value if filters.source else None,
                    "entity_type": filters.entity_type.value if filters.entity_type else None,
                    "limit": filters.limit,
                    "offset": filters.offset
                }
            )
            
            # Fetch entities based on filters
            entities = []
            
            if filters.source:
                entities = await entity_repo.find_by_source(
                    source=filters.source,
                    active_only=filters.active_only,
                    limit=filters.limit,
                    offset=filters.offset
                )
            elif filters.entity_type:
                entities = await entity_repo.find_by_entity_type(
                    entity_type=filters.entity_type,
                    limit=filters.limit,
                    offset=filters.offset
                )
            else:
                entities = await entity_repo.find_all(
                    active_only=filters.active_only,
                    limit=filters.limit,
                    offset=filters.offset
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
                    "limit": filters.limit,
                    "offset": filters.offset,
                    "total": stats.get('total_active', 0),
                    "returned": len(entity_dtos),
                    "has_more": len(entity_dtos) == filters.limit
                },
                filters=filters,
                statistics=statistics,
                metadata={
                    "timestamp": datetime.utcnow(),
                    "request_id": getattr(request.state, 'request_id', None),
                    "duration_ms": duration_ms
                }
            )
            
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message=str(e),
                    context={"filters": filters.model_dump()}
                )
            ).model_dump()
        )
    except Exception as e:
        logger.error(f"Error listing entities: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to list entities",
                    context={"error": str(e)}
                )
            ).model_dump()
        )

@router.get(
    "/entities/search",
    response_model=EntitySearchResponse,
    summary="Search entities",
    description="Search entities by name with optional fuzzy matching"
)
async def search_entities(
    request: Request,
    search: EntitySearchRequest = Depends(),
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntitySearchResponse:
    """Search entities with validated input."""
    try:
        entities = await entity_repo.search_by_name(
            name=search.query,
            fuzzy=search.fuzzy,
            limit=search.limit,
            offset=search.offset
        )
        
        # Convert to DTOs with relevance scores
        entity_dtos = []
        for entity in entities:
            dto = entity_domain_to_summary(entity)
            # Add mock relevance score (would be calculated in real implementation)
            dto_with_score = {**dto.model_dump(), "relevance_score": 0.95}
            entity_dtos.append(dto_with_score)
        
        return EntitySearchResponse(
            success=True,
            data=entity_dtos,
            query=search.query,
            fuzzy_matching=search.fuzzy,
            pagination={
                "limit": search.limit,
                "offset": search.offset,
                "total": None,  # Would need separate count query
                "returned": len(entity_dtos),
                "has_more": len(entity_dtos) == search.limit
            },
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
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
                    context={"query": search.query, "error": str(e)}
                )
            ).model_dump()
        )

@router.get(
    "/entities/{uid}",
    response_model=EntityResponse,
    summary="Get entity by UID",
    description="Get detailed information about a specific entity"
)
async def get_entity_by_uid(
    uid: str,
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository)
) -> EntityResponse:
    """Get entity details with proper DTO response."""
    try:
        entity = await entity_repo.get_by_uid(uid)
        
        if not entity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        code="ENTITY_NOT_FOUND",
                        message=f"Entity with UID '{uid}' not found",
                        field="uid"
                    )
                ).model_dump()
            )
        
        entity_dto = entity_domain_to_dto(entity)
        
        return EntityResponse(
            success=True,
            data=entity_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
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
                )
            ).model_dump()
        )

# ======================== CHANGE DETECTION ENDPOINTS ========================

@router.get(
    "/changes",
    response_model=ChangeEventListResponse,
    summary="List change events",
    description="Get paginated list of detected changes with filters"
)
async def list_changes(
    request: Request,
    filters: ChangeFilterRequest = Depends(),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
) -> ChangeEventListResponse:
    """List changes with full validation."""
    try:
        # Calculate date range
        if filters.start_date and filters.end_date:
            days = (filters.end_date - filters.start_date).days
        else:
            days = 7  # Default
        
        # Get change summary
        summary = await change_detection_service.get_change_summary(
            days=days,
            source=filters.source,
            risk_level=filters.risk_level
        )
        
        # Get actual changes (would need to be implemented in service)
        # For now, return empty list as placeholder
        changes = []
        
        # Convert to DTOs
        change_dtos = [change_event_domain_to_summary(change) for change in changes]
        
        # Create summary DTO
        summary_dto = ChangeSummaryDTO(
            period=summary.get('period', {}),
            filters=summary.get('filters', {}),
            totals=summary.get('totals', {}),
            by_type=summary.get('by_type', {}),
            by_risk_level=summary.get('by_risk_level', {})
        )
        
        return ChangeEventListResponse(
            success=True,
            data=change_dtos,
            pagination={
                "limit": filters.limit,
                "offset": filters.offset,
                "total": None,
                "returned": len(change_dtos),
                "has_more": len(change_dtos) == filters.limit
            },
            filters=filters,
            summary=summary_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
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
                )
            ).model_dump()
        )

@router.get(
    "/changes/critical",
    response_model=CriticalChangesResponse,
    summary="Get critical changes",
    description="Get critical changes requiring immediate attention"
)
async def get_critical_changes(
    request: Request,
    params: CriticalChangesRequest = Depends(),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
) -> CriticalChangesResponse:
    """Get critical changes with proper validation."""
    try:
        critical_changes = await change_detection_service.get_critical_changes(
            hours=params.hours,
            source=params.source
        )
        
        # Convert to DTOs
        change_dtos = [change_event_domain_to_detail(change) for change in critical_changes]
        
        return CriticalChangesResponse(
            success=True,
            data=change_dtos,
            count=len(change_dtos),
            period={
                "hours": params.hours,
                "since": (datetime.utcnow() - timedelta(hours=params.hours)).isoformat(),
                "until": datetime.utcnow().isoformat()
            },
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
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
                )
            ).model_dump()
        )

@router.get(
    "/changes/summary",
    response_model=ChangeSummaryResponse,
    summary="Get change summary",
    description="Get summary statistics of changes over time period"
)
async def get_change_summary(
    request: Request,
    params: ChangeSummaryRequest = Depends(),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
) -> ChangeSummaryResponse:
    """Get change summary with validation."""
    try:
        summary = await change_detection_service.get_change_summary(
            days=params.days,
            source=params.source,
            risk_level=params.risk_level
        )
        
        summary_dto = ChangeSummaryDTO(
            period=summary.get('period', {}),
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
                "request_id": getattr(request.state, 'request_id', None)
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
                )
            ).model_dump()
        )

# ======================== SCRAPER RUN ENDPOINTS ========================

@router.post(
    "/scraping/run",
    response_model=ScraperRunResponse,
    summary="Start scraper run",
    description="Manually trigger a scraper run for a data source",
    status_code=status.HTTP_202_ACCEPTED
)
async def start_scraper_run(
    request: Request,
    run_request: ScraperRunRequest = Body(...),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
) -> ScraperRunResponse:
    """Start a scraper run with validated input."""
    try:
        # Create scraping request
        scraping_request = ScrapingRequest(
            source=run_request.source,
            force_update=run_request.force_update,
            timeout_seconds=run_request.timeout_seconds
        )
        
        # Execute scraping
        result = await scraping_service.execute_scraping_request(scraping_request)
        
        # Create response DTO (simplified for example)
        run_dto = ScraperRunDetailDTO(
            run_id=result['scraper_run_id'],
            source=run_request.source,
            status="RUNNING",  # Would be from actual result
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
        
        return ScraperRunResponse(
            success=True,
            data=run_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
            }
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
                )
            ).model_dump()
        )

@router.get(
    "/scraping/status",
    response_model=ScrapingStatusResponse,
    summary="Get scraping status",
    description="Get status of scraping system and recent runs"
)
async def get_scraping_status(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look back"),
    source: Optional[DataSource] = Query(None, description="Filter by source"),
    scraping_service: ScrapingOrchestrationService = Depends(get_scraping_service)
) -> ScrapingStatusResponse:
    """Get scraping status with proper response model."""
    try:
        status = await scraping_service.get_scraping_status(
            source=source,
            hours=hours
        )
        
        # Convert recent runs to DTOs
        recent_run_dtos = [
            scraper_run_domain_to_summary(run) 
            for run in status.get('recent_runs', [])[:10]
        ]
        
        status_dto = ScrapingStatusDTO(
            period=status.get('period', {}),
            filter=status.get('filter', {}),
            metrics=status.get('metrics', {}),
            recent_runs=recent_run_dtos
        )
        
        return ScrapingStatusResponse(
            success=True,
            data=status_dto,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
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
                )
            ).model_dump()
        )

# ======================== HEALTH AND STATISTICS ========================

@router.get(
    "/statistics",
    response_model=BaseResponse[Dict[str, Any]],
    summary="Get system statistics",
    description="Get comprehensive system statistics"
)
async def get_statistics(
    request: Request,
    entity_repo: SanctionedEntityRepository = Depends(get_sanctioned_entity_repository),
    change_detection_service: ChangeDetectionService = Depends(get_change_detection_service)
) -> BaseResponse[Dict[str, Any]]:
    """Get system statistics with validated response."""
    try:
        # Get entity statistics
        entity_stats = await entity_repo.get_statistics()
        
        # Get change statistics
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
        
        return BaseResponse(
            success=True,
            data=stats,
            metadata={
                "timestamp": datetime.utcnow(),
                "request_id": getattr(request.state, 'request_id', None)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_ERROR",
                    message="Failed to get statistics",
                    context={"error": str(e)}
                )
            ).model_dump()
        )

# ======================== EXPORTS ========================

__all__ = ['router']