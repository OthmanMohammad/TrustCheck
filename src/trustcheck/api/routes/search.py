"""
TrustCheck Advanced Search API Routes.

Endpoints for advanced search with filters and saved presets.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from trustcheck.database import get_session_context
from trustcheck.database.models import SearchPresetModel
from trustcheck.domain import DataSource, EntityType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["Advanced Search"])


# ==================== Request/Response Models ====================

class AdvancedSearchRequest(BaseModel):
    """Request for advanced entity search."""
    # Text search
    query: str | None = Field(None, description="Name search query")

    # Entity filters
    entity_types: list[str] | None = Field(None, description="Filter by entity types")
    sources: list[str] | None = Field(None, description="Filter by data sources")
    countries: list[str] | None = Field(None, description="Filter by nationality/country")
    programs: list[str] | None = Field(None, description="Filter by sanctions programs")

    # Field-specific search
    date_of_birth: str | None = Field(None, description="Filter by date of birth (YYYY-MM-DD or YYYY)")
    year_of_birth_min: int | None = Field(None, description="Minimum birth year")
    year_of_birth_max: int | None = Field(None, description="Maximum birth year")
    passport_number: str | None = Field(None, description="Search by passport number")
    national_id: str | None = Field(None, description="Search by national ID")

    # Date range filters
    added_after: str | None = Field(None, description="Added after date (ISO format)")
    added_before: str | None = Field(None, description="Added before date (ISO format)")
    updated_after: str | None = Field(None, description="Updated after date (ISO format)")
    updated_before: str | None = Field(None, description="Updated before date (ISO format)")

    # Other options
    active_only: bool = Field(True, description="Only return active entities")

    # Pagination
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class CreatePresetRequest(BaseModel):
    """Request to create a search preset."""
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    filters: AdvancedSearchRequest
    is_default: bool = False


class UpdatePresetRequest(BaseModel):
    """Request to update a search preset."""
    name: str | None = None
    description: str | None = None
    filters: AdvancedSearchRequest | None = None
    is_default: bool | None = None


# ==================== Search Endpoints ====================

@router.post("/advanced")
async def advanced_search(request: AdvancedSearchRequest) -> dict[str, Any]:
    """
    Perform advanced entity search with multiple filters.

    Supports filtering by:
    - Entity type (INDIVIDUAL, ORGANIZATION, VESSEL, AIRCRAFT)
    - Data source (OFAC_SDN, UN, EU, UK)
    - Country/nationality
    - Sanctions programs
    - Date of birth / year of birth range
    - Passport number
    - National ID
    - Date added/updated range
    """
    from datetime import datetime
    from sqlalchemy import and_, or_, select, func
    from sqlalchemy.orm import selectinload
    from trustcheck.database.models import EntityModel, SourceRecordModel, IdentifierModel

    async with get_session_context() as session:
        # Build base query
        stmt = select(EntityModel).options(
            selectinload(EntityModel.names),
            selectinload(EntityModel.addresses),
            selectinload(EntityModel.identifiers),
            selectinload(EntityModel.source_records),
        )

        conditions = []

        # Active only filter
        if request.active_only:
            conditions.append(EntityModel.is_active.is_(True))

        # Text search on name
        if request.query:
            normalized_query = f"%{request.query.upper()}%"
            conditions.append(EntityModel.primary_name_normalized.like(normalized_query))

        # Entity type filter
        if request.entity_types:
            valid_types = []
            for t in request.entity_types:
                try:
                    valid_types.append(EntityType(t.upper()).value)
                except ValueError:
                    pass
            if valid_types:
                conditions.append(EntityModel.entity_type.in_(valid_types))

        # Source filter - requires join
        if request.sources:
            valid_sources = []
            for s in request.sources:
                try:
                    valid_sources.append(DataSource(s.upper()).value)
                except ValueError:
                    pass
            if valid_sources:
                stmt = stmt.join(SourceRecordModel)
                conditions.append(SourceRecordModel.source.in_(valid_sources))
                conditions.append(SourceRecordModel.is_active.is_(True))

        # Country/nationality filter
        if request.countries:
            country_conditions = []
            for country in request.countries:
                country_conditions.append(
                    EntityModel.nationality.ilike(f"%{country}%")
                )
            if country_conditions:
                conditions.append(or_(*country_conditions))

        # Year of birth range
        if request.year_of_birth_min:
            conditions.append(EntityModel.year_of_birth >= request.year_of_birth_min)
        if request.year_of_birth_max:
            conditions.append(EntityModel.year_of_birth <= request.year_of_birth_max)

        # Date of birth exact match
        if request.date_of_birth:
            conditions.append(EntityModel.date_of_birth == request.date_of_birth)

        # Date added range
        if request.added_after:
            try:
                added_after_dt = datetime.fromisoformat(request.added_after)
                conditions.append(EntityModel.created_at >= added_after_dt)
            except ValueError:
                pass
        if request.added_before:
            try:
                added_before_dt = datetime.fromisoformat(request.added_before)
                conditions.append(EntityModel.created_at <= added_before_dt)
            except ValueError:
                pass

        # Date updated range
        if request.updated_after:
            try:
                updated_after_dt = datetime.fromisoformat(request.updated_after)
                conditions.append(EntityModel.updated_at >= updated_after_dt)
            except ValueError:
                pass
        if request.updated_before:
            try:
                updated_before_dt = datetime.fromisoformat(request.updated_before)
                conditions.append(EntityModel.updated_at <= updated_before_dt)
            except ValueError:
                pass

        # Apply all conditions
        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Count total before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await session.execute(count_stmt)).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(EntityModel.updated_at.desc()).offset(request.offset).limit(request.limit)

        result = await session.execute(stmt)
        models = result.scalars().unique().all()

        # Convert to response format
        entities = []
        for model in models:
            # Get sources from source records
            sources = []
            programs = []
            for sr in model.source_records:
                if sr.is_active:
                    sources.append(sr.source)
                    if sr.programs:
                        import json
                        try:
                            programs.extend(json.loads(sr.programs))
                        except json.JSONDecodeError:
                            pass

            entities.append({
                "id": model.id,
                "primary_name": model.primary_name,
                "entity_type": model.entity_type,
                "nationality": model.nationality,
                "date_of_birth": model.date_of_birth,
                "year_of_birth": model.year_of_birth,
                "is_active": model.is_active,
                "sources": list(set(sources)),
                "programs": list(set(programs)),
                "created_at": model.created_at.isoformat() if model.created_at else None,
                "updated_at": model.updated_at.isoformat() if model.updated_at else None,
            })

        # Handle identifier searches separately if needed
        if request.passport_number or request.national_id:
            # Additional filtering by identifiers
            identifier_matches = []
            for entity in entities:
                async with get_session_context() as id_session:
                    id_stmt = select(IdentifierModel).where(
                        IdentifierModel.entity_id == entity["id"]
                    )
                    id_result = await id_session.execute(id_stmt)
                    identifiers = id_result.scalars().all()

                    match = False
                    for ident in identifiers:
                        if request.passport_number and ident.id_type == "PASSPORT":
                            if request.passport_number.upper() in ident.id_value.upper():
                                match = True
                                break
                        if request.national_id and ident.id_type == "NATIONAL_ID":
                            if request.national_id.upper() in ident.id_value.upper():
                                match = True
                                break

                    if match or (not request.passport_number and not request.national_id):
                        identifier_matches.append(entity)

            entities = identifier_matches
            total = len(entities)

    return {
        "success": True,
        "data": entities,
        "pagination": {
            "total": total,
            "limit": request.limit,
            "offset": request.offset,
            "returned": len(entities),
        },
        "filters_applied": {
            "query": request.query,
            "entity_types": request.entity_types,
            "sources": request.sources,
            "countries": request.countries,
            "year_of_birth_range": [request.year_of_birth_min, request.year_of_birth_max],
        },
    }


@router.get("/filters")
async def get_available_filters() -> dict[str, Any]:
    """Get available filter options (entity types, sources, countries, programs)."""
    from sqlalchemy import select, func, distinct
    from trustcheck.database.models import EntityModel, SourceRecordModel

    async with get_session_context() as session:
        # Get distinct entity types
        type_stmt = select(distinct(EntityModel.entity_type)).where(EntityModel.is_active.is_(True))
        type_result = await session.execute(type_stmt)
        entity_types = [row[0] for row in type_result.all() if row[0]]

        # Get distinct sources
        source_stmt = select(distinct(SourceRecordModel.source)).where(SourceRecordModel.is_active.is_(True))
        source_result = await session.execute(source_stmt)
        sources = [row[0] for row in source_result.all() if row[0]]

        # Get distinct nationalities
        nat_stmt = select(distinct(EntityModel.nationality)).where(
            EntityModel.is_active.is_(True),
            EntityModel.nationality.isnot(None),
            EntityModel.nationality != "",
        )
        nat_result = await session.execute(nat_stmt)
        nationalities = sorted([row[0] for row in nat_result.all() if row[0]])[:100]  # Limit to 100

    return {
        "success": True,
        "data": {
            "entity_types": [
                {"value": "INDIVIDUAL", "label": "Individual"},
                {"value": "ORGANIZATION", "label": "Organization"},
                {"value": "VESSEL", "label": "Vessel"},
                {"value": "AIRCRAFT", "label": "Aircraft"},
            ],
            "sources": [
                {"value": "OFAC_SDN", "label": "OFAC SDN (US)"},
                {"value": "UN", "label": "UN Consolidated"},
                {"value": "EU", "label": "EU Sanctions"},
                {"value": "UK", "label": "UK FCDO"},
            ],
            "nationalities": nationalities,
            "active_sources": sources,
            "active_types": entity_types,
        },
    }


# ==================== Preset Endpoints ====================

@router.post("/presets")
async def create_preset(request: CreatePresetRequest) -> dict[str, Any]:
    """Create a new search preset."""
    import json
    from sqlalchemy import select

    async with get_session_context() as session:
        # Check if name already exists
        check_stmt = select(SearchPresetModel).where(SearchPresetModel.name == request.name)
        existing = (await session.execute(check_stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail="Preset with this name already exists")

        # If setting as default, unset other defaults
        if request.is_default:
            from sqlalchemy import update
            await session.execute(
                update(SearchPresetModel).values(is_default=False)
            )

        # Create preset
        preset = SearchPresetModel(
            name=request.name,
            description=request.description,
            filters=json.dumps(request.filters.model_dump()),
            is_default=request.is_default,
        )
        session.add(preset)
        await session.commit()

        return {
            "success": True,
            "preset_id": preset.id,
            "message": "Preset created",
        }


@router.get("/presets")
async def list_presets() -> dict[str, Any]:
    """List all saved search presets."""
    import json
    from sqlalchemy import select

    async with get_session_context() as session:
        stmt = select(SearchPresetModel).order_by(SearchPresetModel.name)
        result = await session.execute(stmt)
        presets = result.scalars().all()

        return {
            "success": True,
            "data": [
                {
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "filters": json.loads(p.filters) if p.filters else {},
                    "is_default": p.is_default,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                }
                for p in presets
            ],
        }


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str) -> dict[str, Any]:
    """Get a specific search preset."""
    import json
    from sqlalchemy import select

    async with get_session_context() as session:
        stmt = select(SearchPresetModel).where(SearchPresetModel.id == preset_id)
        preset = (await session.execute(stmt)).scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        return {
            "success": True,
            "data": {
                "id": preset.id,
                "name": preset.name,
                "description": preset.description,
                "filters": json.loads(preset.filters) if preset.filters else {},
                "is_default": preset.is_default,
                "created_at": preset.created_at.isoformat() if preset.created_at else None,
            },
        }


@router.put("/presets/{preset_id}")
async def update_preset(preset_id: str, request: UpdatePresetRequest) -> dict[str, Any]:
    """Update a search preset."""
    import json
    from sqlalchemy import select, update

    async with get_session_context() as session:
        stmt = select(SearchPresetModel).where(SearchPresetModel.id == preset_id)
        preset = (await session.execute(stmt)).scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        # Build update values
        values = {}
        if request.name is not None:
            values["name"] = request.name
        if request.description is not None:
            values["description"] = request.description
        if request.filters is not None:
            values["filters"] = json.dumps(request.filters.model_dump())
        if request.is_default is not None:
            # If setting as default, unset other defaults
            if request.is_default:
                await session.execute(
                    update(SearchPresetModel).values(is_default=False)
                )
            values["is_default"] = request.is_default

        if values:
            await session.execute(
                update(SearchPresetModel)
                .where(SearchPresetModel.id == preset_id)
                .values(**values)
            )
            await session.commit()

        return {
            "success": True,
            "message": "Preset updated",
        }


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str) -> dict[str, Any]:
    """Delete a search preset."""
    from sqlalchemy import select, delete

    async with get_session_context() as session:
        stmt = select(SearchPresetModel).where(SearchPresetModel.id == preset_id)
        preset = (await session.execute(stmt)).scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        await session.execute(
            delete(SearchPresetModel).where(SearchPresetModel.id == preset_id)
        )
        await session.commit()

        return {
            "success": True,
            "message": "Preset deleted",
        }


@router.post("/presets/{preset_id}/apply")
async def apply_preset(preset_id: str) -> dict[str, Any]:
    """Apply a preset and return search results."""
    import json
    from sqlalchemy import select

    async with get_session_context() as session:
        stmt = select(SearchPresetModel).where(SearchPresetModel.id == preset_id)
        preset = (await session.execute(stmt)).scalar_one_or_none()

        if not preset:
            raise HTTPException(status_code=404, detail="Preset not found")

        filters = json.loads(preset.filters) if preset.filters else {}

    # Execute the search with preset filters
    search_request = AdvancedSearchRequest(**filters)
    return await advanced_search(search_request)
