"""
TrustCheck Screening Service.

Provides name screening against sanctions lists with fuzzy matching.
"""

import logging
import time
from datetime import datetime
from functools import lru_cache
from uuid import uuid4

from cachetools import TTLCache

from trustcheck.config import settings
from trustcheck.database import EntityRepository, get_session_context
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

# Cache for name data - refreshes every 5 minutes
_name_cache: TTLCache[str, list[tuple[str, str, str]]] = TTLCache(
    maxsize=1, ttl=settings.cache_ttl_seconds
)


class ScreeningService:
    """Service for screening names against sanctions lists."""

    def __init__(self) -> None:
        self.matcher = NameMatcher(default_threshold=settings.default_match_threshold)

    async def screen(self, request: ScreeningRequest) -> ScreeningResult:
        """
        Screen a single name against sanctions lists.

        Args:
            request: Screening request with name and options

        Returns:
            ScreeningResult with matches
        """
        start_time = time.time()

        # Get all names from cache or database
        all_names = await self._get_all_names(request.include_inactive)

        # Find matches
        matches = self.matcher.find_matches(
            query=request.name,
            candidates=all_names,
            threshold=request.threshold,
            max_results=request.max_results,
        )

        # Convert to ScreeningMatch objects
        screening_matches = []
        matched_entity_ids = set()

        for entity_id, matched_name, score in matches:
            # Skip duplicates (same entity matched via different names)
            if entity_id in matched_entity_ids:
                continue
            matched_entity_ids.add(entity_id)

            # Get full entity details
            entity = await self._get_entity(entity_id)
            if not entity:
                continue

            # Build match result
            # Note: matched_name is the specific name/alias that matched
            # entity.primary_name might be different if match was on an alias
            is_alias_match = matched_name.upper() != entity.primary_name.upper()

            match = ScreeningMatch(
                entity=entity,
                score=score.overall_score,
                match_type=score.match_type,
                matched_fields=[
                    MatchedField(
                        field_name="name" if not is_alias_match else "alias",
                        query_value=request.name,
                        matched_value=matched_name,
                        score=score.overall_score,
                        match_type=score.match_type,
                    )
                ],
                sources=self._get_entity_sources(entity),
            )

            # If matched on alias, add info about which alias matched
            if is_alias_match:
                match.matched_fields.append(
                    MatchedField(
                        field_name="primary_name",
                        query_value=request.name,
                        matched_value=entity.primary_name,
                        score=0.0,  # Not scored, just informational
                        match_type=MatchType.NONE,
                    )
                )

            # Apply secondary attribute boosts
            if request.date_of_birth and entity.date_of_birth:
                if str(request.date_of_birth) == str(entity.date_of_birth):
                    match.score = min(1.0, match.score + 0.10)
                    match.matched_fields.append(
                        MatchedField(
                            field_name="date_of_birth",
                            query_value=str(request.date_of_birth),
                            matched_value=str(entity.date_of_birth),
                            score=1.0,
                            match_type=MatchType.EXACT,
                        )
                    )

            if request.country and entity.nationality:
                if request.country.upper() == entity.nationality.upper():
                    match.score = min(1.0, match.score + 0.05)
                    match.matched_fields.append(
                        MatchedField(
                            field_name="nationality",
                            query_value=request.country,
                            matched_value=entity.nationality,
                            score=1.0,
                            match_type=MatchType.EXACT,
                        )
                    )

            screening_matches.append(match)

        # Sort by final score
        screening_matches.sort(key=lambda m: m.score, reverse=True)

        # Limit results
        screening_matches = screening_matches[: request.max_results]

        processing_time = (time.time() - start_time) * 1000

        return ScreeningResult(
            request=request,
            matches=screening_matches,
            screened_at=datetime.utcnow(),
            processing_time_ms=processing_time,
        )

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

        for name in names[: settings.batch_screening_limit]:
            request = ScreeningRequest(
                name=name,
                threshold=threshold or settings.default_match_threshold,
                include_inactive=include_inactive,
            )
            results[name] = await self.screen(request)

        return results

    async def _get_all_names(self, include_inactive: bool = False) -> list[tuple[str, str, str]]:
        """
        Get all entity names for matching.

        Returns cached data if available, otherwise loads from database.
        """
        cache_key = f"names_{include_inactive}"

        if cache_key in _name_cache:
            return _name_cache[cache_key]

        async with get_session_context() as session:
            entity_repo = EntityRepository(session)
            names = await entity_repo.get_all_normalized_names(active_only=not include_inactive)

        _name_cache[cache_key] = names
        logger.info(f"Loaded {len(names)} names into cache")

        return names

    async def _get_entity(self, entity_id: str) -> SanctionedEntity | None:
        """Get full entity details by ID."""
        async with get_session_context() as session:
            entity_repo = EntityRepository(session)
            return await entity_repo.get_by_id(entity_id)

    def _get_entity_sources(self, entity: SanctionedEntity) -> list[DataSource]:
        """Get list of sources for an entity (from programs)."""
        sources = []

        # Infer sources from programs
        for program in entity.programs:
            program_upper = program.upper()

            if any(p in program_upper for p in ["OFAC", "SDN", "SDGT", "IRAN", "SYRIA", "CUBA"]):
                if DataSource.OFAC_SDN not in sources:
                    sources.append(DataSource.OFAC_SDN)
            elif any(p in program_upper for p in ["UN", "ISIL", "QAIDA", "TALIBAN"]):
                if DataSource.UN not in sources:
                    sources.append(DataSource.UN)
            elif any(p in program_upper for p in ["EU", "EUROP"]):
                if DataSource.EU not in sources:
                    sources.append(DataSource.EU)
            elif any(p in program_upper for p in ["UK", "BRIT"]):
                if DataSource.UK not in sources:
                    sources.append(DataSource.UK)

        return sources if sources else [DataSource.OFAC_SDN]  # Default fallback

    def clear_cache(self) -> None:
        """Clear the name cache to force reload from database."""
        _name_cache.clear()
        logger.info("Screening cache cleared")


# Global service instance
_screening_service: ScreeningService | None = None


def get_screening_service() -> ScreeningService:
    """Get the global screening service instance."""
    global _screening_service
    if _screening_service is None:
        _screening_service = ScreeningService()
    return _screening_service
