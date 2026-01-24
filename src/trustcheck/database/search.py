"""
TrustCheck Database Search.

PostgreSQL-native fuzzy search using pg_trgm extension.
Provides efficient trigram similarity search at the database level.
"""

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from trustcheck.config import settings
from trustcheck.matching import normalize_name

logger = logging.getLogger(__name__)


@dataclass
class SearchCandidate:
    """A candidate match from database search."""
    entity_id: str
    name_id: str
    name_value: str
    name_normalized: str
    name_type: str
    primary_name: str
    entity_type: str
    nationality: str | None
    date_of_birth: str | None
    similarity: float
    is_primary: bool


class DatabaseSearch:
    """
    PostgreSQL-native search using pg_trgm.

    Uses trigram similarity for efficient fuzzy matching at the database level.
    Falls back to basic LIKE search for SQLite.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_names(
        self,
        query: str,
        threshold: float | None = None,
        limit: int = 100,
        active_only: bool = True,
        entity_types: list[str] | None = None,
        sources: list[str] | None = None,
    ) -> list[SearchCandidate]:
        """
        Search for matching names using database-level fuzzy search.

        For PostgreSQL: Uses pg_trgm similarity() function
        For SQLite: Falls back to normalized LIKE search

        Args:
            query: The name to search for
            threshold: Minimum similarity score (0.0-1.0)
            limit: Maximum results to return
            active_only: Only search active entities
            entity_types: Filter by entity types
            sources: Filter by data sources

        Returns:
            List of SearchCandidate objects sorted by similarity
        """
        threshold = threshold or settings.trigram_similarity_threshold
        query_normalized = normalize_name(query)

        if not query_normalized:
            return []

        if settings.is_postgresql:
            return await self._search_postgresql(
                query_normalized, threshold, limit, active_only, entity_types, sources
            )
        else:
            return await self._search_sqlite(
                query_normalized, threshold, limit, active_only, entity_types, sources
            )

    async def _search_postgresql(
        self,
        query_normalized: str,
        threshold: float,
        limit: int,
        active_only: bool,
        entity_types: list[str] | None,
        sources: list[str] | None,
    ) -> list[SearchCandidate]:
        """PostgreSQL search using pg_trgm similarity."""
        # Build the query with trigram similarity
        sql = """
            SELECT
                n.entity_id,
                n.id as name_id,
                n.name_value,
                n.name_normalized,
                n.name_type,
                e.primary_name,
                e.entity_type,
                e.nationality,
                e.date_of_birth,
                similarity(n.name_normalized, :query) as sim,
                (n.name_type = 'PRIMARY') as is_primary
            FROM names n
            JOIN entities e ON n.entity_id = e.id
            WHERE similarity(n.name_normalized, :query) >= :threshold
        """

        params: dict[str, Any] = {
            "query": query_normalized,
            "threshold": threshold,
        }

        if active_only:
            sql += " AND e.is_active = true"

        if entity_types:
            sql += " AND e.entity_type = ANY(:entity_types)"
            params["entity_types"] = entity_types

        if sources:
            sql += """
                AND EXISTS (
                    SELECT 1 FROM source_records sr
                    WHERE sr.entity_id = e.id
                    AND sr.source = ANY(:sources)
                    AND sr.is_active = true
                )
            """
            params["sources"] = sources

        # Order by similarity descending, prefer primary names
        sql += """
            ORDER BY sim DESC, is_primary DESC
            LIMIT :limit
        """
        params["limit"] = limit

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        return [
            SearchCandidate(
                entity_id=row[0],
                name_id=row[1],
                name_value=row[2],
                name_normalized=row[3],
                name_type=row[4],
                primary_name=row[5],
                entity_type=row[6],
                nationality=row[7],
                date_of_birth=row[8],
                similarity=float(row[9]),
                is_primary=bool(row[10]),
            )
            for row in rows
        ]

    async def _search_sqlite(
        self,
        query_normalized: str,
        threshold: float,
        limit: int,
        active_only: bool,
        entity_types: list[str] | None,
        sources: list[str] | None,
    ) -> list[SearchCandidate]:
        """SQLite fallback search using LIKE and basic similarity."""
        # SQLite doesn't have pg_trgm, so we use a simpler approach:
        # 1. Find candidates using LIKE with wildcards
        # 2. Calculate similarity in Python

        # Create search patterns
        # For "JOHN SMITH", search for "%JOHN%" OR "%SMITH%"
        tokens = query_normalized.split()
        if not tokens:
            return []

        sql = """
            SELECT
                n.entity_id,
                n.id as name_id,
                n.name_value,
                n.name_normalized,
                n.name_type,
                e.primary_name,
                e.entity_type,
                e.nationality,
                e.date_of_birth,
                (n.name_type = 'PRIMARY') as is_primary
            FROM names n
            JOIN entities e ON n.entity_id = e.id
            WHERE (
        """

        params: dict[str, Any] = {}
        like_conditions = []
        for i, token in enumerate(tokens[:5]):  # Limit to first 5 tokens
            param_name = f"token_{i}"
            like_conditions.append(f"n.name_normalized LIKE :{param_name}")
            params[param_name] = f"%{token}%"

        sql += " OR ".join(like_conditions)
        sql += ")"

        if active_only:
            sql += " AND e.is_active = 1"

        if entity_types:
            placeholders = ",".join(f":et_{i}" for i in range(len(entity_types)))
            sql += f" AND e.entity_type IN ({placeholders})"
            for i, et in enumerate(entity_types):
                params[f"et_{i}"] = et

        if sources:
            placeholders = ",".join(f":src_{i}" for i in range(len(sources)))
            sql += f"""
                AND EXISTS (
                    SELECT 1 FROM source_records sr
                    WHERE sr.entity_id = e.id
                    AND sr.source IN ({placeholders})
                    AND sr.is_active = 1
                )
            """
            for i, src in enumerate(sources):
                params[f"src_{i}"] = src

        sql += " LIMIT :limit"
        params["limit"] = limit * 3  # Get more candidates, filter in Python

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        # Calculate similarity in Python
        candidates = []
        for row in rows:
            name_normalized = row[3]
            similarity = self._calculate_similarity(query_normalized, name_normalized)

            if similarity >= threshold:
                candidates.append(
                    SearchCandidate(
                        entity_id=row[0],
                        name_id=row[1],
                        name_value=row[2],
                        name_normalized=name_normalized,
                        name_type=row[4],
                        primary_name=row[5],
                        entity_type=row[6],
                        nationality=row[7],
                        date_of_birth=row[8],
                        similarity=similarity,
                        is_primary=bool(row[9]),
                    )
                )

        # Sort by similarity and limit
        candidates.sort(key=lambda x: (-x.similarity, -x.is_primary))
        return candidates[:limit]

    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate trigram similarity between two strings (Python fallback)."""
        if not s1 or not s2:
            return 0.0

        # Generate trigrams
        def trigrams(s: str) -> set[str]:
            s = f"  {s} "  # Pad with spaces like pg_trgm
            return {s[i:i+3] for i in range(len(s) - 2)}

        t1 = trigrams(s1.upper())
        t2 = trigrams(s2.upper())

        if not t1 or not t2:
            return 0.0

        intersection = len(t1 & t2)
        union = len(t1 | t2)

        return intersection / union if union > 0 else 0.0

    async def search_by_identifier(
        self,
        id_type: str,
        id_value: str,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Search for entities by identifier (passport, national ID, etc.).

        Args:
            id_type: Type of identifier (PASSPORT, NATIONAL_ID, etc.)
            id_value: The identifier value to search for
            active_only: Only search active entities

        Returns:
            List of matching entities with their identifiers
        """
        sql = """
            SELECT
                e.id as entity_id,
                e.primary_name,
                e.entity_type,
                e.nationality,
                i.id_type,
                i.id_value,
                i.issuing_country
            FROM identifiers i
            JOIN entities e ON i.entity_id = e.id
            WHERE UPPER(i.id_type) = UPPER(:id_type)
            AND UPPER(i.id_value) LIKE UPPER(:id_value)
        """

        params: dict[str, Any] = {
            "id_type": id_type,
            "id_value": f"%{id_value}%",
        }

        if active_only:
            active_check = "e.is_active = true" if settings.is_postgresql else "e.is_active = 1"
            sql += f" AND {active_check}"

        sql += " LIMIT 100"

        result = await self.session.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "entity_id": row[0],
                "primary_name": row[1],
                "entity_type": row[2],
                "nationality": row[3],
                "id_type": row[4],
                "id_value": row[5],
                "issuing_country": row[6],
            }
            for row in rows
        ]

    async def get_entity_with_details(self, entity_id: str) -> dict[str, Any] | None:
        """
        Get full entity details including all names, addresses, identifiers.

        This is optimized for PostgreSQL with a single query using JSON aggregation.
        """
        if settings.is_postgresql:
            return await self._get_entity_postgresql(entity_id)
        else:
            return await self._get_entity_sqlite(entity_id)

    async def _get_entity_postgresql(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity with PostgreSQL JSON aggregation."""
        sql = """
            SELECT
                e.id,
                e.primary_name,
                e.entity_type,
                e.nationality,
                e.date_of_birth,
                e.year_of_birth,
                e.place_of_birth,
                e.is_active,
                e.created_at,
                e.updated_at,
                COALESCE(
                    json_agg(DISTINCT jsonb_build_object(
                        'name_value', n.name_value,
                        'name_type', n.name_type
                    )) FILTER (WHERE n.id IS NOT NULL),
                    '[]'
                ) as names,
                COALESCE(
                    json_agg(DISTINCT jsonb_build_object(
                        'source', sr.source,
                        'source_uid', sr.source_uid,
                        'programs', sr.programs
                    )) FILTER (WHERE sr.id IS NOT NULL AND sr.is_active = true),
                    '[]'
                ) as sources,
                COALESCE(
                    json_agg(DISTINCT jsonb_build_object(
                        'id_type', i.id_type,
                        'id_value', i.id_value,
                        'issuing_country', i.issuing_country
                    )) FILTER (WHERE i.id IS NOT NULL),
                    '[]'
                ) as identifiers
            FROM entities e
            LEFT JOIN names n ON n.entity_id = e.id
            LEFT JOIN source_records sr ON sr.entity_id = e.id
            LEFT JOIN identifiers i ON i.entity_id = e.id
            WHERE e.id = :entity_id
            GROUP BY e.id
        """

        result = await self.session.execute(text(sql), {"entity_id": entity_id})
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "primary_name": row[1],
            "entity_type": row[2],
            "nationality": row[3],
            "date_of_birth": row[4],
            "year_of_birth": row[5],
            "place_of_birth": row[6],
            "is_active": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
            "updated_at": row[9].isoformat() if row[9] else None,
            "names": row[10],
            "sources": row[11],
            "identifiers": row[12],
        }

    async def _get_entity_sqlite(self, entity_id: str) -> dict[str, Any] | None:
        """Get entity with separate queries for SQLite."""
        # Get entity
        entity_sql = """
            SELECT id, primary_name, entity_type, nationality, date_of_birth,
                   year_of_birth, place_of_birth, is_active, created_at, updated_at
            FROM entities
            WHERE id = :entity_id
        """
        result = await self.session.execute(text(entity_sql), {"entity_id": entity_id})
        row = result.fetchone()

        if not row:
            return None

        entity = {
            "id": row[0],
            "primary_name": row[1],
            "entity_type": row[2],
            "nationality": row[3],
            "date_of_birth": row[4],
            "year_of_birth": row[5],
            "place_of_birth": row[6],
            "is_active": bool(row[7]),
            "created_at": row[8],
            "updated_at": row[9],
        }

        # Get names
        names_sql = "SELECT name_value, name_type FROM names WHERE entity_id = :entity_id"
        result = await self.session.execute(text(names_sql), {"entity_id": entity_id})
        entity["names"] = [{"name_value": r[0], "name_type": r[1]} for r in result.fetchall()]

        # Get sources
        sources_sql = """
            SELECT source, source_uid, programs FROM source_records
            WHERE entity_id = :entity_id AND is_active = 1
        """
        result = await self.session.execute(text(sources_sql), {"entity_id": entity_id})
        entity["sources"] = [{"source": r[0], "source_uid": r[1], "programs": r[2]} for r in result.fetchall()]

        # Get identifiers
        id_sql = """
            SELECT id_type, id_value, issuing_country FROM identifiers
            WHERE entity_id = :entity_id
        """
        result = await self.session.execute(text(id_sql), {"entity_id": entity_id})
        entity["identifiers"] = [
            {"id_type": r[0], "id_value": r[1], "issuing_country": r[2]}
            for r in result.fetchall()
        ]

        return entity
