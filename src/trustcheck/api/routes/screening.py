"""
TrustCheck Screening Routes.

API endpoints for name screening against sanctions lists.
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks

from trustcheck.api.schemas import (
    BatchScreeningRequest,
    BatchScreeningResponse,
    MatchedFieldSchema,
    ScreeningMatchSchema,
    ScreeningRequest,
    ScreeningResponse,
)
from trustcheck.domain import ScreeningRequest as DomainScreeningRequest
from trustcheck.services import get_screening_service

router = APIRouter(prefix="/api/screen", tags=["Screening"])


@router.post("", response_model=ScreeningResponse)
async def screen_name(request: ScreeningRequest) -> ScreeningResponse:
    """
    Screen a single name against sanctions lists.

    Returns all matches above the specified threshold, sorted by score.
    """
    service = get_screening_service()

    # Convert to domain request
    domain_request = DomainScreeningRequest(
        name=request.name,
        date_of_birth=request.date_of_birth,
        country=request.country,
        threshold=request.threshold,
        include_inactive=request.include_inactive,
        max_results=request.max_results,
    )

    # Perform screening
    result = await service.screen(domain_request)

    # Convert matches to schema
    matches = []
    for match in result.matches:
        matches.append(
            ScreeningMatchSchema(
                entity_id=str(match.entity.id),
                entity_name=match.entity.primary_name,
                entity_type=match.entity.entity_type.value,
                score=match.score,
                match_type=match.match_type.value,
                matched_fields=[
                    MatchedFieldSchema(
                        field_name=f.field_name,
                        query_value=f.query_value,
                        matched_value=f.matched_value,
                        score=f.score,
                        match_type=f.match_type.value,
                    )
                    for f in match.matched_fields
                ],
                sources=[s.value for s in match.sources],
                programs=match.entity.programs,
            )
        )

    return ScreeningResponse(
        success=True,
        request_id=str(result.request.request_id),
        query=request.name,
        matches=matches,
        screened_at=result.screened_at,
        processing_time_ms=result.processing_time_ms,
    )


@router.post("/batch", response_model=BatchScreeningResponse)
async def screen_batch(request: BatchScreeningRequest) -> BatchScreeningResponse:
    """
    Screen multiple names in batch.

    Returns matches for each name in the request.
    Limited to 10,000 names per request.
    """
    service = get_screening_service()

    # Perform batch screening
    results = await service.screen_batch(
        names=request.names,
        threshold=request.threshold,
        include_inactive=request.include_inactive,
    )

    # Convert results
    response_results = {}
    total_matches = 0

    for name, result in results.items():
        matches = []
        for match in result.matches:
            matches.append(
                ScreeningMatchSchema(
                    entity_id=str(match.entity.id),
                    entity_name=match.entity.primary_name,
                    entity_type=match.entity.entity_type.value,
                    score=match.score,
                    match_type=match.match_type.value,
                    matched_fields=[
                        MatchedFieldSchema(
                            field_name=f.field_name,
                            query_value=f.query_value,
                            matched_value=f.matched_value,
                            score=f.score,
                            match_type=f.match_type.value,
                        )
                        for f in match.matched_fields
                    ],
                    sources=[s.value for s in match.sources],
                    programs=match.entity.programs,
                )
            )
        response_results[name] = matches
        total_matches += len(matches)

    return BatchScreeningResponse(
        success=True,
        total_names=len(request.names),
        total_matches=total_matches,
        results=response_results,
    )
