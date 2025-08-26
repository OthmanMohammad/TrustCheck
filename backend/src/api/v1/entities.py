"""
Entity API Endpoints
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Path, status
from fastapi.responses import JSONResponse

from src.services.entity_service import EntityService, SearchResult
from src.schemas.entity_schemas import (
    EntityCreate, EntityUpdate, EntityDetail, EntitySummary, EntitySearchFilters,
    EntityListResponse, EntitySearchResponse, BulkEntityCreate, BulkOperationResult
)
from src.schemas.api_responses import (
    APIResponse, ErrorResponse, PaginatedResponse
)
from src.core.enums import EntityType, SanctionsSource, SortOrder
from src.core.exceptions import (
    EntityNotFoundError, ValidationError, EntityAlreadyExistsError
)
from src.utils.logging import get_logger, LogContext
from src.main import get_entity_service  # Dependency injection

# ======================== ROUTER SETUP ========================

router = APIRouter(prefix="/entities")
logger = get_logger("api.entities")

# ======================== ENTITY CRUD ENDPOINTS ========================

@router.post(
    "/",
    response_model=APIResponse[EntityDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new sanctioned entity",
    description="Create a new sanctioned entity with full validation and change tracking."
)
async def create_entity(
    entity_data: EntityCreate,
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[EntityDetail]:
    """
    Create a new sanctioned entity.
    
    This endpoint:
    - Validates all input data using Pydantic schemas
    - Checks for duplicate entities
    - Creates domain entity with business rules
    - Stores in database via repository pattern
    - Returns structured response
    
    Args:
        entity_data: Entity creation data (validated by Pydantic)
        entity_service: Injected entity service
        
    Returns:
        APIResponse containing created entity details
        
    Raises:
        400: Validation error or entity already exists
        500: Internal server error
    """
    request_id = f"create_{datetime.utcnow().timestamp()}"
    
    with LogContext(logger, request_id=request_id):
        logger.info(
            f"Creating entity: {entity_data.name}",
            extra={
                "entity_type": entity_data.entity_type.value,
                "source": entity_data.source.value,
                "uid": entity_data.uid
            }
        )
        
        try:
            # Use service layer for business logic
            result = entity_service.create_entity(entity_data)
            
            if result.success:
                logger.info(
                    f"Entity created successfully: {result.entity.name}",
                    extra={
                        "entity_id": result.entity.entity_id,
                        "processing_time_ms": 0  # Would implement timing
                    }
                )
                
                return APIResponse(
                    success=True,
                    data=EntityDetail.from_orm(result.entity),
                    message=result.message,
                    timestamp=datetime.utcnow()
                )
            else:
                logger.warning(
                    f"Entity creation failed: {result.message}",
                    extra={"errors": result.errors}
                )
                
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "Entity creation failed",
                        "message": result.message,
                        "errors": result.errors
                    }
                )
                
        except EntityAlreadyExistsError as e:
            logger.warning(f"Entity already exists: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=e.to_dict()
            )
        except ValidationError as e:
            logger.warning(f"Validation failed: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.to_dict()
            )
        except Exception as e:
            logger.error(f"Unexpected error creating entity: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Internal server error", "message": str(e)}
            )


@router.get(
    "/{entity_id}",
    response_model=APIResponse[EntityDetail],
    summary="Get entity by ID",
    description="Retrieve a specific entity by its database ID."
)
async def get_entity(
    entity_id: int = Path(..., description="Entity database ID", gt=0),
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[EntityDetail]:
    """
    Get entity by ID with comprehensive error handling.
    
    Args:
        entity_id: Database ID of the entity
        entity_service: Injected entity service
        
    Returns:
        APIResponse containing entity details
        
    Raises:
        404: Entity not found
        500: Internal server error
    """
    with LogContext(logger, entity_id=entity_id):
        logger.info(f"Retrieving entity: {entity_id}")
        
        try:
            result = entity_service.get_entity_by_id(entity_id)
            
            if result.success:
                return APIResponse(
                    success=True,
                    data=EntityDetail.from_orm(result.entity),
                    message="Entity retrieved successfully"
                )
            else:
                logger.warning(f"Entity retrieval failed: {result.message}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error": "Entity not found", "entity_id": entity_id}
                )
                
        except EntityNotFoundError as e:
            logger.info(f"Entity not found: {entity_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=e.to_dict()
            )


@router.put(
    "/{entity_id}",
    response_model=APIResponse[EntityDetail],
    summary="Update entity",
    description="Update an existing entity with change tracking."
)
async def update_entity(
    entity_id: int = Path(..., description="Entity database ID", gt=0),
    update_data: EntityUpdate = ...,
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[EntityDetail]:
    """
    Update entity with automatic change detection.
    
    Args:
        entity_id: Database ID of the entity
        update_data: Updated entity data (partial update)
        entity_service: Injected entity service
        
    Returns:
        APIResponse containing updated entity
    """
    with LogContext(logger, entity_id=entity_id):
        logger.info(f"Updating entity: {entity_id}")
        
        try:
            result = entity_service.update_entity(entity_id, update_data)
            
            if result.success:
                logger.info(f"Entity updated successfully: {entity_id}")
                return APIResponse(
                    success=True,
                    data=EntityDetail.from_orm(result.entity),
                    message=result.message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Update failed", "message": result.message}
                )
                
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())
        except ValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.to_dict())


@router.delete(
    "/{entity_id}",
    response_model=APIResponse[Dict[str, Any]],
    summary="Delete entity",
    description="Delete an entity (soft delete by default)."
)
async def delete_entity(
    entity_id: int = Path(..., description="Entity database ID", gt=0),
    hard_delete: bool = Query(False, description="Perform hard delete instead of soft delete"),
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[Dict[str, Any]]:
    """
    Delete entity with soft/hard delete options.
    
    Args:
        entity_id: Database ID of the entity
        hard_delete: Whether to perform hard delete (default: soft delete)
        entity_service: Injected entity service
        
    Returns:
        APIResponse confirming deletion
    """
    with LogContext(logger, entity_id=entity_id):
        logger.info(f"Deleting entity: {entity_id} (hard={hard_delete})")
        
        try:
            result = entity_service.delete_entity(entity_id, soft_delete=not hard_delete)
            
            if result.success:
                return APIResponse(
                    success=True,
                    data={"entity_id": entity_id, "deleted": True, "hard_delete": hard_delete},
                    message=result.message
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error": "Delete failed", "message": result.message}
                )
                
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())


# ======================== SEARCH AND FILTERING ENDPOINTS ========================

@router.get(
    "/",
    response_model=EntityListResponse,
    summary="Search and list entities",
    description="Search entities with advanced filtering, pagination, and sorting."
)
async def search_entities(
    # Search filters
    name: Optional[str] = Query(None, description="Search by name (minimum 2 characters)"),
    entity_type: Optional[EntityType] = Query(None, description="Filter by entity type"),
    source: Optional[SanctionsSource] = Query(None, description="Filter by sanctions source"),
    programs: Optional[List[str]] = Query(None, description="Filter by sanctions programs"),
    nationalities: Optional[List[str]] = Query(None, description="Filter by nationalities"),
    is_active: bool = Query(True, description="Include only active entities"),
    
    # Pagination
    page: int = Query(1, description="Page number (1-based)", ge=1),
    page_size: int = Query(50, description="Items per page", ge=1, le=1000),
    
    # Sorting
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort order"),
    
    # Dependencies
    entity_service: EntityService = Depends(get_entity_service)
) -> EntityListResponse:
    """
    Advanced entity search with comprehensive filtering.
    
    This endpoint provides:
    - Text search across entity names
    - Filtering by type, source, programs, etc.
    - Pagination with configurable page sizes
    - Sorting by various fields
    - Performance optimization with caching
    
    Args:
        Various search and pagination parameters
        entity_service: Injected entity service
        
    Returns:
        Paginated list of entities with metadata
    """
    search_start = datetime.utcnow()
    
    # Build search filters from query parameters
    filters = EntitySearchFilters(
        name=name,
        entity_type=entity_type,
        source=source,
        programs=programs or [],
        nationalities=nationalities or [],
        is_active=is_active
    )
    
    with LogContext(logger, page=page, page_size=page_size):
        logger.info(
            "Searching entities",
            extra={
                "filters": filters.dict(exclude_unset=True),
                "sort_by": sort_by,
                "sort_order": sort_order.value
            }
        )
        
        try:
            # Execute search via service layer
            search_result: SearchResult = entity_service.search_entities(
                filters=filters,
                page=page,
                page_size=page_size,
                sort_by=sort_by,
                sort_order=sort_order
            )
            
            # Calculate pagination metadata
            total_pages = (search_result.total_count + page_size - 1) // page_size
            has_next = page < total_pages
            has_prev = page > 1
            
            logger.info(
                f"Search completed: {len(search_result.entities)} entities found",
                extra={
                    "total_count": search_result.total_count,
                    "search_time_ms": search_result.search_time_ms,
                    "page": page,
                    "total_pages": total_pages
                }
            )
            
            # Convert to API response format
            entity_summaries = [
                EntitySummary.from_orm(entity) 
                for entity in search_result.entities
            ]
            
            return EntityListResponse(
                entities=entity_summaries,
                filters_applied=filters,
                
                # Pagination metadata
                page=page,
                page_size=page_size,
                total_items=search_result.total_count,
                total_pages=total_pages,
                has_next_page=has_next,
                has_prev_page=has_prev,
                
                # Performance metadata
                search_time_ms=search_result.search_time_ms,
                suggestions=search_result.suggestions,
                timestamp=datetime.utcnow()
            )
            
        except ValidationError as e:
            logger.warning(f"Search validation failed: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.to_dict()
            )
        except Exception as e:
            search_time_ms = int((datetime.utcnow() - search_start).total_seconds() * 1000)
            logger.error(f"Search failed after {search_time_ms}ms: {e}", exc_info=True)
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Search failed",
                    "message": str(e),
                    "search_time_ms": search_time_ms
                }
            )


@router.get(
    "/{entity_id}/similar",
    response_model=APIResponse[List[EntitySummary]],
    summary="Find similar entities",
    description="Find entities similar to the specified entity using AI similarity scoring."
)
async def find_similar_entities(
    entity_id: int = Path(..., description="Reference entity ID", gt=0),
    threshold: float = Query(0.7, description="Similarity threshold", ge=0.0, le=1.0),
    limit: int = Query(10, description="Maximum results", ge=1, le=50),
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[List[EntitySummary]]:
    """
    Find entities similar to the reference entity.
    
    Uses advanced similarity algorithms to find potentially related entities
    based on names, aliases, addresses, and other attributes.
    
    Args:
        entity_id: Reference entity ID
        threshold: Similarity threshold (0.0 to 1.0)  
        limit: Maximum number of results
        entity_service: Injected entity service
        
    Returns:
        APIResponse with list of similar entities
    """
    with LogContext(logger, entity_id=entity_id, threshold=threshold):
        logger.info(f"Finding similar entities for: {entity_id}")
        
        try:
            result = entity_service.find_similar_entities(
                entity_id=entity_id,
                similarity_threshold=threshold,
                limit=limit
            )
            
            if result.success:
                similar_entities = [
                    EntitySummary.from_orm(entity)
                    for entity in result.entities or []
                ]
                
                return APIResponse(
                    success=True,
                    data=similar_entities,
                    message=f"Found {len(similar_entities)} similar entities",
                    metadata=result.metadata
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={"error": "Similarity search failed", "message": result.message}
                )
                
        except EntityNotFoundError as e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.to_dict())


# ======================== BULK OPERATIONS ========================

@router.post(
    "/bulk",
    response_model=APIResponse[BulkOperationResult], 
    status_code=status.HTTP_201_CREATED,
    summary="Bulk create entities",
    description="Create multiple entities in a single operation with detailed results."
)
async def bulk_create_entities(
    bulk_data: BulkEntityCreate,
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[BulkOperationResult]:
    """
    Bulk create multiple entities with comprehensive error reporting.
    
    This endpoint:
    - Validates all entities before processing
    - Creates entities in batches for performance
    - Provides detailed success/failure reporting
    - Handles partial failures gracefully
    
    Args:
        bulk_data: Bulk creation request with entities list
        entity_service: Injected entity service
        
    Returns:
        APIResponse with detailed operation results
    """
    with LogContext(logger, batch_size=len(bulk_data.entities)):
        logger.info(
            f"Starting bulk entity creation: {len(bulk_data.entities)} entities",
            extra={
                "source": bulk_data.source.value,
                "batch_id": bulk_data.batch_id
            }
        )
        
        try:
            # Execute bulk operation via service
            result = entity_service.bulk_create_entities(bulk_data.entities)
            
            logger.info(
                f"Bulk creation completed: {result.successful} successful, "
                f"{result.failed} failed, {result.skipped} skipped",
                extra={
                    "processing_time_ms": result.processing_time_ms,
                    "success_rate": result.success_rate,
                    "batch_id": bulk_data.batch_id
                }
            )
            
            # Determine response status based on results
            if result.failed == 0:
                status_code = status.HTTP_201_CREATED
                message = f"Successfully created {result.successful} entities"
            elif result.successful == 0:
                status_code = status.HTTP_400_BAD_REQUEST
                message = f"Failed to create any entities ({result.failed} failures)"
            else:
                status_code = status.HTTP_207_MULTI_STATUS
                message = f"Partial success: {result.successful} created, {result.failed} failed"
            
            response = APIResponse(
                success=result.successful > 0,
                data=result,
                message=message
            )
            
            return JSONResponse(
                status_code=status_code,
                content=response.dict()
            )
            
        except ValidationError as e:
            logger.warning(f"Bulk validation failed: {e.message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=e.to_dict()
            )
        except Exception as e:
            logger.error(f"Bulk creation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Bulk operation failed", "message": str(e)}
            )


# ======================== ANALYTICS ENDPOINTS ========================

@router.get(
    "/statistics",
    response_model=APIResponse[Dict[str, Any]],
    summary="Get entity statistics", 
    description="Get comprehensive statistics and analytics for entities."
)
async def get_entity_statistics(
    source: Optional[SanctionsSource] = Query(None, description="Filter by source"),
    entity_service: EntityService = Depends(get_entity_service)
) -> APIResponse[Dict[str, Any]]:
    """
    Get comprehensive entity statistics and analytics.
    
    Provides detailed metrics including:
    - Entity counts by type, source, program
    - Risk distribution analysis  
    - Recent activity trends
    - Data quality metrics
    
    Args:
        source: Optional source filter
        entity_service: Injected entity service
        
    Returns:
        APIResponse with statistics data
    """
    with LogContext(logger, source=source.value if source else "all"):
        logger.info(f"Generating entity statistics for: {source or 'all sources'}")
        
        try:
            stats = entity_service.get_entity_statistics(source=source)
            
            return APIResponse(
                success=True,
                data=stats,
                message=f"Statistics generated for {source.value if source else 'all sources'}"
            )
            
        except Exception as e:
            logger.error(f"Statistics generation failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "Statistics generation failed", "message": str(e)}
            )