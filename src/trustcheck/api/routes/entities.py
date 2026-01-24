"""
TrustCheck Entity Routes.

API endpoints for entity management and retrieval.
"""

from fastapi import APIRouter, HTTPException, Query

from trustcheck.api.schemas import (
    AddressSchema,
    EntityDetail,
    EntityDetailResponse,
    EntityListResponse,
    EntitySummary,
    IdentifierSchema,
    NameSchema,
    PaginationMeta,
    SearchRequest,
    SearchResponse,
)
from trustcheck.database import EntityRepository, get_session_context
from trustcheck.domain import DataSource, EntityType, SanctionedEntity

router = APIRouter(prefix="/api/entities", tags=["Entities"])


def entity_to_summary(entity: SanctionedEntity) -> EntitySummary:
    """Convert domain entity to summary schema."""
    return EntitySummary(
        id=str(entity.id),
        primary_name=entity.primary_name,
        entity_type=entity.entity_type.value,
        is_active=entity.is_active,
        programs=entity.programs,
        sources=[],  # Would need to load from source_records
        updated_at=entity.updated_at,
    )


def entity_to_detail(entity: SanctionedEntity) -> EntityDetail:
    """Convert domain entity to detail schema."""
    return EntityDetail(
        id=str(entity.id),
        primary_name=entity.primary_name,
        primary_name_normalized=entity.primary_name_normalized,
        entity_type=entity.entity_type.value,
        names=[
            NameSchema(
                value=n.value,
                type=n.name_type.value,
                script=n.script.value,
            )
            for n in entity.names
        ],
        addresses=[
            AddressSchema(
                country=a.country,
                city=a.city,
                street=a.street,
                postal_code=a.postal_code,
                full_address=a.full_address,
            )
            for a in entity.addresses
        ],
        identifiers=[
            IdentifierSchema(
                type=i.id_type.value,
                value=i.value,
                country=i.country,
            )
            for i in entity.identifiers
        ],
        programs=entity.programs,
        date_of_birth=str(entity.date_of_birth) if entity.date_of_birth else None,
        year_of_birth=entity.year_of_birth,
        place_of_birth=entity.place_of_birth,
        nationality=entity.nationality,
        remarks=entity.remarks,
        is_active=entity.is_active,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get("", response_model=EntityListResponse)
async def list_entities(
    source: str | None = Query(None, description="Filter by source (OFAC_SDN, UN, EU, UK)"),
    entity_type: str | None = Query(None, description="Filter by type (INDIVIDUAL, ORGANIZATION, VESSEL, AIRCRAFT)"),
    active_only: bool = Query(True, description="Only return active entities"),
    limit: int = Query(50, ge=1, le=500, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> EntityListResponse:
    """
    List sanctioned entities with filtering and pagination.
    """
    # Parse source filter
    source_filter = None
    if source:
        try:
            source_filter = DataSource(source.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    # Parse entity type filter
    type_filter = None
    if entity_type:
        try:
            type_filter = EntityType(entity_type.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity_type: {entity_type}")

    async with get_session_context() as session:
        repo = EntityRepository(session)
        entities, total = await repo.list_entities(
            source=source_filter,
            entity_type=type_filter,
            active_only=active_only,
            limit=limit,
            offset=offset,
        )

    return EntityListResponse(
        success=True,
        data=[entity_to_summary(e) for e in entities],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            returned=len(entities),
        ),
    )


@router.get("/search", response_model=SearchResponse)
async def search_entities(
    query: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    active_only: bool = Query(True, description="Only search active entities"),
) -> SearchResponse:
    """
    Search entities by name.
    """
    async with get_session_context() as session:
        repo = EntityRepository(session)
        entities = await repo.search(query=query, limit=limit, active_only=active_only)

    return SearchResponse(
        success=True,
        query=query,
        data=[entity_to_summary(e) for e in entities],
    )


@router.get("/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(entity_id: str) -> EntityDetailResponse:
    """
    Get detailed information about a specific entity.
    """
    async with get_session_context() as session:
        repo = EntityRepository(session)
        entity = await repo.get_by_id(entity_id)

    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

    return EntityDetailResponse(
        success=True,
        data=entity_to_detail(entity),
    )


@router.get("/{entity_id}/history")
async def get_entity_history(entity_id: str) -> dict:
    """
    Get the change history for an entity.
    """
    from trustcheck.database import ChangeEventRepository

    async with get_session_context() as session:
        entity_repo = EntityRepository(session)
        entity = await entity_repo.get_by_id(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")

        change_repo = ChangeEventRepository(session)
        changes, _ = await change_repo.list_changes(days=365, limit=100)

        # Filter to this entity
        entity_changes = [c for c in changes if str(c.entity_id) == entity_id]

    return {
        "success": True,
        "entity_id": entity_id,
        "entity_name": entity.primary_name,
        "changes": [
            {
                "id": str(c.id),
                "change_type": c.change_type.value,
                "field_changes": c.field_changes,
                "detected_at": c.detected_at.isoformat(),
            }
            for c in entity_changes
        ],
    }
