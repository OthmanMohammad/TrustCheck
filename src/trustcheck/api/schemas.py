"""
TrustCheck API Schemas.

Pydantic models for API request/response serialization.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# Base schemas
class BaseResponse(BaseModel):
    """Base response model with common fields."""

    success: bool = True
    message: str | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int
    limit: int
    offset: int
    returned: int


class PaginatedResponse(BaseResponse):
    """Paginated response model."""

    pagination: PaginationMeta | None = None


# Entity schemas
class NameSchema(BaseModel):
    """Name (alias) schema."""

    value: str
    type: str
    script: str = "LATIN"


class AddressSchema(BaseModel):
    """Address schema."""

    country: str | None = None
    city: str | None = None
    street: str | None = None
    postal_code: str | None = None
    full_address: str | None = None


class IdentifierSchema(BaseModel):
    """Identifier (passport, ID) schema."""

    type: str
    value: str
    country: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None


class EntitySummary(BaseModel):
    """Brief entity summary for lists."""

    id: str
    primary_name: str
    entity_type: str
    is_active: bool
    programs: list[str] = []
    sources: list[str] = []
    updated_at: datetime | None = None


class EntityDetail(BaseModel):
    """Full entity details."""

    id: str
    primary_name: str
    primary_name_normalized: str
    entity_type: str
    names: list[NameSchema] = []
    addresses: list[AddressSchema] = []
    identifiers: list[IdentifierSchema] = []
    programs: list[str] = []
    date_of_birth: str | None = None
    year_of_birth: int | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    remarks: str | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EntityListResponse(PaginatedResponse):
    """Response for entity list endpoint."""

    data: list[EntitySummary] = []


class EntityDetailResponse(BaseResponse):
    """Response for entity detail endpoint."""

    data: EntityDetail | None = None


# Screening schemas
class ScreeningRequest(BaseModel):
    """Request for name screening."""

    name: str = Field(..., min_length=1, max_length=500, description="Name to screen")
    date_of_birth: date | None = Field(None, description="Optional date of birth for boosting")
    country: str | None = Field(None, max_length=3, description="Optional country code (ISO 3166)")
    threshold: float = Field(0.80, ge=0.0, le=1.0, description="Minimum match score")
    include_inactive: bool = Field(False, description="Include inactive entities")
    max_results: int = Field(100, ge=1, le=1000, description="Maximum results to return")


class BatchScreeningRequest(BaseModel):
    """Request for batch name screening."""

    names: list[str] = Field(..., min_length=1, max_length=10000)
    threshold: float = Field(0.80, ge=0.0, le=1.0)
    include_inactive: bool = False


class MatchedFieldSchema(BaseModel):
    """Details of a matched field."""

    field_name: str
    query_value: str
    matched_value: str
    score: float
    match_type: str


class ScreeningMatchSchema(BaseModel):
    """A single screening match."""

    entity_id: str
    entity_name: str
    entity_type: str
    score: float
    match_type: str
    matched_fields: list[MatchedFieldSchema] = []
    sources: list[str] = []
    programs: list[str] = []


class ScreeningResponse(BaseResponse):
    """Response for screening endpoint."""

    request_id: str
    query: str
    matches: list[ScreeningMatchSchema] = []
    screened_at: datetime
    processing_time_ms: float


class BatchScreeningResponse(BaseResponse):
    """Response for batch screening endpoint."""

    total_names: int
    total_matches: int
    results: dict[str, list[ScreeningMatchSchema]] = {}


# Change schemas
class ChangeEventSchema(BaseModel):
    """Change event schema."""

    id: str
    entity_id: str
    entity_name: str
    source: str
    change_type: str
    field_changes: dict[str, Any] = {}
    detected_at: datetime
    scraper_run_id: str | None = None


class ChangeListResponse(PaginatedResponse):
    """Response for change list endpoint."""

    data: list[ChangeEventSchema] = []


class ChangeStatsSchema(BaseModel):
    """Change statistics."""

    changes_last_24h: int
    changes_last_7d: int
    changes_by_source: dict[str, int] = {}
    changes_by_type: dict[str, int] = {}


class ChangeStatsResponse(BaseResponse):
    """Response for change stats endpoint."""

    data: ChangeStatsSchema | None = None


# Admin schemas
class ScraperStatusSchema(BaseModel):
    """Scraper run status."""

    source: str
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    entities_processed: int = 0
    entities_added: int = 0
    entities_modified: int = 0
    entities_removed: int = 0
    error_message: str | None = None


class ScraperTriggerRequest(BaseModel):
    """Request to trigger a scraper."""

    source: str = Field(..., description="Source to scrape (OFAC_SDN, UN, EU, UK)")


class ScraperTriggerResponse(BaseResponse):
    """Response for scraper trigger endpoint."""

    job_id: str
    source: str
    status: str


class ScheduledJobSchema(BaseModel):
    """Scheduled job info."""

    id: str
    name: str
    trigger: str
    next_run: str | None = None


class SystemStatusResponse(BaseResponse):
    """System status response."""

    version: str
    environment: str
    database_connected: bool
    scheduler_running: bool
    jobs: list[ScheduledJobSchema] = []
    scraper_statuses: list[ScraperStatusSchema] = []


# Dashboard schemas
class DashboardStatsSchema(BaseModel):
    """Dashboard statistics."""

    total_entities: int
    active_entities: int
    entities_by_source: dict[str, int] = {}
    entities_by_type: dict[str, int] = {}
    changes_last_24h: int
    changes_last_7d: int
    last_scrape_times: dict[str, datetime | None] = {}
    scraper_statuses: dict[str, str] = {}


class DashboardResponse(BaseResponse):
    """Response for dashboard endpoint."""

    data: DashboardStatsSchema | None = None


# Health check schemas
class HealthCheckResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    environment: str
    database: str
    scheduler: str
    timestamp: datetime


# Search schemas
class SearchRequest(BaseModel):
    """Search request."""

    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(50, ge=1, le=500)
    active_only: bool = True


class SearchResponse(BaseResponse):
    """Response for search endpoint."""

    query: str
    data: list[EntitySummary] = []
