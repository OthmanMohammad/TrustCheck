"""
Base schemas for API requests and responses.

Provides common base classes and utilities for all API DTOs.
"""

from typing import Any, Dict, Optional, Generic, TypeVar, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator
from enum import Enum
from uuid import UUID

# ======================== CONFIGURATION ========================

# Generic type for data payload
DataT = TypeVar('DataT')

# ======================== BASE MODELS ========================

class BaseSchema(BaseModel):
    """
    Base schema with common configuration for all DTOs.
    """
    model_config = ConfigDict(
        # Use Enums by value for JSON serialization
        use_enum_values=True,
        # Validate on assignment
        validate_assignment=True,
        # Allow population by field name or alias
        populate_by_name=True,
        # Include all fields in JSON schema
        json_schema_extra={
            "example": {}
        },
        # Forbid extra fields by default
        extra='forbid',
        # Serialize datetime as ISO string
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

class TimestampedSchema(BaseSchema):
    """Schema with timestamp fields."""
    created_at: datetime = Field(
        ...,
        description="Creation timestamp in UTC"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Last update timestamp in UTC"
    )

# ======================== REQUEST MODELS ========================

class PaginationRequest(BaseSchema):
    """Common pagination parameters for list endpoints."""
    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of items to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip"
    )
    
    @field_validator('limit')
    @classmethod
    def validate_limit(cls, v: int) -> int:
        """Ensure reasonable limits."""
        if v > 1000:
            raise ValueError("Limit cannot exceed 1000")
        return v

class FilterRequest(BaseSchema):
    """Common filter parameters."""
    active_only: bool = Field(
        default=True,
        description="Return only active items"
    )
    sort_by: Optional[str] = Field(
        None,
        description="Field to sort by"
    )
    sort_order: str = Field(
        default="desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc or desc)"
    )

class DateRangeFilter(BaseSchema):
    """Date range filter parameters."""
    start_date: Optional[datetime] = Field(
        None,
        description="Start date (inclusive)"
    )
    end_date: Optional[datetime] = Field(
        None,
        description="End date (inclusive)"
    )
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, end_date: Optional[datetime], info) -> Optional[datetime]:
        """Ensure end_date is after start_date."""
        if end_date and 'start_date' in info.data:
            start_date = info.data['start_date']
            if start_date and end_date < start_date:
                raise ValueError("end_date must be after start_date")
        return end_date

# ======================== RESPONSE MODELS ========================

class ResponseMetadata(BaseSchema):
    """Metadata for API responses."""
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp in UTC"
    )
    request_id: Optional[str] = Field(
        None,
        description="Request correlation ID"
    )
    duration_ms: Optional[float] = Field(
        None,
        description="Request processing time in milliseconds"
    )

class PaginationMetadata(BaseSchema):
    """Pagination metadata for list responses."""
    limit: int = Field(..., description="Items per page")
    offset: int = Field(..., description="Items skipped")
    total: Optional[int] = Field(None, description="Total items available")
    returned: int = Field(..., description="Items in this response")
    has_more: bool = Field(..., description="More items available")

class BaseResponse(BaseSchema, Generic[DataT]):
    """
    Base response wrapper for all API responses.
    
    Provides consistent response structure:
    - success: Operation status
    - data: Actual response data
    - metadata: Response metadata
    """
    success: bool = Field(
        ...,
        description="Whether the operation was successful"
    )
    data: Optional[DataT] = Field(
        None,
        description="Response data payload"
    )
    metadata: ResponseMetadata = Field(
        default_factory=ResponseMetadata,
        description="Response metadata"
    )

class PaginatedResponse(BaseResponse[DataT]):
    """Response wrapper for paginated list endpoints."""
    pagination: PaginationMetadata = Field(
        ...,
        description="Pagination information"
    )

class ErrorDetail(BaseSchema):
    """Detailed error information."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")

class ErrorResponse(BaseSchema):
    """Standard error response."""
    success: bool = Field(default=False)
    error: ErrorDetail = Field(..., description="Error details")
    metadata: ResponseMetadata = Field(
        default_factory=ResponseMetadata,
        description="Response metadata"
    )
    suggestions: Optional[List[str]] = Field(
        None,
        description="Suggestions for resolving the error"
    )

# ======================== VALIDATION UTILITIES ========================

class StrictString(str):
    """String that strips whitespace and validates length."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("String required")
        v = v.strip()
        if not v:
            raise ValueError("String cannot be empty")
        if len(v) > 500:
            raise ValueError("String too long (max 500 characters)")
        return v

class EntityUID(str):
    """Validated entity UID."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not isinstance(v, str):
            raise TypeError("UID must be a string")
        v = v.strip()
        if not v:
            raise ValueError("UID cannot be empty")
        # Validate UID format (alphanumeric with hyphens/underscores)
        import re
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError("Invalid UID format")
        return v

# ======================== COMMON FIELD DEFINITIONS ========================

# Common field configurations for reuse
ENTITY_NAME_FIELD = Field(
    ...,
    min_length=1,
    max_length=500,
    description="Entity name"
)

SOURCE_FIELD = Field(
    ...,
    description="Data source (OFAC, UN, EU, UK_HMT)"
)

RISK_LEVEL_FIELD = Field(
    ...,
    description="Risk level (CRITICAL, HIGH, MEDIUM, LOW)"
)

CHANGE_TYPE_FIELD = Field(
    ...,
    description="Change type (ADDED, MODIFIED, REMOVED)"
)

# ======================== EXPORTS ========================

__all__ = [
    # Base classes
    'BaseSchema',
    'TimestampedSchema',
    
    # Request models
    'PaginationRequest',
    'FilterRequest',
    'DateRangeFilter',
    
    # Response models
    'BaseResponse',
    'PaginatedResponse',
    'ResponseMetadata',
    'PaginationMetadata',
    'ErrorDetail',
    'ErrorResponse',
    
    # Validation utilities
    'StrictString',
    'EntityUID',
    
    # Field definitions
    'ENTITY_NAME_FIELD',
    'SOURCE_FIELD',
    'RISK_LEVEL_FIELD',
    'CHANGE_TYPE_FIELD',
    
    # Type variables
    'DataT'
]