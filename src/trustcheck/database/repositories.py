"""
TrustCheck Database Repositories.

Repository pattern implementation for database access.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from trustcheck.database.models import (
    AddressModel,
    ChangeEventModel,
    EntityModel,
    EventModel,
    IdentifierModel,
    NameModel,
    ScraperRunModel,
    ScreeningResultModel,
    SourceRecordModel,
)
from trustcheck.domain import (
    Address,
    ChangeEvent,
    ChangeType,
    DataSource,
    DashboardStats,
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

logger = logging.getLogger(__name__)


class EntityRepository:
    """Repository for entity operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: str) -> SanctionedEntity | None:
        """Get entity by ID with all related data."""
        stmt = (
            select(EntityModel)
            .options(
                selectinload(EntityModel.names),
                selectinload(EntityModel.addresses),
                selectinload(EntityModel.identifiers),
                selectinload(EntityModel.source_records),
            )
            .where(EntityModel.id == entity_id)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_source_uid(self, source: DataSource, source_uid: str) -> SanctionedEntity | None:
        """Get entity by source and source UID."""
        stmt = (
            select(EntityModel)
            .join(SourceRecordModel)
            .options(
                selectinload(EntityModel.names),
                selectinload(EntityModel.addresses),
                selectinload(EntityModel.identifiers),
                selectinload(EntityModel.source_records),
            )
            .where(
                SourceRecordModel.source == source.value,
                SourceRecordModel.source_uid == source_uid,
            )
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_entities(
        self,
        source: DataSource | None = None,
        entity_type: EntityType | None = None,
        active_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SanctionedEntity], int]:
        """List entities with filtering and pagination."""
        # Base query with all relationships eagerly loaded
        stmt = select(EntityModel).options(
            selectinload(EntityModel.names),
            selectinload(EntityModel.addresses),
            selectinload(EntityModel.identifiers),
            selectinload(EntityModel.source_records),
        )

        # Apply filters
        if active_only:
            stmt = stmt.where(EntityModel.is_active.is_(True))
        if entity_type:
            stmt = stmt.where(EntityModel.entity_type == entity_type.value)
        if source:
            stmt = stmt.join(SourceRecordModel).where(SourceRecordModel.source == source.value)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(EntityModel.updated_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        models = result.scalars().unique().all()
        entities = [self._to_domain(m) for m in models]

        return entities, total

    async def search(
        self,
        query: str,
        limit: int = 50,
        active_only: bool = True,
    ) -> list[SanctionedEntity]:
        """Search entities by name (normalized)."""
        normalized_query = f"%{query.upper()}%"

        stmt = (
            select(EntityModel)
            .options(
                selectinload(EntityModel.names),
                selectinload(EntityModel.addresses),
                selectinload(EntityModel.identifiers),
                selectinload(EntityModel.source_records),
            )
            .where(EntityModel.primary_name_normalized.like(normalized_query))
        )

        if active_only:
            stmt = stmt.where(EntityModel.is_active.is_(True))

        stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        models = result.scalars().unique().all()
        return [self._to_domain(m) for m in models]

    async def create(self, entity: SanctionedEntity) -> SanctionedEntity:
        """Create a new entity with all related data."""
        model = EntityModel(
            id=str(entity.id),
            entity_type=entity.entity_type.value,
            primary_name=entity.primary_name,
            primary_name_normalized=entity.primary_name_normalized,
            date_of_birth=entity.date_of_birth.isoformat() if entity.date_of_birth else None,
            year_of_birth=entity.year_of_birth,
            place_of_birth=entity.place_of_birth,
            nationality=entity.nationality,
            remarks=entity.remarks,
            is_active=entity.is_active,
        )

        # Add names
        for name in entity.names:
            model.names.append(
                NameModel(
                    id=str(name.id),
                    name_type=name.name_type.value,
                    name_value=name.value,
                    name_normalized=name.normalized,
                    script=name.script.value,
                )
            )

        # Add addresses
        for addr in entity.addresses:
            model.addresses.append(
                AddressModel(
                    id=str(addr.id),
                    country=addr.country,
                    city=addr.city,
                    street=addr.street,
                    postal_code=addr.postal_code,
                    full_address=addr.full_address,
                )
            )

        # Add identifiers
        for ident in entity.identifiers:
            model.identifiers.append(
                IdentifierModel(
                    id=str(ident.id),
                    id_type=ident.id_type.value,
                    id_value=ident.value,
                    country=ident.country,
                    issue_date=ident.issue_date.isoformat() if ident.issue_date else None,
                    expiry_date=ident.expiry_date.isoformat() if ident.expiry_date else None,
                )
            )

        self.session.add(model)
        await self.session.flush()

        return entity

    async def update(self, entity: SanctionedEntity) -> SanctionedEntity:
        """Update an existing entity."""
        stmt = (
            update(EntityModel)
            .where(EntityModel.id == str(entity.id))
            .values(
                primary_name=entity.primary_name,
                primary_name_normalized=entity.primary_name_normalized,
                entity_type=entity.entity_type.value,
                date_of_birth=entity.date_of_birth.isoformat() if entity.date_of_birth else None,
                year_of_birth=entity.year_of_birth,
                place_of_birth=entity.place_of_birth,
                nationality=entity.nationality,
                remarks=entity.remarks,
                is_active=entity.is_active,
                updated_at=datetime.utcnow(),
            )
        )
        await self.session.execute(stmt)

        # Update names - delete and recreate
        await self.session.execute(delete(NameModel).where(NameModel.entity_id == str(entity.id)))
        for name in entity.names:
            self.session.add(
                NameModel(
                    id=str(name.id),
                    entity_id=str(entity.id),
                    name_type=name.name_type.value,
                    name_value=name.value,
                    name_normalized=name.normalized,
                    script=name.script.value,
                )
            )

        await self.session.flush()
        return entity

    async def deactivate(self, entity_id: str) -> None:
        """Mark entity as inactive."""
        stmt = (
            update(EntityModel)
            .where(EntityModel.id == entity_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        await self.session.execute(stmt)

    async def get_all_normalized_names(self, active_only: bool = True) -> list[tuple[str, str, str]]:
        """Get all normalized names for matching (entity_id, name_normalized, name_value)."""
        stmt = select(NameModel.entity_id, NameModel.name_normalized, NameModel.name_value)

        if active_only:
            stmt = stmt.join(EntityModel).where(EntityModel.is_active.is_(True))

        result = await self.session.execute(stmt)
        return [(row[0], row[1], row[2]) for row in result.all()]

    async def count_by_source(self) -> dict[str, int]:
        """Count entities by source."""
        stmt = (
            select(SourceRecordModel.source, func.count(func.distinct(SourceRecordModel.entity_id)))
            .where(SourceRecordModel.is_active.is_(True))
            .group_by(SourceRecordModel.source)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_by_type(self) -> dict[str, int]:
        """Count entities by type."""
        stmt = (
            select(EntityModel.entity_type, func.count())
            .where(EntityModel.is_active.is_(True))
            .group_by(EntityModel.entity_type)
        )
        result = await self.session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_total(self, active_only: bool = True) -> int:
        """Count total entities."""
        stmt = select(func.count()).select_from(EntityModel)
        if active_only:
            stmt = stmt.where(EntityModel.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, model: EntityModel) -> SanctionedEntity:
        """Convert database model to domain entity."""
        names = [
            Name(
                id=UUID(n.id),
                value=n.name_value,
                normalized=n.name_normalized,
                name_type=NameType(n.name_type),
                script=Script(n.script) if n.script else Script.LATIN,
            )
            for n in model.names
        ]

        addresses = [
            Address(
                id=UUID(a.id),
                country=a.country,
                city=a.city,
                street=a.street,
                postal_code=a.postal_code,
                full_address=a.full_address,
            )
            for a in model.addresses
        ]

        identifiers = [
            Identifier(
                id=UUID(i.id),
                id_type=IdentifierType(i.id_type) if i.id_type in IdentifierType.__members__ else IdentifierType.OTHER,
                value=i.id_value,
                country=i.country,
            )
            for i in model.identifiers
        ]

        programs = []
        sources = []
        for sr in model.source_records:
            if sr.is_active:
                try:
                    sources.append(DataSource(sr.source))
                except ValueError:
                    pass
            if sr.programs:
                try:
                    programs.extend(json.loads(sr.programs))
                except json.JSONDecodeError:
                    pass

        return SanctionedEntity(
            id=UUID(model.id),
            primary_name=model.primary_name,
            primary_name_normalized=model.primary_name_normalized,
            entity_type=EntityType(model.entity_type),
            names=names,
            addresses=addresses,
            identifiers=identifiers,
            programs=list(set(programs)),
            sources=list(set(sources)),
            date_of_birth=datetime.fromisoformat(model.date_of_birth).date() if model.date_of_birth else None,
            year_of_birth=model.year_of_birth,
            place_of_birth=model.place_of_birth,
            nationality=model.nationality,
            remarks=model.remarks,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SourceRecordRepository:
    """Repository for source record operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_source_uid(self, source: DataSource, source_uid: str) -> SourceRecord | None:
        """Get source record by source and UID."""
        stmt = select(SourceRecordModel).where(
            SourceRecordModel.source == source.value,
            SourceRecordModel.source_uid == source_uid,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all_by_source(self, source: DataSource, active_only: bool = True) -> list[SourceRecord]:
        """Get all source records for a source."""
        stmt = select(SourceRecordModel).where(SourceRecordModel.source == source.value)
        if active_only:
            stmt = stmt.where(SourceRecordModel.is_active.is_(True))

        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def get_all_uids_for_source(self, source: DataSource) -> list[str]:
        """Get all source UIDs for a source (for efficient duplicate checking)."""
        stmt = select(SourceRecordModel.source_uid).where(
            SourceRecordModel.source == source.value
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.fetchall()]

    async def get_batch_by_source_uids(
        self, source: DataSource, source_uids: list[str]
    ) -> dict[str, SourceRecord]:
        """Get multiple source records by UIDs in one query. Returns dict keyed by source_uid."""
        if not source_uids:
            return {}
        stmt = select(SourceRecordModel).where(
            SourceRecordModel.source == source.value,
            SourceRecordModel.source_uid.in_(source_uids),
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return {m.source_uid: self._to_domain(m) for m in models}

    async def create(self, record: SourceRecord) -> SourceRecord:
        """Create a new source record."""
        model = SourceRecordModel(
            id=str(record.id),
            entity_id=str(record.entity_id),
            source=record.source.value,
            source_uid=record.source_uid,
            programs=json.dumps(record.programs) if record.programs else None,
            raw_data=json.dumps(record.raw_data) if record.raw_data else None,
            content_hash=record.content_hash,
            is_active=record.is_active,
        )
        self.session.add(model)
        await self.session.flush()
        return record

    async def update_last_seen(self, record_id: str) -> None:
        """Update the last seen timestamp."""
        stmt = (
            update(SourceRecordModel)
            .where(SourceRecordModel.id == record_id)
            .values(last_seen_at=datetime.utcnow())
        )
        await self.session.execute(stmt)

    async def update_hash(self, record_id: str, content_hash: str, raw_data: dict[str, Any]) -> None:
        """Update content hash and raw data."""
        stmt = (
            update(SourceRecordModel)
            .where(SourceRecordModel.id == record_id)
            .values(
                content_hash=content_hash,
                raw_data=json.dumps(raw_data),
                last_seen_at=datetime.utcnow(),
            )
        )
        await self.session.execute(stmt)

    async def deactivate_missing(self, source: DataSource, seen_uids: set[str]) -> list[str]:
        """Deactivate records not in the seen UIDs set. Returns deactivated entity IDs."""
        # Get records to deactivate
        stmt = select(SourceRecordModel.entity_id).where(
            SourceRecordModel.source == source.value,
            SourceRecordModel.is_active.is_(True),
            SourceRecordModel.source_uid.not_in(seen_uids) if seen_uids else True,
        )
        result = await self.session.execute(stmt)
        entity_ids = [row[0] for row in result.all()]

        # Deactivate
        if entity_ids:
            stmt = (
                update(SourceRecordModel)
                .where(
                    SourceRecordModel.source == source.value,
                    SourceRecordModel.entity_id.in_(entity_ids),
                )
                .values(is_active=False)
            )
            await self.session.execute(stmt)

        return entity_ids

    def _to_domain(self, model: SourceRecordModel) -> SourceRecord:
        """Convert database model to domain entity."""
        return SourceRecord(
            id=UUID(model.id),
            entity_id=UUID(model.entity_id),
            source=DataSource(model.source),
            source_uid=model.source_uid,
            programs=json.loads(model.programs) if model.programs else [],
            raw_data=json.loads(model.raw_data) if model.raw_data else {},
            content_hash=model.content_hash,
            is_active=model.is_active,
            first_seen_at=model.first_seen_at,
            last_seen_at=model.last_seen_at,
        )


class ChangeEventRepository:
    """Repository for change event operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: ChangeEvent) -> ChangeEvent:
        """Create a new change event."""
        model = ChangeEventModel(
            id=str(event.id),
            entity_id=str(event.entity_id),
            entity_name=event.entity_name,
            source=event.source.value,
            change_type=event.change_type.value,
            field_changes=json.dumps(event.field_changes) if event.field_changes else None,
            old_values=json.dumps(event.old_values) if event.old_values else None,
            new_values=json.dumps(event.new_values) if event.new_values else None,
            detected_at=event.detected_at,
            scraper_run_id=str(event.scraper_run_id) if event.scraper_run_id else None,
        )
        self.session.add(model)
        await self.session.flush()
        return event

    async def list_changes(
        self,
        source: DataSource | None = None,
        change_type: ChangeType | None = None,
        days: int = 7,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ChangeEvent], int]:
        """List change events with filtering."""
        since = datetime.utcnow() - timedelta(days=days)

        stmt = select(ChangeEventModel).where(ChangeEventModel.detected_at >= since)

        if source:
            stmt = stmt.where(ChangeEventModel.source == source.value)
        if change_type:
            stmt = stmt.where(ChangeEventModel.change_type == change_type.value)

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Apply pagination
        stmt = stmt.order_by(ChangeEventModel.detected_at.desc()).offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        models = result.scalars().all()
        events = [self._to_domain(m) for m in models]

        return events, total

    async def count_since(self, since: datetime) -> int:
        """Count changes since a given time."""
        stmt = select(func.count()).select_from(ChangeEventModel).where(ChangeEventModel.detected_at >= since)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    def _to_domain(self, model: ChangeEventModel) -> ChangeEvent:
        """Convert database model to domain entity."""
        return ChangeEvent(
            id=UUID(model.id),
            entity_id=UUID(model.entity_id),
            entity_name=model.entity_name,
            source=DataSource(model.source),
            change_type=ChangeType(model.change_type),
            field_changes=json.loads(model.field_changes) if model.field_changes else {},
            old_values=json.loads(model.old_values) if model.old_values else {},
            new_values=json.loads(model.new_values) if model.new_values else {},
            detected_at=model.detected_at,
            scraper_run_id=UUID(model.scraper_run_id) if model.scraper_run_id else None,
        )


class ScraperRunRepository:
    """Repository for scraper run operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, run: ScraperRun) -> ScraperRun:
        """Create a new scraper run."""
        model = ScraperRunModel(
            id=str(run.id),
            source=run.source.value,
            status=run.status.value,
            started_at=run.started_at,
        )
        self.session.add(model)
        await self.session.flush()
        return run

    async def update(self, run: ScraperRun) -> ScraperRun:
        """Update a scraper run."""
        stmt = (
            update(ScraperRunModel)
            .where(ScraperRunModel.id == str(run.id))
            .values(
                status=run.status.value,
                completed_at=run.completed_at,
                entities_processed=run.entities_processed,
                entities_added=run.entities_added,
                entities_modified=run.entities_modified,
                entities_removed=run.entities_removed,
                content_hash=run.content_hash,
                error_message=run.error_message,
            )
        )
        await self.session.execute(stmt)
        return run

    async def get_latest_by_source(self, source: DataSource) -> ScraperRun | None:
        """Get the latest scraper run for a source."""
        stmt = (
            select(ScraperRunModel)
            .where(ScraperRunModel.source == source.value)
            .order_by(ScraperRunModel.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_latest_successful_by_source(self, source: DataSource) -> ScraperRun | None:
        """Get the latest successful scraper run for a source."""
        stmt = (
            select(ScraperRunModel)
            .where(
                ScraperRunModel.source == source.value,
                ScraperRunModel.status == ScraperStatus.SUCCESS.value,
            )
            .order_by(ScraperRunModel.started_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_all_latest(self) -> dict[str, ScraperRun]:
        """Get latest run for each source."""
        sources = [s.value for s in DataSource]
        result = {}

        for source in sources:
            run = await self.get_latest_by_source(DataSource(source))
            if run:
                result[source] = run

        return result

    def _to_domain(self, model: ScraperRunModel) -> ScraperRun:
        """Convert database model to domain entity."""
        return ScraperRun(
            id=UUID(model.id),
            source=DataSource(model.source),
            status=ScraperStatus(model.status),
            started_at=model.started_at,
            completed_at=model.completed_at,
            entities_processed=model.entities_processed,
            entities_added=model.entities_added,
            entities_modified=model.entities_modified,
            entities_removed=model.entities_removed,
            content_hash=model.content_hash,
            error_message=model.error_message,
        )


class EventRepository:
    """Repository for audit events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, event: Event) -> Event:
        """Create a new audit event."""
        model = EventModel(
            id=str(event.id),
            event_type=event.event_type.value,
            aggregate_type=event.aggregate_type,
            aggregate_id=str(event.aggregate_id),
            event_data=json.dumps(event.event_data),
            metadata=json.dumps(event.metadata) if event.metadata else None,
            occurred_at=event.occurred_at,
        )
        self.session.add(model)
        await self.session.flush()
        return event

    async def get_by_aggregate(self, aggregate_type: str, aggregate_id: str) -> list[Event]:
        """Get all events for an aggregate."""
        stmt = (
            select(EventModel)
            .where(
                EventModel.aggregate_type == aggregate_type,
                EventModel.aggregate_id == aggregate_id,
            )
            .order_by(EventModel.occurred_at.asc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    def _to_domain(self, model: EventModel) -> Event:
        """Convert database model to domain entity."""
        return Event(
            id=UUID(model.id),
            event_type=EventType(model.event_type),
            aggregate_type=model.aggregate_type,
            aggregate_id=UUID(model.aggregate_id),
            event_data=json.loads(model.event_data),
            metadata=json.loads(model.metadata) if model.metadata else {},
            occurred_at=model.occurred_at,
        )


class DashboardRepository:
    """Repository for dashboard statistics."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.entity_repo = EntityRepository(session)
        self.change_repo = ChangeEventRepository(session)
        self.scraper_repo = ScraperRunRepository(session)

    async def get_stats(self) -> DashboardStats:
        """Get dashboard statistics."""
        now = datetime.utcnow()
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Get counts
        total = await self.entity_repo.count_total(active_only=False)
        active = await self.entity_repo.count_total(active_only=True)
        by_source = await self.entity_repo.count_by_source()
        by_type = await self.entity_repo.count_by_type()

        # Get change counts
        changes_24h = await self.change_repo.count_since(day_ago)
        changes_7d = await self.change_repo.count_since(week_ago)

        # Get scraper statuses
        latest_runs = await self.scraper_repo.get_all_latest()
        last_scrape_times = {
            source: run.completed_at or run.started_at for source, run in latest_runs.items()
        }
        scraper_statuses = {source: run.status.value for source, run in latest_runs.items()}

        return DashboardStats(
            total_entities=total,
            active_entities=active,
            entities_by_source=by_source,
            entities_by_type=by_type,
            recent_changes=changes_7d,
            changes_last_24h=changes_24h,
            changes_last_7d=changes_7d,
            last_scrape_times=last_scrape_times,
            scraper_statuses=scraper_statuses,
        )
