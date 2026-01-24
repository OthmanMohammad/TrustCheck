"""
TrustCheck Changes Routes.

API endpoints for change monitoring and history.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from trustcheck.api.schemas import (
    ChangeEventSchema,
    ChangeListResponse,
    ChangeStatsResponse,
    ChangeStatsSchema,
    PaginationMeta,
)
from trustcheck.database import ChangeEventRepository, get_session_context
from trustcheck.domain import ChangeType, DataSource

router = APIRouter(prefix="/api/changes", tags=["Changes"])


@router.get("", response_model=ChangeListResponse)
async def list_changes(
    source: str | None = Query(None, description="Filter by source"),
    change_type: str | None = Query(None, description="Filter by change type (ADDED, MODIFIED, REMOVED)"),
    days: int = Query(7, ge=1, le=90, description="Number of days to look back"),
    limit: int = Query(100, ge=1, le=1000, description="Number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> ChangeListResponse:
    """
    List recent changes with filtering and pagination.
    """
    # Parse filters
    source_filter = None
    if source:
        try:
            source_filter = DataSource(source.upper())
        except ValueError:
            pass  # Invalid source, ignore filter

    type_filter = None
    if change_type:
        try:
            type_filter = ChangeType(change_type.upper())
        except ValueError:
            pass  # Invalid type, ignore filter

    async with get_session_context() as session:
        repo = ChangeEventRepository(session)
        changes, total = await repo.list_changes(
            source=source_filter,
            change_type=type_filter,
            days=days,
            limit=limit,
            offset=offset,
        )

    return ChangeListResponse(
        success=True,
        data=[
            ChangeEventSchema(
                id=str(c.id),
                entity_id=str(c.entity_id),
                entity_name=c.entity_name,
                source=c.source.value,
                change_type=c.change_type.value,
                field_changes=c.field_changes,
                detected_at=c.detected_at,
                scraper_run_id=str(c.scraper_run_id) if c.scraper_run_id else None,
            )
            for c in changes
        ],
        pagination=PaginationMeta(
            total=total,
            limit=limit,
            offset=offset,
            returned=len(changes),
        ),
    )


@router.get("/stats", response_model=ChangeStatsResponse)
async def get_change_stats() -> ChangeStatsResponse:
    """
    Get change statistics.
    """
    now = datetime.utcnow()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    async with get_session_context() as session:
        repo = ChangeEventRepository(session)

        changes_24h = await repo.count_since(day_ago)
        changes_7d = await repo.count_since(week_ago)

        # Get changes by source and type (simplified - would need additional repo methods)
        changes, _ = await repo.list_changes(days=7, limit=1000)

        by_source: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for change in changes:
            source = change.source.value
            by_source[source] = by_source.get(source, 0) + 1

            ctype = change.change_type.value
            by_type[ctype] = by_type.get(ctype, 0) + 1

    return ChangeStatsResponse(
        success=True,
        data=ChangeStatsSchema(
            changes_last_24h=changes_24h,
            changes_last_7d=changes_7d,
            changes_by_source=by_source,
            changes_by_type=by_type,
        ),
    )
