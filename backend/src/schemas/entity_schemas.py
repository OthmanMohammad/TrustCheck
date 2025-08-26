"""
Entity Schemas (DTOs) using Pydantic

Basic API contracts for request/response validation and serialization.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.core.enums import EntityType, SanctionsSource

# ======================== BASE SCHEMAS ========================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    class Config:
        use_enum_values = True
        from_attributes = True  # Updated for Pydantic v2

# ======================== ENTITY SCHEMAS ========================

class EntitySearchFilters(BaseModel):
    """Filters for entity search."""
    name: Optional[str] = Field(None, min_length=2, description="Search by name")
    entity_type: Optional[EntityType] = None
    source: Optional[SanctionsSource] = None
    programs: Optional[List[str]] = Field(None, description="Filter by sanctions programs")
    nationalities: Optional[List[str]] = Field(None, description="Filter by nationalities")
    is_active: Optional[bool] = Field(True, description="Include active entities")
    
    @validator('name')
    def validate_name_length(cls, v):
        if v and len(v.strip()) < 2:
            raise ValueError('Search name must be at least 2 characters')
        return v.strip() if v else v

class EntityCreate(BaseSchema):
    """Schema for creating new entities."""
    uid: str = Field(..., min_length=1, max_length=100, description="Unique identifier")
    name: str = Field(..., min_length=1, max_length=500, description="Entity name")
    entity_type: EntityType = Field(..., description="Type of entity")
    source: SanctionsSource = Field(..., description="Sanctions source")
    programs: Optional[List[str]] = Field(default_factory=list, description="Sanctions programs")
    aliases: Optional[List[str]] = Field(default_factory=list, description="Alternative names")
    addresses: Optional[List[str]] = Field(default_factory=list, description="Known addresses")
    dates_of_birth: Optional[List[str]] = Field(default_factory=list, description="Birth dates")
    places_of_birth: Optional[List[str]] = Field(default_factory=list, description="Birth places")
    nationalities: Optional[List[str]] = Field(default_factory=list, description="Nationalities")
    remarks: Optional[str] = Field(None, max_length=5000, description="Additional remarks")
    
    @validator('uid')
    def validate_uid(cls, v):
        return v.strip().upper()
    
    @validator('aliases', 'addresses', 'programs', 'dates_of_birth', 'places_of_birth', 'nationalities')
    def validate_lists(cls, v):
        if v is None:
            return []
        # Remove empty strings and duplicates
        cleaned = list(dict.fromkeys([item.strip() for item in v if item and item.strip()]))
        return cleaned

class EntityUpdate(BaseSchema):
    """Schema for updating entities."""
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    entity_type: Optional[EntityType] = None
    programs: Optional[List[str]] = None
    aliases: Optional[List[str]] = None
    addresses: Optional[List[str]] = None
    dates_of_birth: Optional[List[str]] = None
    places_of_birth: Optional[List[str]] = None
    nationalities: Optional[List[str]] = None
    remarks: Optional[str] = Field(None, max_length=5000)
    is_active: Optional[bool] = None
    
    @validator('aliases', 'addresses', 'programs', 'dates_of_birth', 'places_of_birth', 'nationalities')
    def validate_lists(cls, v):
        if v is None:
            return None
        cleaned = list(dict.fromkeys([item.strip() for item in v if item and item.strip()]))
        return cleaned

class EntitySummary(BaseSchema):
    """Lightweight entity summary for lists."""
    id: int
    uid: str
    name: str
    entity_type: str
    source: str
    programs: List[str] = Field(default_factory=list)
    is_active: bool
    last_seen: Optional[datetime] = None

class EntityDetail(EntitySummary):
    """Detailed entity information."""
    aliases: List[str] = Field(default_factory=list)
    addresses: List[str] = Field(default_factory=list)
    dates_of_birth: List[str] = Field(default_factory=list)
    places_of_birth: List[str] = Field(default_factory=list)
    nationalities: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None
    content_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# ======================== API RESPONSE SCHEMAS ========================

class APIResponse(BaseSchema):
    """Generic API response wrapper."""
    success: bool = True
    data: Optional[Any] = None
    message: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    errors: List[str] = Field(default_factory=list)

class EntityListResponse(APIResponse):
    """Paginated entity list response."""
    data: List[EntitySummary] = Field(default_factory=list)
    total_count: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 0

class SearchResponse(APIResponse):
    """Search response with metadata."""
    data: List[EntitySummary] = Field(default_factory=list)
    query: str = ""
    total_matches: int = 0
    search_time_ms: int = 0

# ======================== SCRAPER SCHEMAS ========================

class ScraperRunResponse(BaseSchema):
    """Scraper execution response."""
    status: str
    source: str
    entities_processed: int = 0
    entities_added: int = 0
    entities_updated: int = 0
    entities_removed: int = 0
    duration_seconds: float = 0
    error_message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# ======================== STATISTICS SCHEMAS ========================

class EntityStatistics(BaseSchema):
    """Entity statistics and metrics."""
    total_entities: int = 0
    active_entities: int = 0
    inactive_entities: int = 0
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    recent_additions_30d: int = 0
    statistics_generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# ======================== ERROR SCHEMAS ========================

class ErrorResponse(BaseSchema):
    """Standardized error response."""
    success: bool = False
    error: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed",
                    "details": {},
                    "error_id": "abc123"
                },
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }