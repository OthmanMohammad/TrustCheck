"""
TrustCheck Domain Models.

Pure Python domain models representing the core business entities.
These models are independent of any persistence layer.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from trustcheck.domain.enums import (
    ChangeType,
    DataSource,
    EntityType,
    EventType,
    IdentifierType,
    MatchType,
    NameType,
    ScraperStatus,
    Script,
)


@dataclass
class Name:
    """An entity name (primary or alias)."""

    value: str
    normalized: str
    name_type: NameType = NameType.PRIMARY
    script: Script = Script.LATIN
    id: UUID = field(default_factory=uuid4)


@dataclass
class Address:
    """A physical address associated with an entity."""

    country: str | None = None
    city: str | None = None
    street: str | None = None
    postal_code: str | None = None
    full_address: str | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class Identifier:
    """An identifying document or number for an entity."""

    id_type: IdentifierType
    value: str
    country: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    id: UUID = field(default_factory=uuid4)


@dataclass
class SanctionedEntity:
    """A sanctioned entity (person, organization, vessel, etc.)."""

    primary_name: str
    primary_name_normalized: str
    entity_type: EntityType
    id: UUID = field(default_factory=uuid4)
    names: list[Name] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    identifiers: list[Identifier] = field(default_factory=list)
    programs: list[str] = field(default_factory=list)
    sources: list[DataSource] = field(default_factory=list)
    date_of_birth: date | None = None
    year_of_birth: int | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    remarks: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SourceRecord:
    """A record from a specific sanctions data source."""

    source: DataSource
    source_uid: str
    entity_id: UUID
    raw_data: dict[str, Any]
    content_hash: str
    id: UUID = field(default_factory=uuid4)
    programs: list[str] = field(default_factory=list)
    is_active: bool = True
    first_seen_at: datetime = field(default_factory=datetime.utcnow)
    last_seen_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ChangeEvent:
    """A detected change in sanctions data."""

    entity_id: UUID
    entity_name: str
    source: DataSource
    change_type: ChangeType
    id: UUID = field(default_factory=uuid4)
    field_changes: dict[str, Any] = field(default_factory=dict)
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    scraper_run_id: UUID | None = None


@dataclass
class Event:
    """An immutable audit event for event sourcing."""

    event_type: EventType
    aggregate_id: UUID
    event_data: dict[str, Any]
    id: UUID = field(default_factory=uuid4)
    aggregate_type: str = "ENTITY"
    metadata: dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ScraperRun:
    """A record of a scraper execution."""

    source: DataSource
    id: UUID = field(default_factory=uuid4)
    status: ScraperStatus = ScraperStatus.RUNNING
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    entities_processed: int = 0
    entities_added: int = 0
    entities_modified: int = 0
    entities_removed: int = 0
    content_hash: str | None = None
    error_message: str | None = None


@dataclass
class MatchedField:
    """Details of a matched field in screening."""

    field_name: str
    query_value: str
    matched_value: str
    score: float
    match_type: MatchType


@dataclass
class ScreeningMatch:
    """A match result from screening."""

    entity: SanctionedEntity
    score: float
    match_type: MatchType
    matched_fields: list[MatchedField] = field(default_factory=list)
    sources: list[DataSource] = field(default_factory=list)


@dataclass
class ScreeningRequest:
    """A request to screen a name against sanctions lists."""

    name: str
    date_of_birth: date | None = None
    country: str | None = None
    threshold: float = 0.80
    include_inactive: bool = False
    max_results: int = 100
    request_id: UUID = field(default_factory=uuid4)


@dataclass
class ScreeningResult:
    """The result of a screening request."""

    request: ScreeningRequest
    matches: list[ScreeningMatch] = field(default_factory=list)
    screened_at: datetime = field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0


@dataclass
class DashboardStats:
    """Statistics for the dashboard."""

    total_entities: int = 0
    active_entities: int = 0
    entities_by_source: dict[str, int] = field(default_factory=dict)
    entities_by_type: dict[str, int] = field(default_factory=dict)
    recent_changes: int = 0
    changes_last_24h: int = 0
    changes_last_7d: int = 0
    last_scrape_times: dict[str, datetime | None] = field(default_factory=dict)
    scraper_statuses: dict[str, str] = field(default_factory=dict)
