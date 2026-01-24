"""
TrustCheck Ingestion Service.

Handles the complete data ingestion pipeline:
1. Scraping data from sources
2. Detecting changes
3. Persisting to database
4. Recording audit events
"""

import json
import logging
from datetime import datetime
from uuid import uuid4

from trustcheck.database import (
    ChangeEventRepository,
    EntityRepository,
    EventRepository,
    ScraperRunRepository,
    SourceRecordRepository,
    get_session_context,
)
from trustcheck.domain import (
    Address,
    ChangeEvent,
    ChangeType,
    DataSource,
    EntityType,
    Event,
    EventType,
    Identifier,
    IdentifierType,
    Name,
    NameType,
    SanctionedEntity,
    ScraperRun,
    ScraperStatus,
    Script,
    SourceRecord,
)
from trustcheck.matching import normalize_name
from trustcheck.progress import progress_tracker
from trustcheck.scrapers import ScrapeResult, get_scraper
from trustcheck.scrapers.base import RawEntity

logger = logging.getLogger(__name__)


class IngestionService:
    """Service for ingesting sanctions data from various sources."""

    async def ingest_source(self, source: DataSource, task_id: str | None = None) -> ScraperRun:
        """
        Ingest data from a single source.

        Args:
            source: The data source to ingest from
            task_id: Optional task ID for progress tracking

        Returns:
            ScraperRun with results
        """
        logger.info(f"Starting ingestion for {source.value}")

        # Create scraper run record
        run = ScraperRun(source=source, status=ScraperStatus.RUNNING)

        async with get_session_context() as session:
            run_repo = ScraperRunRepository(session)
            await run_repo.create(run)

        try:
            # Update progress: downloading
            if task_id:
                await progress_tracker.update_progress(
                    task_id, progress=0.05, message=f"Downloading {source.value} data..."
                )

            # Get and execute scraper
            scraper = get_scraper(source)
            result = await scraper.scrape()

            if not result.success:
                run.status = ScraperStatus.FAILED
                run.error_message = result.error_message
                run.completed_at = datetime.utcnow()

                async with get_session_context() as session:
                    run_repo = ScraperRunRepository(session)
                    await run_repo.update(run)

                logger.error(f"Scraping failed for {source.value}: {result.error_message}")
                return run

            # Update progress: processing
            if task_id:
                await progress_tracker.update_progress(
                    task_id,
                    progress=0.15,
                    message=f"Processing {len(result.entities)} entities...",
                    details={"total_entities": len(result.entities)}
                )

            # Process results with progress tracking
            run = await self._process_results(run, result, task_id)

            logger.info(
                f"Ingestion complete for {source.value}: "
                f"{run.entities_processed} processed, "
                f"{run.entities_added} added, "
                f"{run.entities_modified} modified, "
                f"{run.entities_removed} removed"
            )

        except Exception as e:
            logger.exception(f"Error during ingestion for {source.value}: {e}")
            run.status = ScraperStatus.FAILED
            run.error_message = str(e)
            run.completed_at = datetime.utcnow()

            async with get_session_context() as session:
                run_repo = ScraperRunRepository(session)
                await run_repo.update(run)

        return run

    async def ingest_all_sources(self) -> dict[DataSource, ScraperRun]:
        """
        Ingest data from all sources.

        Returns:
            Dictionary of source to ScraperRun results
        """
        results = {}

        for source in [DataSource.OFAC_SDN, DataSource.UN, DataSource.EU, DataSource.UK]:
            try:
                run = await self.ingest_source(source)
                results[source] = run
            except Exception as e:
                logger.error(f"Error ingesting {source.value}: {e}")
                results[source] = ScraperRun(
                    source=source,
                    status=ScraperStatus.FAILED,
                    error_message=str(e),
                )

        return results

    async def _process_results(
        self, run: ScraperRun, result: ScrapeResult, task_id: str | None = None
    ) -> ScraperRun:
        """Process scrape results and update database."""
        run.content_hash = result.content_hash
        run.entities_processed = len(result.entities)
        total_entities = len(result.entities)

        async with get_session_context() as session:
            entity_repo = EntityRepository(session)
            source_repo = SourceRecordRepository(session)
            change_repo = ChangeEventRepository(session)
            event_repo = EventRepository(session)
            run_repo = ScraperRunRepository(session)

            # Track seen UIDs for deactivation
            seen_uids: set[str] = set()

            # Progress tracking
            progress_interval = max(1, total_entities // 20)  # Update every 5%

            for idx, raw_entity in enumerate(result.entities):
                seen_uids.add(raw_entity.source_uid)

                try:
                    change = await self._process_entity(
                        raw_entity,
                        run,
                        entity_repo,
                        source_repo,
                        change_repo,
                        event_repo,
                    )

                    if change:
                        if change.change_type == ChangeType.ADDED:
                            run.entities_added += 1
                        elif change.change_type == ChangeType.MODIFIED:
                            run.entities_modified += 1

                except Exception as e:
                    logger.warning(f"Error processing entity {raw_entity.source_uid}: {e}")
                    continue

                # Update progress periodically
                if task_id and (idx + 1) % progress_interval == 0:
                    progress = 0.15 + (0.80 * (idx + 1) / total_entities)
                    await progress_tracker.update_progress(
                        task_id,
                        progress=progress,
                        message=f"Processing entities ({idx + 1}/{total_entities})...",
                        details={
                            "processed": idx + 1,
                            "total": total_entities,
                            "added": run.entities_added,
                            "modified": run.entities_modified,
                        }
                    )

            # Deactivate entities not seen in this scrape
            removed_ids = await source_repo.deactivate_missing(run.source, seen_uids)
            run.entities_removed = len(removed_ids)

            # Create removal change events
            for entity_id in removed_ids:
                entity = await entity_repo.get_by_id(entity_id)
                if entity:
                    await entity_repo.deactivate(entity_id)

                    change = ChangeEvent(
                        entity_id=entity.id,
                        entity_name=entity.primary_name,
                        source=run.source,
                        change_type=ChangeType.REMOVED,
                        scraper_run_id=run.id,
                    )
                    await change_repo.create(change)

                    event = Event(
                        event_type=EventType.ENTITY_REMOVED,
                        aggregate_id=entity.id,
                        event_data={"name": entity.primary_name, "source": run.source.value},
                    )
                    await event_repo.create(event)

            # Update run status
            run.status = ScraperStatus.SUCCESS
            run.completed_at = datetime.utcnow()
            await run_repo.update(run)

            # Final progress update
            if task_id:
                await progress_tracker.update_progress(
                    task_id,
                    progress=0.95,
                    message="Finalizing...",
                    details={
                        "processed": total_entities,
                        "added": run.entities_added,
                        "modified": run.entities_modified,
                        "removed": run.entities_removed,
                    }
                )

        return run

    async def _process_entity(
        self,
        raw: RawEntity,
        run: ScraperRun,
        entity_repo: EntityRepository,
        source_repo: SourceRecordRepository,
        change_repo: ChangeEventRepository,
        event_repo: EventRepository,
    ) -> ChangeEvent | None:
        """Process a single raw entity."""
        # Check if we already have this source record
        existing_record = await source_repo.get_by_source_uid(run.source, raw.source_uid)

        if existing_record:
            # Update existing
            return await self._update_entity(
                raw, existing_record, run, entity_repo, source_repo, change_repo, event_repo
            )
        else:
            # Create new
            return await self._create_entity(raw, run, entity_repo, source_repo, change_repo, event_repo)

    async def _create_entity(
        self,
        raw: RawEntity,
        run: ScraperRun,
        entity_repo: EntityRepository,
        source_repo: SourceRecordRepository,
        change_repo: ChangeEventRepository,
        event_repo: EventRepository,
    ) -> ChangeEvent:
        """Create a new entity from raw data."""
        # Build domain entity
        entity = self._raw_to_entity(raw)

        # Create entity
        await entity_repo.create(entity)

        # Create source record
        content_hash = self._hash_raw_entity(raw)
        source_record = SourceRecord(
            entity_id=entity.id,
            source=run.source,
            source_uid=raw.source_uid,
            programs=raw.programs,
            raw_data=raw.raw_data,
            content_hash=content_hash,
        )
        await source_repo.create(source_record)

        # Create change event
        change = ChangeEvent(
            entity_id=entity.id,
            entity_name=entity.primary_name,
            source=run.source,
            change_type=ChangeType.ADDED,
            new_values={
                "name": entity.primary_name,
                "type": entity.entity_type.value,
                "programs": raw.programs,
            },
            scraper_run_id=run.id,
        )
        await change_repo.create(change)

        # Create audit event
        event = Event(
            event_type=EventType.ENTITY_ADDED,
            aggregate_id=entity.id,
            event_data={
                "name": entity.primary_name,
                "source": run.source.value,
                "source_uid": raw.source_uid,
            },
        )
        await event_repo.create(event)

        return change

    async def _update_entity(
        self,
        raw: RawEntity,
        existing_record: SourceRecord,
        run: ScraperRun,
        entity_repo: EntityRepository,
        source_repo: SourceRecordRepository,
        change_repo: ChangeEventRepository,
        event_repo: EventRepository,
    ) -> ChangeEvent | None:
        """Update an existing entity with new raw data."""
        content_hash = self._hash_raw_entity(raw)

        # Check if content changed
        if content_hash == existing_record.content_hash:
            # No changes, just update last seen
            await source_repo.update_last_seen(str(existing_record.id))
            return None

        # Content changed - update
        old_entity = await entity_repo.get_by_id(str(existing_record.entity_id))
        if not old_entity:
            return None

        # Build new entity from raw
        new_entity = self._raw_to_entity(raw)
        new_entity.id = old_entity.id
        new_entity.created_at = old_entity.created_at

        # Detect field changes
        field_changes = self._detect_changes(old_entity, new_entity)

        if not field_changes:
            # No meaningful changes
            await source_repo.update_last_seen(str(existing_record.id))
            return None

        # Update entity
        await entity_repo.update(new_entity)

        # Update source record
        await source_repo.update_hash(str(existing_record.id), content_hash, raw.raw_data)

        # Create change event
        change = ChangeEvent(
            entity_id=new_entity.id,
            entity_name=new_entity.primary_name,
            source=run.source,
            change_type=ChangeType.MODIFIED,
            field_changes=field_changes,
            scraper_run_id=run.id,
        )
        await change_repo.create(change)

        # Create audit event
        event = Event(
            event_type=EventType.ENTITY_MODIFIED,
            aggregate_id=new_entity.id,
            event_data={
                "name": new_entity.primary_name,
                "source": run.source.value,
                "changes": field_changes,
            },
        )
        await event_repo.create(event)

        return change

    def _raw_to_entity(self, raw: RawEntity) -> SanctionedEntity:
        """Convert raw entity to domain entity."""
        # Build names
        names = []
        for name_data in raw.names:
            name_type = NameType.ALIAS
            type_str = name_data.get("type", "").upper()
            if type_str == "PRIMARY":
                name_type = NameType.PRIMARY
            elif type_str in ("AKA", "ALSO KNOWN AS"):
                name_type = NameType.AKA
            elif type_str in ("FKA", "FORMERLY KNOWN AS"):
                name_type = NameType.FKA

            names.append(
                Name(
                    value=name_data["value"],
                    normalized=normalize_name(name_data["value"]),
                    name_type=name_type,
                    script=Script.LATIN,
                )
            )

        # Build addresses
        addresses = []
        for addr_data in raw.addresses:
            addresses.append(
                Address(
                    country=addr_data.get("country"),
                    city=addr_data.get("city"),
                    street=addr_data.get("street"),
                    postal_code=addr_data.get("postal_code"),
                    full_address=addr_data.get("full_address"),
                )
            )

        # Build identifiers
        identifiers = []
        for id_data in raw.identifiers:
            id_type = IdentifierType.OTHER
            type_str = id_data.get("type", "").upper()
            if type_str in IdentifierType.__members__:
                id_type = IdentifierType[type_str]

            identifiers.append(
                Identifier(
                    id_type=id_type,
                    value=id_data["value"],
                    country=id_data.get("country"),
                )
            )

        return SanctionedEntity(
            primary_name=raw.primary_name,
            primary_name_normalized=normalize_name(raw.primary_name),
            entity_type=raw.entity_type,
            names=names,
            addresses=addresses,
            identifiers=identifiers,
            programs=raw.programs,
            place_of_birth=raw.place_of_birth,
            nationality=raw.nationality,
            remarks=raw.remarks,
        )

    def _hash_raw_entity(self, raw: RawEntity) -> str:
        """Generate a hash of the raw entity for change detection."""
        import hashlib

        # Create a normalized representation for hashing
        data = {
            "source_uid": raw.source_uid,
            "name": raw.primary_name,
            "type": raw.entity_type.value,
            "names": sorted([n["value"] for n in raw.names]),
            "programs": sorted(raw.programs),
            "dob": raw.date_of_birth,
            "pob": raw.place_of_birth,
            "nationality": raw.nationality,
        }
        content = json.dumps(data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _detect_changes(
        self, old: SanctionedEntity, new: SanctionedEntity
    ) -> dict[str, dict[str, str]]:
        """Detect field-level changes between old and new entity."""
        changes = {}

        if old.primary_name != new.primary_name:
            changes["primary_name"] = {"old": old.primary_name, "new": new.primary_name}

        if old.entity_type != new.entity_type:
            changes["entity_type"] = {"old": old.entity_type.value, "new": new.entity_type.value}

        old_names = {n.value for n in old.names}
        new_names = {n.value for n in new.names}
        if old_names != new_names:
            added = new_names - old_names
            removed = old_names - new_names
            if added or removed:
                changes["names"] = {
                    "added": list(added),
                    "removed": list(removed),
                }

        old_programs = set(old.programs)
        new_programs = set(new.programs)
        if old_programs != new_programs:
            added = new_programs - old_programs
            removed = old_programs - new_programs
            if added or removed:
                changes["programs"] = {
                    "added": list(added),
                    "removed": list(removed),
                }

        if old.nationality != new.nationality:
            changes["nationality"] = {
                "old": old.nationality or "",
                "new": new.nationality or "",
            }

        return changes


# Global service instance
_ingestion_service: IngestionService | None = None


def get_ingestion_service() -> IngestionService:
    """Get the global ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service
