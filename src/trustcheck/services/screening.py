"""
TrustCheck Screening Service.

Enterprise-grade name screening against sanctions lists.
Uses PostgreSQL pg_trgm for efficient fuzzy matching at database level.
"""

import json
import logging
import time
from datetime import datetime
from uuid import uuid4

from trustcheck.config import settings
from trustcheck.database import get_session_context
from trustcheck.database.search import DatabaseSearch, SearchCandidate
from trustcheck.domain import (
    DataSource,
    MatchedField,
    MatchType,
    SanctionedEntity,
    ScreeningMatch,
    ScreeningRequest,
    ScreeningResult,
)
from trustcheck.matching import MatchScore, NameMatcher, normalize_name

logger = logging.getLogger(__name__)


class ScreeningService:
    """
    Enterprise screening service.

    Uses database-level trigram search for candidate generation,
    then applies detailed scoring on top candidates.
    """

    def __init__(self) -> None:
        self.matcher = NameMatcher(default_threshold=settings.default_match_threshold)

    async def screen(self, request: ScreeningRequest) -> ScreeningResult:
        """
        Screen a single name against sanctions lists.

        Two-stage approach:
        1. Database-level trigram search for candidate generation
        2. Detailed scoring on candidates using multiple algorithms

        Args:
            request: Screening request with name and options

        Returns:
            ScreeningResult with matches
        """
        start_time = time.time()

        # Stage 1: Database-level candidate generation
        async with get_session_context() as session:
            db_search = DatabaseSearch(session)

            # Get candidates using trigram similarity
            candidates = await db_search.search_names(
                query=request.name,
                threshold=settings.trigram_similarity_threshold,
                limit=settings.max_screening_results * 2,  # Get extra for filtering
                active_only=not request.include_inactive,
                entity_types=request.entity_types if hasattr(request, 'entity_types') else None,
                sources=request.sources if hasattr(request, 'sources') else None,
            )

        # Stage 2: Detailed scoring on candidates
        screening_matches = await self._score_candidates(request, candidates)

        # Apply threshold filter
        threshold = request.threshold or settings.default_match_threshold
        screening_matches = [m for m in screening_matches if m.score >= threshold]

        # Sort by score and limit
        screening_matches.sort(key=lambda m: m.score, reverse=True)
        screening_matches = screening_matches[:request.max_results]

        processing_time = (time.time() - start_time) * 1000

        return ScreeningResult(
            request=request,
            matches=screening_matches,
            screened_at=datetime.utcnow(),
            processing_time_ms=processing_time,
        )

    async def _score_candidates(
        self,
        request: ScreeningRequest,
        candidates: list[SearchCandidate],
    ) -> list[ScreeningMatch]:
        """
        Apply detailed scoring to database candidates.

        Uses multiple algorithms: fuzzy matching, phonetic, n-gram, etc.
        """
        matches: list[ScreeningMatch] = []
        seen_entities: set[str] = set()

        for candidate in candidates:
            # Skip duplicate entities (matched via different names)
            if candidate.entity_id in seen_entities:
                continue
            seen_entities.add(candidate.entity_id)

            # Calculate detailed score
            score = self.matcher.score(request.name, candidate.name_value)

            # Determine if this was an alias match
            is_alias_match = candidate.name_value.upper() != candidate.primary_name.upper()

            # Build matched fields
            matched_fields = [
                MatchedField(
                    field_name="alias" if is_alias_match else "name",
                    query_value=request.name,
                    matched_value=candidate.name_value,
                    score=score.overall_score,
                    match_type=score.match_type,
                )
            ]

            # If matched on alias, add primary name info
            if is_alias_match:
                matched_fields.append(
                    MatchedField(
                        field_name="primary_name",
                        query_value=request.name,
                        matched_value=candidate.primary_name,
                        score=0.0,
                        match_type=MatchType.NONE,
                    )
                )

            # Get sources for this entity
            sources = await self._get_entity_sources(candidate.entity_id)

            # Create entity object
            entity = SanctionedEntity(
                id=candidate.entity_id,
                primary_name=candidate.primary_name,
                entity_type=candidate.entity_type,
                nationality=candidate.nationality,
                date_of_birth=candidate.date_of_birth,
            )

            # Build screening match
            match = ScreeningMatch(
                entity=entity,
                score=score.overall_score,
                match_type=score.match_type,
                matched_fields=matched_fields,
                sources=sources,
            )

            # Apply secondary attribute boosts
            match = self._apply_attribute_boosts(request, match, candidate)

            matches.append(match)

        return matches

    def _apply_attribute_boosts(
        self,
        request: ScreeningRequest,
        match: ScreeningMatch,
        candidate: SearchCandidate,
    ) -> ScreeningMatch:
        """Apply score boosts for matching secondary attributes."""
        # Date of birth boost
        if request.date_of_birth and candidate.date_of_birth:
            if str(request.date_of_birth) == str(candidate.date_of_birth):
                match.score = min(1.0, match.score + 0.10)
                match.matched_fields.append(
                    MatchedField(
                        field_name="date_of_birth",
                        query_value=str(request.date_of_birth),
                        matched_value=str(candidate.date_of_birth),
                        score=1.0,
                        match_type=MatchType.EXACT,
                    )
                )

        # Country/nationality boost
        if request.country and candidate.nationality:
            if request.country.upper() == candidate.nationality.upper():
                match.score = min(1.0, match.score + 0.05)
                match.matched_fields.append(
                    MatchedField(
                        field_name="nationality",
                        query_value=request.country,
                        matched_value=candidate.nationality,
                        score=1.0,
                        match_type=MatchType.EXACT,
                    )
                )

        return match

    async def _get_entity_sources(self, entity_id: str) -> list[DataSource]:
        """Get data sources for an entity."""
        async with get_session_context() as session:
            from sqlalchemy import text
            result = await session.execute(
                text("""
                    SELECT DISTINCT source FROM source_records
                    WHERE entity_id = :entity_id AND is_active = true
                """) if settings.is_postgresql else
                text("""
                    SELECT DISTINCT source FROM source_records
                    WHERE entity_id = :entity_id AND is_active = 1
                """),
                {"entity_id": entity_id}
            )
            rows = result.fetchall()

        sources = []
        for row in rows:
            try:
                sources.append(DataSource(row[0]))
            except ValueError:
                pass

        return sources if sources else [DataSource.OFAC_SDN]

    async def screen_name(
        self,
        name: str,
        date_of_birth: str | None = None,
        country: str | None = None,
        threshold: float | None = None,
        max_results: int = 10,
    ) -> list[ScreeningMatch]:
        """
        Convenience method for simple name screening.

        Args:
            name: Name to screen
            date_of_birth: Optional DOB for boost
            country: Optional country for boost
            threshold: Minimum match score
            max_results: Maximum results

        Returns:
            List of ScreeningMatch objects
        """
        request = ScreeningRequest(
            name=name,
            date_of_birth=date_of_birth,
            country=country,
            threshold=threshold or settings.default_match_threshold,
            max_results=max_results,
        )

        result = await self.screen(request)
        return result.matches

    async def screen_batch(
        self,
        names: list[str],
        threshold: float | None = None,
        include_inactive: bool = False,
    ) -> dict[str, ScreeningResult]:
        """
        Screen multiple names in batch.

        Args:
            names: List of names to screen
            threshold: Minimum match score
            include_inactive: Whether to include inactive entities

        Returns:
            Dictionary mapping name to ScreeningResult
        """
        results = {}

        for name in names[:settings.batch_screening_limit]:
            request = ScreeningRequest(
                name=name,
                threshold=threshold or settings.default_match_threshold,
                include_inactive=include_inactive,
            )
            results[name] = await self.screen(request)

        return results

    async def get_entity_details(self, entity_id: str) -> dict | None:
        """
        Get full details for an entity.

        Returns all names, addresses, identifiers, sources.
        """
        async with get_session_context() as session:
            db_search = DatabaseSearch(session)
            return await db_search.get_entity_with_details(entity_id)

    async def search_by_identifier(
        self,
        id_type: str,
        id_value: str,
    ) -> list[dict]:
        """
        Search for entities by identifier.

        Args:
            id_type: Type of identifier (PASSPORT, NATIONAL_ID, etc.)
            id_value: The identifier value

        Returns:
            List of matching entity details
        """
        async with get_session_context() as session:
            db_search = DatabaseSearch(session)
            return await db_search.search_by_identifier(id_type, id_value)


# Global service instance
_screening_service: ScreeningService | None = None


def get_screening_service() -> ScreeningService:
    """Get the global screening service instance."""
    global _screening_service
    if _screening_service is None:
        _screening_service = ScreeningService()
    return _screening_service


def clear_screening_service() -> None:
    """Clear the global screening service (for testing)."""
    global _screening_service
    _screening_service = None
