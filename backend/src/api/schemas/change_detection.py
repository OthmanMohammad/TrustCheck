"""
Change detection schemas for API.

DTOs for change events, scraper runs, and notifications.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from uuid import UUID

from src.api.schemas.base import (
    BaseSchema, TimestampedSchema, PaginationRequest, FilterRequest,
    BaseResponse, PaginatedResponse, DateRangeFilter,
    EntityUID, ENTITY_NAME_FIELD, SOURCE_FIELD, RISK_LEVEL_FIELD, CHANGE_TYPE_FIELD
)

# Import enums from core
from src.core.enums import (
    DataSource, ChangeType, RiskLevel, ScrapingStatus,
    NotificationChannel, NotificationPriority
)

# ======================== FIELD CHANGE MODELS ========================

class FieldChangeDTO(BaseSchema):
    """Represents a change in a specific field."""
    field_name: str = Field(..., description="Name of the changed field")
    old_value: Any = Field(None, description="Previous value")
    new_value: Any = Field(None, description="New value")
    change_type: str = Field(
        ...,
        pattern="^(field_added|field_removed|field_modified)$",
        description="Type of field change"
    )
    is_significant: bool = Field(
        default=False,
        description="Whether this is a significant change"
    )

# ======================== CHANGE EVENT MODELS ========================

class ChangeEventSummaryDTO(BaseSchema):
    """Summary view of a change event."""
    event_id: UUID = Field(..., description="Unique event identifier")
    entity_uid: EntityUID = Field(..., description="Entity UID")
    entity_name: str = ENTITY_NAME_FIELD
    source: DataSource = SOURCE_FIELD
    change_type: ChangeType = CHANGE_TYPE_FIELD
    risk_level: RiskLevel = RISK_LEVEL_FIELD
    change_summary: str = Field(..., description="Human-readable change summary")
    detected_at: datetime = Field(..., description="When change was detected")
    notification_sent: bool = Field(default=False, description="Whether notification was sent")

class ChangeEventDetailDTO(ChangeEventSummaryDTO):
    """Detailed view of a change event."""
    field_changes: List[FieldChangeDTO] = Field(
        default_factory=list,
        description="Detailed field changes"
    )
    old_content_hash: Optional[str] = Field(None, description="Previous content hash")
    new_content_hash: Optional[str] = Field(None, description="New content hash")
    scraper_run_id: str = Field(..., description="Associated scraper run ID")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    notification_sent_at: Optional[datetime] = Field(None, description="When notification was sent")
    notification_channels: List[NotificationChannel] = Field(
        default_factory=list,
        description="Notification channels used"
    )

# ======================== CHANGE REQUESTS ========================

class ChangeFilterRequest(PaginationRequest, DateRangeFilter):
    """Request for filtering change events."""
    source: Optional[DataSource] = Field(None, description="Filter by source")
    change_type: Optional[ChangeType] = Field(None, description="Filter by change type")
    risk_level: Optional[RiskLevel] = Field(None, description="Filter by risk level")
    entity_uid: Optional[EntityUID] = Field(None, description="Filter by entity UID")
    notification_sent: Optional[bool] = Field(None, description="Filter by notification status")
    
class ChangeSummaryRequest(BaseSchema):
    """Request for change summary."""
    days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="Number of days to look back"
    )
    source: Optional[DataSource] = Field(None, description="Filter by source")
    risk_level: Optional[RiskLevel] = Field(None, description="Filter by risk level")

class CriticalChangesRequest(BaseSchema):
    """Request for critical changes."""
    hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours to look back (max 7 days)"
    )
    source: Optional[DataSource] = Field(None, description="Filter by source")

# ======================== SCRAPER RUN MODELS ========================

class ScraperRunSummaryDTO(BaseSchema):
    """Summary view of a scraper run."""
    run_id: str = Field(..., description="Unique run identifier")
    source: DataSource = SOURCE_FIELD
    status: ScrapingStatus = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    duration_seconds: Optional[float] = Field(None, description="Duration in seconds")
    entities_processed: int = Field(default=0, description="Entities processed")
    total_changes: int = Field(default=0, description="Total changes detected")
    error_message: Optional[str] = Field(None, description="Error message if failed")

class ScraperRunDetailDTO(ScraperRunSummaryDTO):
    """Detailed view of a scraper run."""
    source_url: Optional[str] = Field(None, description="Source URL")
    content_hash: Optional[str] = Field(None, description="Content hash")
    content_size_bytes: Optional[int] = Field(None, description="Content size in bytes")
    content_changed: bool = Field(default=False, description="Whether content changed")
    
    # Entity processing results
    entities_added: int = Field(default=0, description="Entities added")
    entities_modified: int = Field(default=0, description="Entities modified")
    entities_removed: int = Field(default=0, description="Entities removed")
    
    # Change classification
    critical_changes: int = Field(default=0, description="Critical changes")
    high_risk_changes: int = Field(default=0, description="High risk changes")
    medium_risk_changes: int = Field(default=0, description="Medium risk changes")
    low_risk_changes: int = Field(default=0, description="Low risk changes")
    
    # Performance metrics
    download_time_ms: Optional[int] = Field(None, description="Download time")
    parsing_time_ms: Optional[int] = Field(None, description="Parsing time")
    diff_time_ms: Optional[int] = Field(None, description="Diff calculation time")
    storage_time_ms: Optional[int] = Field(None, description="Storage time")
    
    retry_count: int = Field(default=0, description="Number of retries")

class ScraperRunRequest(BaseSchema):
    """Request to start a scraper run."""
    source: DataSource = SOURCE_FIELD
    force_update: bool = Field(
        default=False,
        description="Force update even if content unchanged"
    )
    timeout_seconds: int = Field(
        default=120,
        ge=10,
        le=3600,
        description="Timeout in seconds"
    )

# ======================== RESPONSE MODELS ========================

class ChangeSummaryDTO(BaseSchema):
    """Change detection summary."""
    period: Dict[str, Any] = Field(..., description="Time period covered")
    filters: Dict[str, Any] = Field(..., description="Applied filters")
    totals: Dict[str, int] = Field(..., description="Total counts by category")
    by_type: Dict[str, int] = Field(..., description="Counts by change type")
    by_risk_level: Dict[str, int] = Field(..., description="Counts by risk level")
    by_source: Optional[Dict[str, int]] = Field(None, description="Counts by source")
    trends: Optional[Dict[str, Any]] = Field(None, description="Change trends")

class ScrapingStatusDTO(BaseSchema):
    """Scraping system status."""
    period: Dict[str, Any] = Field(..., description="Time period")
    filter: Dict[str, Any] = Field(..., description="Applied filters")
    metrics: Dict[str, Any] = Field(..., description="System metrics")
    recent_runs: List[ScraperRunSummaryDTO] = Field(..., description="Recent scraper runs")
    next_scheduled: Optional[Dict[str, datetime]] = Field(None, description="Next scheduled runs")

class NotificationStatusDTO(BaseSchema):
    """Notification dispatch status."""
    immediate_sent: int = Field(default=0, description="Immediate notifications sent")
    high_priority_sent: int = Field(default=0, description="High priority sent")
    low_priority_queued: int = Field(default=0, description="Low priority queued")
    failed: int = Field(default=0, description="Failed notifications")
    errors: List[str] = Field(default_factory=list, description="Error messages")

# ======================== RESPONSE WRAPPERS ========================

class ChangeEventResponse(BaseResponse[ChangeEventDetailDTO]):
    """Single change event response."""
    pass

class ChangeEventListResponse(PaginatedResponse[List[ChangeEventSummaryDTO]]):
    """Change event list response."""
    filters: Optional[ChangeFilterRequest] = Field(None, description="Applied filters")
    summary: Optional[ChangeSummaryDTO] = Field(None, description="Summary statistics")

class CriticalChangesResponse(BaseResponse[List[ChangeEventDetailDTO]]):
    """Critical changes response."""
    count: int = Field(..., description="Number of critical changes")
    period: Dict[str, Any] = Field(..., description="Time period")
    notification_status: Optional[NotificationStatusDTO] = Field(None, description="Notification status")

class ChangeSummaryResponse(BaseResponse[ChangeSummaryDTO]):
    """Change summary response."""
    pass

class ScraperRunResponse(BaseResponse[ScraperRunDetailDTO]):
    """Single scraper run response."""
    pass

class ScraperRunListResponse(PaginatedResponse[List[ScraperRunSummaryDTO]]):
    """Scraper run list response."""
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")

class ScrapingStatusResponse(BaseResponse[ScrapingStatusDTO]):
    """Scraping status response."""
    pass

# ======================== DOMAIN CONVERSION ========================

def change_event_domain_to_summary(event: Any) -> ChangeEventSummaryDTO:
    """Convert domain change event to summary DTO."""
    return ChangeEventSummaryDTO(
        event_id=event.event_id,
        entity_uid=event.entity_uid,
        entity_name=event.entity_name,
        source=event.source,
        change_type=event.change_type,
        risk_level=event.risk_level,
        change_summary=event.change_summary,
        detected_at=event.detected_at,
        notification_sent=event.notification_sent_at is not None
    )

def change_event_domain_to_detail(event: Any) -> ChangeEventDetailDTO:
    """Convert domain change event to detailed DTO."""
    # Convert field changes
    field_changes = []
    if event.field_changes:
        for fc in event.field_changes:
            field_changes.append(FieldChangeDTO(
                field_name=fc.field_name,
                old_value=fc.old_value,
                new_value=fc.new_value,
                change_type=fc.change_type,
                is_significant=fc.is_significant if hasattr(fc, 'is_significant') else False
            ))
    
    return ChangeEventDetailDTO(
        event_id=event.event_id,
        entity_uid=event.entity_uid,
        entity_name=event.entity_name,
        source=event.source,
        change_type=event.change_type,
        risk_level=event.risk_level,
        change_summary=event.change_summary,
        detected_at=event.detected_at,
        field_changes=field_changes,
        old_content_hash=event.old_content_hash,
        new_content_hash=event.new_content_hash,
        scraper_run_id=event.scraper_run_id,
        processing_time_ms=event.processing_time_ms,
        notification_sent=event.notification_sent_at is not None,
        notification_sent_at=event.notification_sent_at,
        notification_channels=event.notification_channels or []
    )

def scraper_run_domain_to_summary(run: Any) -> ScraperRunSummaryDTO:
    """Convert domain scraper run to summary DTO."""
    total_changes = (
        run.critical_changes + run.high_risk_changes +
        run.medium_risk_changes + run.low_risk_changes
    )
    
    return ScraperRunSummaryDTO(
        run_id=run.run_id,
        source=run.source,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        entities_processed=run.entities_processed,
        total_changes=total_changes,
        error_message=run.error_message
    )

def scraper_run_domain_to_detail(run: Any) -> ScraperRunDetailDTO:
    """Convert domain scraper run to detailed DTO."""
    return ScraperRunDetailDTO(
        run_id=run.run_id,
        source=run.source,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_seconds=run.duration_seconds,
        source_url=run.source_url,
        content_hash=run.content_hash,
        content_size_bytes=run.content_size_bytes,
        content_changed=run.content_changed,
        entities_processed=run.entities_processed,
        entities_added=run.entities_added,
        entities_modified=run.entities_modified,
        entities_removed=run.entities_removed,
        critical_changes=run.critical_changes,
        high_risk_changes=run.high_risk_changes,
        medium_risk_changes=run.medium_risk_changes,
        low_risk_changes=run.low_risk_changes,
        download_time_ms=run.download_time_ms,
        parsing_time_ms=run.parsing_time_ms,
        diff_time_ms=run.diff_time_ms,
        storage_time_ms=run.storage_time_ms,
        total_changes=(
            run.critical_changes + run.high_risk_changes +
            run.medium_risk_changes + run.low_risk_changes
        ),
        error_message=run.error_message,
        retry_count=run.retry_count
    )

# ======================== EXPORTS ========================

__all__ = [
    # Field change models
    'FieldChangeDTO',
    
    # Change event models
    'ChangeEventSummaryDTO',
    'ChangeEventDetailDTO',
    'ChangeFilterRequest',
    'ChangeSummaryRequest',
    'CriticalChangesRequest',
    
    # Scraper run models
    'ScraperRunSummaryDTO',
    'ScraperRunDetailDTO',
    'ScraperRunRequest',
    
    # Response models
    'ChangeSummaryDTO',
    'ScrapingStatusDTO',
    'NotificationStatusDTO',
    'ChangeEventResponse',
    'ChangeEventListResponse',
    'CriticalChangesResponse',
    'ChangeSummaryResponse',
    'ScraperRunResponse',
    'ScraperRunListResponse',
    'ScrapingStatusResponse',
    
    # Conversion functions
    'change_event_domain_to_summary',
    'change_event_domain_to_detail',
    'scraper_run_domain_to_summary',
    'scraper_run_domain_to_detail'
]