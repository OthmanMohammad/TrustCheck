"""
TrustCheck Database Models.

SQLAlchemy ORM models for the sanctions database.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def generate_uuid() -> str:
    """Generate a UUID string."""
    return str(uuid4())


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class EntityModel(Base):
    """Sanctioned entity database model."""

    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    primary_name: Mapped[str] = mapped_column(String(500), nullable=False)
    primary_name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(20))
    year_of_birth: Mapped[int | None] = mapped_column(Integer)
    place_of_birth: Mapped[str | None] = mapped_column(String(255))
    nationality: Mapped[str | None] = mapped_column(String(255))
    remarks: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    names: Mapped[list["NameModel"]] = relationship(
        "NameModel", back_populates="entity", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["AddressModel"]] = relationship(
        "AddressModel", back_populates="entity", cascade="all, delete-orphan"
    )
    identifiers: Mapped[list["IdentifierModel"]] = relationship(
        "IdentifierModel", back_populates="entity", cascade="all, delete-orphan"
    )
    source_records: Mapped[list["SourceRecordModel"]] = relationship(
        "SourceRecordModel", back_populates="entity", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_entity_active_type", "is_active", "entity_type"),
        Index("idx_entity_name_normalized", "primary_name_normalized"),
    )


class NameModel(Base):
    """Entity name (primary or alias) database model."""

    __tablename__ = "names"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name_value: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    script: Mapped[str] = mapped_column(String(20), default="LATIN")

    # Relationships
    entity: Mapped["EntityModel"] = relationship("EntityModel", back_populates="names")

    __table_args__ = (Index("idx_name_entity_type", "entity_id", "name_type"),)


class AddressModel(Base):
    """Entity address database model."""

    __tablename__ = "addresses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    country: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(255))
    street: Mapped[str | None] = mapped_column(String(500))
    postal_code: Mapped[str | None] = mapped_column(String(50))
    full_address: Mapped[str | None] = mapped_column(Text)

    # Relationships
    entity: Mapped["EntityModel"] = relationship("EntityModel", back_populates="addresses")


class IdentifierModel(Base):
    """Entity identifier database model."""

    __tablename__ = "identifiers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    id_type: Mapped[str] = mapped_column(String(50), nullable=False)
    id_value: Mapped[str] = mapped_column(Text, nullable=False)  # Can be very long
    country: Mapped[str | None] = mapped_column(String(255))
    issue_date: Mapped[str | None] = mapped_column(String(20))
    expiry_date: Mapped[str | None] = mapped_column(String(20))

    # Relationships
    entity: Mapped["EntityModel"] = relationship("EntityModel", back_populates="identifiers")

    __table_args__ = (Index("idx_identifier_type_value", "id_type", "id_value"),)


class SourceRecordModel(Base):
    """Source record database model."""

    __tablename__ = "source_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_uid: Mapped[str] = mapped_column(String(255), nullable=False)
    programs: Mapped[str | None] = mapped_column(Text)  # JSON array as string
    raw_data: Mapped[str | None] = mapped_column(Text)  # JSON as string
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    entity: Mapped["EntityModel"] = relationship("EntityModel", back_populates="source_records")

    __table_args__ = (
        Index("idx_source_record_source_uid", "source", "source_uid", unique=True),
        Index("idx_source_record_hash", "content_hash"),
    )


class EventModel(Base):
    """Immutable event for audit logging."""

    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(String(50), default="ENTITY")
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_data: Mapped[str] = mapped_column(Text, nullable=False)  # JSON as string
    event_metadata: Mapped[str | None] = mapped_column(Text)  # JSON as string
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index("idx_event_aggregate", "aggregate_type", "aggregate_id"),
        Index("idx_event_type_time", "event_type", "occurred_at"),
    )


class ScraperRunModel(Base):
    """Scraper execution record."""

    __tablename__ = "scraper_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    entities_processed: Mapped[int] = mapped_column(Integer, default=0)
    entities_added: Mapped[int] = mapped_column(Integer, default=0)
    entities_modified: Mapped[int] = mapped_column(Integer, default=0)
    entities_removed: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("idx_scraper_run_source_time", "source", "started_at"),
        Index("idx_scraper_run_status", "status"),
    )


class ChangeEventModel(Base):
    """Change event database model."""

    __tablename__ = "change_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    field_changes: Mapped[str | None] = mapped_column(Text)  # JSON as string
    old_values: Mapped[str | None] = mapped_column(Text)  # JSON as string
    new_values: Mapped[str | None] = mapped_column(Text)  # JSON as string
    detected_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    scraper_run_id: Mapped[str | None] = mapped_column(String(36))

    __table_args__ = (
        Index("idx_change_source_time", "source", "detected_at"),
        Index("idx_change_type_time", "change_type", "detected_at"),
    )


class ScreeningResultModel(Base):
    """Screening result database model for audit purposes."""

    __tablename__ = "screening_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    query_name: Mapped[str] = mapped_column(String(500), nullable=False)
    query_normalized: Mapped[str] = mapped_column(String(500), nullable=False)
    matched_entity_id: Mapped[str | None] = mapped_column(String(36))
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_type: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_fields: Mapped[str | None] = mapped_column(Text)  # JSON as string
    screened_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    processing_time_ms: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (Index("idx_screening_time", "screened_at"),)


class BatchJobModel(Base):
    """Batch screening job database model."""

    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    processed_records: Mapped[int] = mapped_column(Integer, default=0)
    matched_records: Mapped[int] = mapped_column(Integer, default=0)
    threshold: Mapped[float] = mapped_column(Float, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_message: Mapped[str | None] = mapped_column(Text)
    result_file: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    results: Mapped[list["BatchResultModel"]] = relationship(
        "BatchResultModel", back_populates="batch_job", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_batch_status", "status"),
        Index("idx_batch_created", "created_at"),
    )


class BatchResultModel(Base):
    """Individual result from batch screening."""

    __tablename__ = "batch_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    batch_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("batch_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    input_name: Mapped[str] = mapped_column(String(500), nullable=False)
    input_dob: Mapped[str | None] = mapped_column(String(20))
    input_country: Mapped[str | None] = mapped_column(String(255))
    has_match: Mapped[bool] = mapped_column(Boolean, default=False)
    best_match_score: Mapped[float | None] = mapped_column(Float)
    best_match_entity_id: Mapped[str | None] = mapped_column(String(36))
    best_match_name: Mapped[str | None] = mapped_column(String(500))
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    all_matches: Mapped[str | None] = mapped_column(Text)  # JSON array

    # Relationships
    batch_job: Mapped["BatchJobModel"] = relationship("BatchJobModel", back_populates="results")

    __table_args__ = (Index("idx_batch_result_job", "batch_job_id", "row_number"),)


class WatchlistModel(Base):
    """User watchlist for monitoring entities."""

    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_url: Mapped[str | None] = mapped_column(String(1000))
    email_recipients: Mapped[str | None] = mapped_column(Text)  # JSON array of emails
    threshold: Mapped[float] = mapped_column(Float, default=0.80)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    entries: Mapped[list["WatchlistEntryModel"]] = relationship(
        "WatchlistEntryModel", back_populates="watchlist", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["AlertModel"]] = relationship(
        "AlertModel", back_populates="watchlist", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_watchlist_active", "is_active"),)


class WatchlistEntryModel(Base):
    """Entry in a watchlist (name to monitor)."""

    __tablename__ = "watchlist_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    watchlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    date_of_birth: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(255))
    reference_id: Mapped[str | None] = mapped_column(String(255))  # External reference
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    watchlist: Mapped["WatchlistModel"] = relationship("WatchlistModel", back_populates="entries")

    __table_args__ = (Index("idx_watchlist_entry_name", "watchlist_id", "name_normalized"),)


class AlertModel(Base):
    """Alert generated when watchlist entry matches new entity."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    watchlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    watchlist_entry_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    matched_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    matched_entity_name: Mapped[str] = mapped_column(String(500), nullable=False)
    match_score: Mapped[float] = mapped_column(Float, nullable=False)
    match_type: Mapped[str] = mapped_column(String(50), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)  # NEW_MATCH, ENTITY_ADDED, ENTITY_MODIFIED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")  # PENDING, NOTIFIED, DISMISSED
    webhook_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    watchlist: Mapped["WatchlistModel"] = relationship("WatchlistModel", back_populates="alerts")

    __table_args__ = (
        Index("idx_alert_status", "status", "created_at"),
        Index("idx_alert_watchlist", "watchlist_id", "created_at"),
    )


class AuditLogModel(Base):
    """Audit log for compliance tracking."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str | None] = mapped_column(String(36))
    user_id: Mapped[str | None] = mapped_column(String(100))  # For future auth
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    request_data: Mapped[str | None] = mapped_column(Text)  # JSON
    response_summary: Mapped[str | None] = mapped_column(Text)  # JSON summary
    status_code: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), index=True)

    __table_args__ = (
        Index("idx_audit_action_time", "action", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
    )


class SearchPresetModel(Base):
    """Saved search filter presets."""

    __tablename__ = "search_presets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    filters: Mapped[str] = mapped_column(Text, nullable=False)  # JSON with filter config
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (Index("idx_search_preset_name", "name"),)
